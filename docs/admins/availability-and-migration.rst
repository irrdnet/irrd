====================================
IRRd availability and data migration
====================================

This document explains approaches you can take to set up standby instances
of IRRd, how you might switch between instances, and share load between multiple
instances. This document only applies when you run an authoritative IRR
registry. If you do not, availability is much simpler: run multiple instances
that each mirror from the original sources.

While this document explains this from the limited perspective
of IRRd itself, always think carefully about your own availability requirements,
what kind of failure modes exist, and how you are monitoring and mitigating them.

As migrating from a legacy IRRd is partially like building a standby instance,
which is then promoted to the active instance,
that scenario is also covered here.

.. contents::
   :backlinks: none
   :local:

Migrating and mirroring data
----------------------------
You need to migrate or continuously mirror authoritative IRR data between your
IRRd instances in a number of cases:

* You are migrating to IRRDv4 from a legacy version of IRRd.
* You are migrating from one IRRDv4 deployment to the other.
* You are using one IRRd instance as the active instance, and would like to
  have a second on standby to promote to the active instance with the
  most recent data.
* You have a large volume of queries and want to distribute load over
  multiple instances.

This document mainly discusses three kinds of IRRd instances:

* An **active** instance is an IRRd instance that is accepting and processing
  authoritative changes. Others can mirror from the active instance.
  This might also be a current legacy IRRd instance.
* A **standby** instance mirrors from the active instance, and is intended to
  be promoted to the active instance as part of a migration or fallback.
  While in a standby role, it can be used for queries, as those are read-only.
* A **query-only** instance mirrors from an active instance, and is never
  intended to be promoted to an active instance.

.. warning::
    It is important that there is only a single IRRd instance
    that processes authoritative changes, and is the single source of truth,
    at one point in time. IRRd does not support having multiple active instances.

.. warning::
    Previous versions of IRRd and this documentation suggested standby servers
    with NRTM as an option. This option is strongly recommended against, due to
    incompatibility with :doc:`object suppression </admins/object-suppression>`
    along with other issues regarding mirror synchronisation.
    The ``sources.{name}.export_destination_unfiltered`` and
    ``sources.{name}.export_destination`` settings are deprecated.


Using PostgreSQL replication for standby and query-only instances
-----------------------------------------------------------------
The best option to run either standby or query-only instance is using
PostgreSQL replication. All persistent IRRD data is stored in the
PostgreSQL database, and will therefore be included.
PostgreSQL replication will also ensure all journal entries and
serials remain the same after a switch.
:doc:`Suppressed objects </admins/object-suppression>`, e.g. by RPKI
validation, and suspended objects,
are correctly included in the replication as well.

There are several important requirements for this setup:

* The standby must run a PostgreSQL streaming replication from the
  active instance. Logical replication is not supported.
* The PostgreSQL configuration must have ``track_commit_timestamp``
  and ``hot_standby_feedback`` enabled.
* On the standby, you run the IRRD instance with the ``readonly_standby``
  parameters set.
* The standby instance must use its own Redis instance. Do not use
  Redis replication.
* ``rpki.roa_source`` must be consistent between active and standby
  configurations.
* You are recommended to keep other settings, like ``scopefilter``,
  ``sources.{name}.route_object_preference``,
  ``sources.{name}.object_class_filter`` consistent between active
  and standby. Note that you can not set
  ``sources.{name}.authoritative``, ``sources.{name}.nrtm_host``, or
  ``sources.{name}.import_source`` on a standby instance, as these
  conflict with ``readonly_standby``.
* All instances must run the same IRRD version.
* It is recommended that all PostgreSQL instances only host the IRRd
  database. Streaming replication will always include all databases,
  and commits received on the standby in any database will trigger
  a local preloaded data refresh.
* Although the details of PostgreSQL are out of scope for
  this documentation, the use of replication slots is recommended.
  Make sure to drop a replication slot if you decommission a
  standby server, to prevent infinite PostgreSQL WAL growth.

As replication replicates the entire database, any IRR registries
mirrored on the active instance, are also mirrored on the standby,
through the PostgreSQL replication process.

Consistency in object suppression settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you query IRRD's configuration on a standby, e.g. with the ``!J``
query, it will reflect the local configuration regarding
:doc:`object suppression settings </admins/object-suppression>`.
However, the standby does not use these settings: its database is
read only, and instead the suppression is applied by the active
instance and then replicated.

