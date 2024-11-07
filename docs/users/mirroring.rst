===================
Mirroring with IRRd
===================

IRRd can mirror other sources, and offers mirroring services for
other users.

This page explains the processes and caveats involved in mirroring.
For details on all configuration options, see
the :doc:`configuration documentation </admins/configuration>`.

.. note::
    If :doc:`object suppression </admins/object-suppression>` is enabled,
    including RPKI-aware mode, this also affects mirroring.

Scheduling
----------

All mirroring processes, except answering NRTMv3 queries, are run in a separate
process for each source. The frequencies at which they run can be configured
for each source and for importing and exporting separately, but there are
default settings.

A global scheduler runs every 3 seconds, which will start mirror import and/or
export processes for one source for which the `import_timer` or `export_timer`
has expired. On startup, all mirror processes are started (at 3 second intervals),
as all their timers are considered expired.

If a previously scheduled process is still running, no new process will be
run, until the current run for this source is finished and the timer
expires again. This means that, for example, when mirroring a source with NRTM
mode, ``import_timer`` can be safely kept low, even though the initial large
full import may take some time.

NRTMv4 overview
---------------

The recommended method of mirroring to/from other databases is NRTM version 4.

NRTMv4 uses `draft-ietf-grow-nrtm-v4`_ which loads JSON-ish files over HTTPS.

The basic building blocks of NRTMv4 are:

* The Update Notification File (UNF), a JSON file that serves as an index.
* The Update Notification File signature, which proves the authenticity
  of the UNF.
* A Snapshot file that contains all objects in a database at a particular time,
  at a particular version number.
* Zero or more Delta files that contain changes to a database.
  A mirror server generates one every minute, with all changes in that minute,
  if there were any changes.
  Each Delta file has an increasing version number.
* The UNF has a random session ID. If this is changed, all clients
  must reload from the snapshot.
* The server keeps Delta files for 24 hours. If a client lags behind too
  far, it will detect this, and reload from the snapshot.

NRTMv4 is reliable, detects errors, secure, and recovers automatically
from loss of synchronisation.

.. _draft-ietf-grow-nrtm-v4: https://datatracker.ietf.org/doc/draft-ietf-grow-nrtm-v4/


Mirroring services for others (exporting)
-----------------------------------------

Two modes for running a mirror servers are available. You can enable
both of them at the same time for the same source.

NRTMv4 mode
~~~~~~~~~~~
To configure an NRTMv4 source, you set the ``nrtm4_server_private_key``
and ``nrtm4_server_local_path`` settings on the
source. The local path is where IRRD will write the files, the base URL
is the full HTTPS URL under which you will be serving the files.
The private key must be a JWK private key in PEM. You can use the
``irrdctl nrtmv4 generate-private-key`` command generate such a key,
though does not store the key in the configuration for you.
You need to use a separate base URL and local path for each
IRR source.

When running the NRTMv4 server process, IRRD will:

* Check that all previous Snapshot and Delta files are still present.
  If a file is missing, the ongoing session is corrupt and will be reset.
* If there is no ongoing session, generate a new session ID and start
  from version 1.
* If there an ongoing session, find any changes since the last Delta file,
  and if there were changes, write a new Delta file.
* If ``nrtm4_server_snapshot_frequency`` has expired (default: 4 hours),
  or there was no ongoing session, write a new snapshot.
* Expire any Delta files older than 24 hours.
* Remove any dangling Delta files.
* Remove older UNF signature files and Snapshot (they are kept for a while
  after no longer being needed, to avoid race conditions).
* Generate a new Update Notification File signature file.
* Write the new Update Notification File.

You need to serve the files written to ``nrtm4_server_local_path`` on
HTTPS, so that clients can retrieve them.
You then tell clients the full URL to ``update-notification-file.jose``
which IRRD will create in the provided path. You can serve them
using the same nginx instance used for other parts of IRRD,
or through an entirely different web server or CDN, depending on your
scalability needs. So in a way, the actual "serving" part of an
NRTMv4 server is not performed by IRRD, as it's just static files over HTTPS.

NRTMv4 has support for in-band key rotation. Use the following process:

* Generate a new private key.
* Save the new key in ``nrtm4_server_private_key_next`` on the source.
* IRRD will automatically add the public key to the ``next_signing_key``
  field in the Update Notification File.
* On their next update of the Update Notification File, clients will
  see the next key, and store it.
* After some time (recommended: one week), set the new key in
  ``nrtm4_server_private_key`` and remove ``nrtm4_server_private_key_next``.
* Key rotation is now complete.

