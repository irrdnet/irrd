===================
Mirroring with IRRd
===================

IRRd can mirror other sources, and offers mirroring services for
other users.

This page explains the processes and caveats involved in mirroring.
For details on all configuration options, see
the :doc:`configuration documentation </admins/configuration>`.

.. note::
    If :doc:`RPKI-aware mode </admins/rpki>` is enabled, mirroring
    is also affected by RPKI validation. This is documented in
    the RPKI integration documentation.


Scheduling
----------

All mirroring processes, except answering NRTM queries, are run in a separate
thread for each source. The frequencies at which they run can be configured
for each source and for importing and exporting separately, but there are
default settings.

A global scheduler runs every 15 seconds, which will start mirror import and/or
export processes for every source for which the `import_timer` or `export_timer`
has expired. On startup, all mirror processes are started, as all their timers
are considered expired.

If a previously scheduled process is still running, no new process will be
run, until the current run for this source is finished and the timer
expires again. This means that, for example, when mirroring a source in NRTM
mode, `import_timer` can be safely kept low, even though the initial large
full import may take some time.


Mirroring services for others (exporting)
-----------------------------------------

IRRd can produce periodic exports and generate NRTM responses to support
mirroring of authoritative or mirrored data by other users.

Periodic exports of the database can be produced for all sources. They consist
of a full export of the text of all objects for a source, gzipped and encoded
in UTF-8. If a serial is known, another file is exported with the serial
number of this export. If the database is entirely empty, an error is logged
and no files are exported.

NRTM responses can be generated for all sources that have `keep_journal`
enabled, as the NRTM response is based on the journal, which records changes
to objects. A journal can be kept for both authoritative sources and mirrors.

In typical setups, the files exported to `export_destination` will be published
over FTP to allow mirrors to load all initial data. After that, NRTM requests
can be made to receive recent changes. If a mirroring client lags behind too
far, it may need to re-import the entire database to catch up.

The NRTM query format is::

    -g <source>:<version>:<serial start>-<serial end>

The version can be 1 or 3. The serial range included the starting and ending
serials. If the ending serial is ``LAST``, all changes from the starting serial
up to the most recent change will be sent. Admins can configure an access list
for NRTM queries. By default all NRTM requests are denied.

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

There are fundamentally two different modes to mirror other databases: NRTM mode
and periodic full imports. Regardless of mode, all updates are performed in a
single transaction. This means that, for example, when a full reload of a mirror
is performed, clients will keep seeing the old objects until the import is
entirely ready. Clients should never see half-finished imports.

NRTM mode
~~~~~~~~~
NRTM mode uses a download of a full copy of the database, followed by updating
the local data using NRTM queries. This requires a downloadable full copy,
the serial belonging to that copy, and NRTM access. This method is recommended,
as it is efficient and allows IRRd to generate a journal, if enabled, so that
others can mirror the source from this IRRd instance too.

Updates will be retrieved every `import_timer`, and IRRd will automatically
perform a full import the first time, and then use NRTM for updates.

Even in sources that normally use NRTM, IRRd can run a full new import of the
database. This may be needed if the NRTM stream has gotten so far behind that
the updates IRRd needs are no longer available. To start a full reload,
use the ``irrd_mirror_force_reload`` command. For example, to force a full
reload for the ``MIRROR-EXAMPLE`` source::

    irrd_mirror_force_reload --config /etc/irrd.yaml MIRROR-EXAMPLE

The config parameter is optional. The reload will start the next time
`import_timer` expires. After the reload, IRRd will resume mirroring from
the NRTM stream.

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
When using NRTM mirroring, the local IRRd journal for each source, if enabled,
can operate in two modes: synchronised serials, or local serials.

In local serial mode, the local journal may have different serials for the same
changes, than the serials provided by the original source. Each IRRd instance
that mirrors from the same original source, may have a different set of serials
for the same changes.

In synchronised serial mode, the local IRRd journal has the same serial for
each change as the original NRTM source. Serials of NRTM operations that are
filtered out by the object class filter are skipped.

IRRd automatically uses synchronised serials for a source if these conditions
are all true:

* :doc:`RPKI-aware mode </admins/rpki>` is disabled, or
  ``sources.{name}.rpki_excluded`` is set for the source, and this
  has been the case since the last full reload.
* The :doc:`scopefilter </admins/scopefilter>` is disabled, or
  ``sources.{name}.scopefilter_excluded`` is set for the source,
  and this has been the case since the last full reload.
* The ``sources.{name}.nrtm_host`` setting is set for the source.

In all other circumstances, IRRd uses local serials. This is necessary because
the scope filter and RPKI-aware mode can cause IRRd to generate local
journal entries, causing the serials to run out of sync.

When users change their NRTM source to a different one when using local serials,
they should reload the entire database from that source, not just resume NRTM
streaming. Simply changing the NRTM host may lead to missing data.

If you disable RPKI-aware mode and the scope filter for a source (or your
whole IRRd instance) that had them enabled previously, IRRd will keep
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
  NRTM mirroring services.

.. caution::
    This process is intended for data sources such as produced by scripts.
    The validation is quite strict, as in script output, an error in script
    execution is a likely cause for any issues in the data.
    To force a reload of a regular mirror that normally uses NRTM,
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
serials, as required for NRTM support.

Examples
~~~~~~~~
For example, to load data for source TEST with serial 10::

    irrd_load_database --source TEST --serial 10 testv1.db

This command will replace all objects for source `TEST` with the contents of
``testv1.db``, and delete all journal entries.

To update the database from a new file::

    irrd_update_database --source TEST testv2.db

This command will update the objects for source `TEST` to match the contents
of `testv2.db`. Journal entries, available over NRTM, are generated for the
changes between ``testv1.db`` and ``testv2.db``.

The ``--config`` parameter can be used to read the configuration from a
different config file. Note that this script always acts on the current
configuration file - not on the configuration that IRRd started with.

.. caution::
    Each time ``irrd_load_database`` is called, all existing journal
    entries for the source are discarded, as they may no longer be complete.
    This breaks any ongoing NRTM mirroring by third parties.
    This only applies if loading was successful.

Performance
~~~~~~~~~~~
The ``irrd_update_database`` command is one of the slower processes in IRRd,
due to the complexity of determining the changes between the data sets.
It is not intended for larger data sets, e.g. those over 150.000 objects.