For consistency in this query output, and reduced risk of configuration
inconsistencies after promoting a standby, you are encouraged to keep
the object suppression settings identical on all instances, even
if some are (currently) not used.

For RPKI, ``rpki.roa_source`` must be consistent between active and
standby, because that setting determines whether the query parser
considers ``RPKI`` a valid source.

Promoting a standby instance to active
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The general plan for promoting an IRRDv4 instance is:

* Hold all update emails.
* Ensure PostgreSQL replication is up to date.
* Promote the PostgreSQL replica to become a main server.
* Disable the ``readonly_standby`` setting in IRRd.
* Make sure your IRRD configuration on the standby is up to date
  compared to the old active (ideally, manage this continuously).
  Make sure the ``authoritative`` setting is enabled on your authoritative
  source, and mirroring settings for any mirrored sources, e.g.
  ``nrtm_host`` are correct.
* Start the IRRd instance.
* Redirect queries to the new instance.
* Run the ``irrd_load_pgp_keys`` command to load all PGP keys from
  authoritative sources into the local keychain, allowing them to be used
  for authentication.
* Redirect update emails to the new instance.
* Ensure published exports are now taken from the new instance.
* Check the mirroring status to ensure the new active instance
  has access to all exports and NRTM streams (some other operators
  restrict NRTM access to certain IPs).

.. warning::
    If users use IRRD internal authentication, by logging in through
    the web interface, ensure you have a consistent URL, i.e.
    direct to the current active instance by DNS records. WebAuthn
    tokens are tied to the URL as seen by the browser, and will
    become unusable if you change the URL.

Upgrading IRRD
~~~~~~~~~~~~~~
When upgrading your IRRD instances, first upgrade the active instance,
then the standby instances. If you need to run ``irrd_database_upgrade``
as part of the upgrade, only do so on the active instance. PostgreSQL
replication will include the schema changes and update standby
databases.

.. note::
    During the time between the database upgrade and upgrading the IRRD
    version on a standby instance, queries on the standby instance may fail.
    This depends on the exact changes between versions.

You are encouraged to always test upgrades yourself before applying them
in production.

Preload data refresh on standby instances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There is one inefficiency in the replication process: like an active
instance, a standby instance will keep certain data in memory and/or
Redis for performance reasons. This data needs to be refreshed if
certain data changes in the SQL database.

On an active instance, the preloaded data is refreshed only when
relevant RPSL objects have changed. On a replica, this information
is not available. Therefore, standby instances refresh this data
after any change to the SQL database. Therefore, you may see more
load on the preload process than is typical on an active instance.
Refreshes are batched, so only a single one will run at a time.

Due to small differences in the timing of the preload process,
there may be an additional delay in updating responses to some
queries on the standby compared to the active instance, in the
order of 15-60 seconds.
This concerns the whois queries ``!g``, ``!6``, ``!a`` and in some cases ``!i``,
and the GraphQL queries ``asnPrefixes`` and ``asSetPrefixes``.


Query-only instances using NRTM
-------------------------------
If you want to distribute the query load, but will never promote the
secondaries to active instances, you can use the PostgreSQL replication
method described above, or NRTM mirroring.
Consider carefully whether you really only need a query-only
instance, or may need to use it as a standby instance later. Promoting
an NRTM query-only instance to an active instance is unsupported.

When others mirror from your instance using NRTM, you need to be aware
of serial synchronisation. There are two options:

* Direct all NRTM queries to your active instance. Publish the RPSL export
  and CURRENTSERIAL file from that instance.
* Use synchronised serials, allowing NRTM queries to be sent to any query-only
  instance. Publish the RPSL export and CURRENTSERIAL file from the active
  instance.

For further details, see the
:ref:`NRTM serial handling documentation <mirroring-nrtm-serials>`.

.. warning::
   When **not** using synchronised serials, NRTM users must never be switched
   (e.g. by DNS changes or load balancers) to different instances, without
   reloading their local copy. Otherwise they may silently lose updates.


Loading from a PostgreSQL backup
--------------------------------
You can initialise an IRRD instance from a database backup, either as
part of a recovery or a planned migration. Key steps:

* If the backup was made with an older IRRD version, run
  ``irrd_database_upgrade`` to upgrade the schema.
* Run the ``irrd_load_pgp_keys`` command to load all PGP keys from
  authoritative sources into the local keychain, allowing them to be used
  for authentication.