The private key(s) stored in your IRRD configuration should never be
shared publicly. Clients should only have the public key.
At any time you can use the ``irrdctl nrtmv4 server-show-public-key``
command to see the public key of the configured private key(s).


NRTMv3 mode
~~~~~~~~~~~
IRRd can produce periodic exports and generate NRTMv3 responses to support
mirroring of authoritative or mirrored data by other users.

Periodic exports of the database can be produced for all sources. They consist
of a full export of the text of all objects for a source, gzipped and encoded
in UTF-8. If a serial is known, another file is exported with the serial
number of this export. If the database is entirely empty, an error is logged
and no files are exported.

NRTMv3 responses can be generated for all sources that have `keep_journal`
enabled, as the NRTMv3 response is based on the journal, which records changes
to objects. A journal can be kept for both authoritative sources and mirrors.

In typical setups, the files exported to `export_destination` will be published
over FTP to allow mirrors to load all initial data. After that, NRTMv3 requests
can be made to receive recent changes. If a mirroring client lags behind too
far, it may need to re-import the entire database to catch up.

The NRTMv3 query format is::

    -g <source>:<version>:<serial start>-<serial end>

The version can be 1 or 3. The serial range included the starting and ending
serials. If the ending serial is ``LAST``, all changes from the starting serial
up to the most recent change will be sent. Admins can configure an access list
for NRTMv3 queries. By default all NRTMv3 requests are denied.

To a query like ``-g EXAMPLESOURCE:3:998350-LAST``, the response may look
like this::

    %START Version: 3 EXAMPLESOURCE 998350-998351

    ADD 998350

    person:         Test person
    address:        DashCare BV
    address:        Amsterdam
    address:        The Netherlands
    phone:          +31 20 000 0000
    nic-hdl:        PERSON-TEST
    mnt-by:         TEST-MNT
    e-mail:         email@example.com
    source:         EXAMPLESOURCE

    DEL 998351

    route-set:      RS-TEST
    descr:          TEST route set
    mbrs-by-ref:    TEST-MNT
    tech-c:         PERSON-TEST
    admin-c:        PERSON-TEST
    mnt-by:         TEST-MNT
    source:         EXAMPLESOURCE

    %END EXAMPLESOURCE

