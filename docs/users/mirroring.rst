===================
Mirroring with IRRd
===================

IRRd can mirror other sources, and offers mirroring services for
other users.

This page explains the processes and caveats involved in mirroring.
For details on all configuration options, see
the :doc:`configuration documentation </admins/configuration>`.

.. contents:: :backlinks: none

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
far, it may need to reimport the entire database to catch up.

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
others can mirror the source from this IRRd instance too. IRRd will record
changes in the journal with the same serial as the original source provided.

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


Manually loading data
---------------------

A third option is to manually load data. This can be useful while testing,
or when generating data files from scripts, as it provides direct feedback
on whether loading data was successful.

.. caution::
    This process is intended for data sources such as produced by scripts.
    The validation is quite strict, as in script output, an error in script
    execution is a likely cause for any issues in the data.
    To force a reload of a regular mirror that normally uses NRTM,
    use the ``irrd_mirror_force_reload`` command instead.

Manual loading uses the ``irrd_load_database`` command:

* The command can be called, providing a name of a source and a path to
  the file to import. This file can not be gzipped.
* The source must already be in the config file, with empty settings
  otherwise if no other settings are needed. The source does not have to
  be authoritative.
* Optionally, a serial number can be set. See the notes about serials below.
* Upon encountering the first error, the process is aborted, and an error
  is printed to stdout. No records are made/changed in the database or in
  the logs, the previously existing objects will remain in the database.
  The exit status is 1.
* When no errors were encountered, all objects for this source are replaced
  with those found in the import file. Log messages are written about the
  result of the import. The exit status is 0. Nothing is written to stdout.
* An error means encountering an object that raises errors in
  :doc:`non-strict object validation </admins/object-validation>`,
  an object with an unknown object class, or an object for which
  the `source` attribute is inconsistent with the `--source` argument.
  Unknown object classes that start with ``*xx`` are silently ignored,
  as these are harmless artifacts from certain legacy IRRd versions.
* The object class filter configured, if any, is followed.

On serials:

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
    Journals can not be kept of manually loaded sources.

For example, to load data for source TEST with serial 10::

    irrd_load_database --source TEST --serial 10 test.db

The ``--config`` parameter can be used to read the configuration from a
different config file. Note that this script always acts on the current
configuration file - not on the configuration that IRRd started with.

.. caution::
    Upon manually loading data, all existing journal entries for the
    source are discarded, as they may no longer be complete.
    This only applies if loading was successful.