Migration from legacy IRRD
--------------------------
To migrate from a legacy IRRD version, you can use the same
:doc:`mirroring </users/mirroring>` features as any other kind of IRR
data mirroring. In addition to usual mirroring, you should enable
``strict_import_keycert_objects`` for the source.

This is a bit different from "regular" mirroring, where the mirror
is never meant to be promoted to an active instance, and instances may be run by entirely
different organisations for different reasons.
There are a number of important special circumstances when using exports and
NRTM for migrations or availability, which are detailed below.

Note that an active IRRd instance for one IRR registry may simultaneously be a
regular mirror for other registries.

.. note::
   If you are migrating from a legacy version of IRRd, also see the
   :doc:`legacy migration documentation </admins/migrating-legacy-irrd>`
   for relevant changes. Also relevant for legacy migrations is that IRRd
   will only import one object per primary key from files. if you have
   multiple objects in your file with the same key, IRRd will
   only import the last one.

Object validation
~~~~~~~~~~~~~~~~~
Mirrored sources use
:doc:`less strict validation than authoritative data </admins/object-validation>`
This allows graceful upgrades of slightly invalid objects, and is especially
useful when migrating data from a legacy version of IRRd with lax validation.

It means that IRRd will permit objects that are invalid under strict
validation while running as a mirror. After making an instance authoritative,
any future changes to objects need to meet strict validation rules.
This means objects are slowly corrected as users change them, without
immediate service impact.

Some objects may be too invalid for IRRd to be able to import them
even in non-strict mode. These objects are logged. **While running IRRd 4
as a mirror, you should check the logs for any such objects - they will
disappear when you make IRRd 4 your authoritative instance.**

Serials
~~~~~~~
Each instance potentially creates its own set of NRTM serials when
importing changes over NRTM.
This means that when switching to a different instance, mirrors would
have to refresh their data.

Promoting a IRRD mirror of a legacy instance to active
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use IRR mirroring with exports and NRTM, the general plan for switching
from a legacy IRRD to a new IRRDv4 instance would be:

* Hold all update emails.
* Ensure an NRTM update has run so that the instances are in sync
  (it may be worthwhile to lower ``import_timer``)
* Remove the mirror configuration from the promoted instance for
  the authoritative sources.
* Set the authoritative sources to ``authoritative: true`` in the config
  of the promoted instance.
* Redirect queries to the new instance.
* Redirect update emails to the new instance.
* Ensure published exports are now taken from the new instance.
* If you were not using synchronised serials, all instances mirroring from
  your instance, must reload their local copy.

It is recommended that you test existing tools and queries against the
new IRRDv4 instance before promoting it to be active.


Background and design considerations
------------------------------------

GPG keychain imports
~~~~~~~~~~~~~~~~~~~~
IRRd uses GnuPG to validate PGP signatures used to authenticate authoritative
changes. This means that all `key-cert` objects need to be inserted into the
GnuPG keychain before users can submit PGP signed updates.

By default, IRRd only inserts public PGP keys from `key-cert` objects for
authoritative sources - as there is no reason to do PGP signature validation
for non-authoritative sources. However, a standby source needs to have these
keys imported already to become active later. This can be enabled with the
``strict_import_keycert_objects`` setting on the mirror configuration.
When enabled, `key-cert` objects always use the strict importer which includes
importing into the key chain, which allows them to be used for authentication
in the future.

If your IRRd instance already has (or may have) `key-cert` objects that were
imported without ``strict_import_keycert_objects``, you can insert them into the
local keychain with the ``irrd_load_pgp_keys`` command.

The ``irrd_load_pgp_keys`` command may fail to import certain keys if they use
an unsupported format. It is safe to run multiple times, even if some or all
keys are already in the keychain, and safe to run while IRRd is running.

Suppressed objects
~~~~~~~~~~~~~~~~~~
:doc:`Suppressed objects </admins/object-suppression>` are invisible
to normal queries and to the NRTM feed, but not deleted. They may
become visible again at any point in the future, e.g. by someone
creating a ROA or a change in another object.

Suppressed objects are included in the PostgreSQL database, but not
in any RPSL exports. Therefore, the RPSL exports can not be used
as a full copy of the database. Otherwise all suppressed objects
would be lost upon promotion of a standby instance, which has
seemingly no effect if they remain suppressed, but also means they
can not become visible later.

In a PostgreSQL replication setup, only the active instance will run
the object suppression tasks. Standby instances replicate the state
of the database including suppression status and e.g. the ROA
table.