In NRTM version 1, serials for individual operations (on the `ADD`/`DEL` lines
are omitted, and the version in the header is `1`.

.. caution::
    NRTM version 1 can be ambiguous when there are gaps in NRTM serials. These
    can occur in a variety of situations. It is strongly recommended to always
    use NRTM version 3.

For authoritative databases in IRRd, serials are guaranteed to be sequential
without any gaps. However, various scenarios can result in gaps in
serials from mirrored databases.


Mirroring other databases (importing)
-------------------------------------

There are three different modes to mirror other databases: NRTMv4 mode, NRTMv3 mode
and periodic full imports. Regardless of mode, all updates are performed in a
single transaction. This means that, for example, when a full reload of a mirror
is performed, clients will keep seeing the old objects until the import is
entirely ready. Clients should never see half-finished imports.

A single source can only use one mirroring mode.

NRTMv4 mode
~~~~~~~~~~~
To configure an NRTMv4 source, you set the ``nrtm4_client_notification_file_url``
setting on the source to the Update Notification File URL.
and the ``nrtm4_client_notification_file_url`` setting to the initial public key.
Both of these will be published by the mirror server operator.

When running the NRTMv4 client process, IRRD will:

* Retrieve and validate the Update Notification File and its signature.
* Check if the force reload flag was set by the ``irrd_mirror_force_reload`` command,
  if so, IRRD reloads from snapshot.
* Check if the session ID is the same as previously known. If not,
  IRRD reloads from snapshot.
* Check if there is a version update. If not, IRRD is up to date and
  no action is needed.
* Check if there are deltas available to update from the current local
  version to the latest. If not, IRRD was lagging too far behind, and
  reloads from snapshot.
* Download and process any relevant delta files.

Whenever IRRD reloads from the snapshot, all local RPSL objects and
journal entries for the source are discarded.

There are some aspects of key management you should be aware of.
For authentication, the UNF is signed, and IRRD uses a public key
to validate the signature. The key set in the
``nrtm4_client_initial_public_key`` setting is the initial key. Once IRRD
has retrieved a valid UNF, it will store the used key in the database.
This is required for key rotation, where a mirror server operator may
transition to a new key, also stored in IRRDs database. This allows
key rotation to be processed entirely automatically without changing your
client configuration. If you missed a key rotation window, or want to
pull NRTMv4 data from a different server, you may need to clear the
key information from the IRRD database.
You can do this with the ``irrdctl nrtmv4 client-clear-known-keys``
command. After that, IRRD will revert back to using the public key from the
``nrtm4_client_initial_public_key`` setting, until the next successful UNF
retrieval.

.. warning::
    Automatically reloading from a snapshot means IRRD will recover
    mirroring in many scenarios. However, the journal is
    cleared when this happens, which means that if you in turn offer
    NRTMv3 of the same source to other clients, they will also
    need to reload. As NRTMv3 has no signalling for this, those
    operators will need to do this manually.

The default ``import_timer`` for NRTMv4 clients is 60 seconds.

NRTMv3 mode
~~~~~~~~~~~
.. note::
    NRTMv4 is always recommended above NRTMv3, as it is much more reliable
    and secure.

NRTMv3 mode uses a download of a full copy of the database, followed by updating
the local data using NRTMv3 queries. This requires a downloadable full copy,
the serial belonging to that copy, and NRTMv3 access. This method is recommended,
as it is efficient and allows IRRd to generate a journal, if enabled, so that
others can mirror the source from this IRRd instance too.

Updates will be retrieved every `import_timer`, and IRRd will automatically
perform a full import the first time, and then use NRTMv3 for updates.

Even in sources that normally use NRTMv3, IRRd can run a full new import of the
database. This may be needed if the NRTMv3 stream has gotten so far behind that
the updates IRRd needs are no longer available. To start a full reload,
use the ``irrd_mirror_force_reload`` command. For example, to force a full
reload for the ``MIRROR-EXAMPLE`` source::

    irrd_mirror_force_reload --config /etc/irrd.yaml MIRROR-EXAMPLE

The config parameter is optional. The reload will start the next time
`import_timer` expires. After the reload, IRRd will resume mirroring from
the NRTMv3 stream.

Note that any instances mirroring from your instance (i.e. your IRRd is
mirroring a source, a third party mirrors this from your instance), will also
have to do a full reload, as the journal for NRTM queries is purged when
doing a full reload.

Periodic full imports
~~~~~~~~~~~~~~~~~~~~~
For sources that do not offer NRTM, simply configuring a source of the data in
`import_source` will make IRRd perform a new full import, every `import_timer`.
Journals can not be generated, and NRTM queries by clients for this source will
be rejected.

When `import_serial_source`, is set, a full import will only be run if the
serial in that file is greater than the highest imported serial so far.
The serial is checked every `import_timer`.

Downloads
~~~~~~~~~
For downloads, FTP and local files are supported. The full copy to be
imported can consist of one or multiple files.

Validation and filtering
~~~~~~~~~~~~~~~~~~~~~~~~
Regardless of mode, all objects received from mirrors are processed with
:doc:`non-strict object validation </admins/object-validation>`. Any objects
that are rejected, are logged at the `CRITICAL` level, as they cause a data
inconsistency between the original source and the mirror.

The mirror can be limited to certain RPSL object classes using the
`object_class_filter` setting. Any objects encountered that are not included
in this list, are immediately discarded. No logs are kept of this. They
are also not kept in the local journal.
If this setting is undefined, all known classes are accepted.

.. _mirroring-nrtm-serials:

Serial handling
~~~~~~~~~~~~~~~
When using NRTMv3 mirroring, the local IRRd journal for each source, if enabled,
can operate in two modes: synchronised serials, or local serials.

In local serial mode, the local journal may have different serials for the same
changes, than the serials provided by the original source. Each IRRd instance
that mirrors from the same original source, may have a different set of serials
for the same changes.

In synchronised serial mode, the local IRRd journal has the same serial for
each change as the original NRTMv3 source. Serials of NRTMv3 operations that are
filtered out by the object class filter are skipped.

IRRd automatically uses synchronised serials for a source if these conditions
are all true:

* :doc:`RPKI-aware mode </admins/rpki>` is disabled, or
  ``sources.{name}.rpki_excluded`` is set for the source, and this
  has been the case since the last full reload.
* The :doc:`scopefilter </admins/scopefilter>` is disabled, or
  ``sources.{name}.scopefilter_excluded`` is set for the source,
  and this has been the case since the last full reload.
* :doc:`Route object preference </admins/route-object-preference>` is not
  enabled for the source.
  and this has been the case since the last full reload.
* The ``sources.{name}.nrtm_host`` setting is set for the source.

In all other circumstances, IRRd uses local serials. This is necessary because
object suppression can cause IRRd to generate local
journal entries, causing the serials to run out of sync.

When users change their NRTMv3 source to a different one when using local serials,
they should reload the entire database from that source, not just resume NRTMv3
streaming. Simply changing the NRTMv3 host may lead to missing data.

If you disable all object suppression (RPKI, scope filter and route object
preference) for a source or your
whole IRRd instance, but they were enabled previously, IRRd will keep
using local serials, because the local journal still contains entries
generated by these features. To enable synchronised serials in this case,
use the ``irrd_mirror_force_reload`` command, which resets the local
journal.

You can check whether a source is using synchronised serials with the
`!J` query.


Manually loading data
---------------------
IRRd also supports manually loading data. The primary use for this is a
scenario where an external system or script generate RPSL data, and
IRRd should serve that data. It can also be useful for testing.

It's somewhat different from typical mirroring, where the authority
for the data lies with a third party. For this reason, manual data loading
uses stricter validation as well.

There are two ways to use manual data loading:

* Calling the ``irrd_load_database`` command periodically. Each call will
  overwrite all data for a specific source, and erase existing journal
  entries.
* Calling the ``irrd_load_database`` command once, and then using the
  ``irrd_update_database`` command to update the state of the database.
  This may be slower, but will generate journal entries to support offering
  NRTMv3 mirroring services.

.. caution::
    This process is intended for data sources such as produced by scripts.
    The validation is quite strict, as in script output, an error in script
    execution is a likely cause for any issues in the data.
    To force a reload of a regular mirror that normally uses NRTMv3,
    use the ``irrd_mirror_force_reload`` command instead.
    Mixing manual data loading with the regular mirroring options documented
    above is not recommended.

Command usage
~~~~~~~~~~~~~
The ``irrd_load_database`` and ``irrd_update_database`` command work as follows:

* The command can be called, providing a name of a source and a path to
  the file to import. This file can not be gzipped.
* The source must already be in the config file, with empty settings
  otherwise if no other settings are needed. The source does not have to
  be authoritative.
* Upon encountering the first error, the process is aborted, and an error
  is printed to stdout. No records are made/changed in the database or in
  the logs, the previously existing objects will remain in the database.
  The exit status is 1.
* When no errors were encountered, the provided file is considered the new
  and current state for the source. Log messages are written about the
  result of the import. The exit status is 0. Nothing is written to stdout.
* An error means encountering an object that raises errors in
  :doc:`non-strict object validation </admins/object-validation>`,
  an object with an unknown object class, or an object for which
  the `source` attribute is inconsistent with the `--source` argument.
  Unknown object classes that start with ``*xx`` are silently ignored,
  as these are harmless artefacts from certain legacy IRRd versions.
* The object class filter configured, if any, is followed.
* Manual object loading and other mirroring settings can not be mixed
  for the same source. Both commands will return an error and exit with
  status 2 if ``import_source`` or ``import_serial_source`` are set for
  the provided source.

Serial handling
~~~~~~~~~~~~~~~
The ``irrd_load_database`` command can be passed a serial to set:

* If no serial is provided, and none has in the past, no serial is
  recorded. This is similar to sources that have ``import_source``
  set, but not ``import_serial_source``.
* If no serial is provided, but a serial has been provided in a past
  command, or through another mirroring process, the existing serial
  is kept.
* If a lower serial is provided than in a past import, the lower
  serial is recorded, but the existing data is still overwritten.
  This is not recommended.
* The data is always reloaded from the provided file regardless of
  whether a serial was provided, or what the provided serial is.

.. note::
    When other databases mirror the source being loaded,
    it is advisable to use incrementing serials, as they may use the
    CURRENTSERIAL file to determine whether to run a new import.

The ``irrd_update_database`` command automatically generates the correct
serials, as required for NRTMv3 support.

Examples
~~~~~~~~
For example, to load data for source TEST with serial 10::

    irrd_load_database --source TEST --serial 10 testv1.db

This command will replace all objects for source `TEST` with the contents of
``testv1.db``, and delete all journal entries.

To update the database from a new file::

    irrd_update_database --source TEST testv2.db

This command will update the objects for source `TEST` to match the contents
of `testv2.db`. Journal entries, available over NRTMv3, are generated for the
changes between ``testv1.db`` and ``testv2.db``.

The ``--config`` parameter can be used to read the configuration from a
different config file. Note that this script always acts on the current
configuration file - not on the configuration that IRRd started with.

.. caution::
    Each time ``irrd_load_database`` is called, all existing journal
    entries for the source are discarded, as they may no longer be complete.
    This breaks any ongoing NRTMv3 mirroring by third parties.
    This only applies if loading was successful.

Performance
~~~~~~~~~~~
The ``irrd_update_database`` command is one of the slower processes in IRRd,
due to the complexity of determining the changes between the data sets.
It is not intended for larger data sets, e.g. those over 150.000 objects.
