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

This document suggest three different approaches for configuring this,
each with their own upsides and downsides.


Option 1: using exports and NRTM for migrations and standby instances
---------------------------------------------------------------------
The first option is to use the same :doc:`mirroring </users/mirroring>`
features as any other kind of IRR data mirroring. This means using the files
placed in ``sources.{name}.export_destination`` by the active instance
as the ``sources.{name}.import_source`` for the standby instances,
and having standby's follow the active NRTM stream.
If you are migrating from a legacy version of IRRd, this is most likely your
only option.

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

GPG keychain imports
~~~~~~~~~~~~~~~~~~~~
In short: standby instances should have ``strict_import_keycert_objects``
enabled.

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

Password hashes
~~~~~~~~~~~~~~~
Password authentication depends on password hashes in `mntner` objects.
To improve security, these password hashes are not included in exports or
NRTM streams for regular mirrors in IRRDv4.

However, when an IRRd mirror is a standby
instance that may need to take an active role later, it needs all password
hashes. To support this, you need to configure a special mirroring process
on the current active instance:

* Set ``sources.{name}.export_destination_unfiltered`` to a path where IRRd
  will store exports that include full password hashes. Other than including
  full hashes, this works the same as ``sources.{name}.export_destination``.
  Then, distribute those files to your standby instance, and point
  ``import_source`` to their location.
* Set ``sources.{name}.nrtm_access_list_unfiltered`` to an access list defined
  in the configuration file. Any IP on this access list will receive
  full password hashes when doing NRTM requests. Other than that, NRTM works
  identical to filtered queries. Set this to the IPs of your standby instances.

On the standby instance, you do not need any specific configuration.
However, if you used previously imported `mntner` objects without full hashes
on the standby, you need to do a full reload of the data on the standby to
ensure it has full hashes for all objects.

If you are migrating from a different IRR server, check that password
hashes are not filtered.

Serials
~~~~~~~
Each IRRd instance potentially creates its own set of NRTM serials when
importing changes over NRTM.
This means that when switching to a different instance, mirrors would
have to refresh their data.

IRRd can run a mirror in synchronised serial mode. This is used by some
deployments to spread their query load over multiple read-only instances.
For further details, see the
:ref:`NRTM serial handling documentation <mirroring-nrtm-serials>`.

.. warning::
   When not using synchronised serials, NRTM users must never be switched
   (e.g. by DNS changes or load balancers) to different instances, without
   reloading their local copy. Otherwise they may silently lose updates.

   Without synchronised serials, the RPSL export, CURRENTSERIAL file, and NRTM
   feed used by a mirror must all come from the same source instance.

RPKI and scope filter
~~~~~~~~~~~~~~~~~~~~~
:doc:`RPKI-aware mode </admins/rpki>` and the
:doc:`scope filter </admins/scopefilter>` make invalid or out of scope
objects invisible locally. These are not included in any exports, and if
an existing object becomes invalid or out of scope, a deletion is added
to the NRTM journal.

IRRd retains invalid or out of scope objects, and they may become visible again
if their status is changed by a configuration or ROA change.
However, a standby or query-only instance using exports and NRTM will never see
objects that are invalid or out of scope on the active instance, as they are
not included in mirroring.
Upon promoting a standby instance to an active instance, these
objects are lost permanently.

For the same reasons, standby and query-only instances that receive their
data over NRTM can not be queried for RPKI invalid or out of scope objects,
as they never see these objects.

Promoting a standby to the active instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you use IRR mirroring with exports and NRTM, the general plan for promoting
an IRRDv4 instance would be:

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

If this is part of a planned migration from a previous version, it is
recommended that you test existing tools and queries against the new IRRDv4
instance before promoting it to be active.


Option 2: PostgreSQL replication
-------------------------------------------

.. danger::
   Since adding this section, an issue was discovered with using PostgreSQL
   replication: the `local preload store may not be updated`_ causing
   potential stale responses to queries.

 .. _local preload store may not be updated: https://github.com/irrdnet/irrd/issues/656

Except for configuration, IRRd stores all its data in the PostgreSQL database.
Redis is used for passing derived data and commands.

You could run two IRRd instances, each on their own PostgreSQL instance, which
use PostgreSQL replication as the synchronisation mechanism. In the standby
IRRd, configure the instance as ``database_readonly`` to prevent local changes.
Note that this prevents the IRRd instance from making any changes of any kind
to the local database.

For Redis, you need to connect all instances to the same Redis instance,
or use `Redis replication`_.

Using PostgreSQL replication solves some of the issues mentioned for other
options, but may have other limitations or issues that are out of scope
for IRRd itself.

.. _Redis replication: https://redis.io/topics/replication

GPG keychain imports with PostgreSQL replication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When you use PostgreSQL replication, the same issue occurs with the GPG
keychain as with NRTM: in order to authenticate updates to authoritative
changes, the PGP keys need to be loaded into the local keychain, which does
not happen for mirrors.

When using PostgreSQL replication, IRRd is not aware of how the objects in the
database are being changed. Therefore, you need to run the
``irrd_load_pgp_keys`` command before making a standby instance the active
instance to make sure PGP authentication keeps working.


Option 3: rebuilding from a periodic SQL dump
---------------------------------------------
You can make a SQL dump of the PostgreSQL database and load it on another IRRd
instance. This is one of the simplest methods. However, it has one significant
danger: if changes happened in the old active instance, after the dump was made,
the dump is loaded into a new instance, which is then promoted to active, the
changes are not in the dump. This is expected. Worse is that new
changes made in the new active instance will reuse the same serials, and may
not be picked up by NRTM mirrors unless they refresh their copy.

The same concerns for the GPG keychain with PostgreSQL replication apply
to this method as well.
