===================
Mirroring with IRRd
===================

IRRd can mirror other sources, and offers mirroring services for
other users.

This page explains the processes and caveats involved in mirroring.
For details on all configuration options, see
the :doc:`configuration documentation </admins/configuration>`.

Mirroring services for others
-----------------------------

IRRd can produce periodic exports and generate NRTM responses to support
mirroring of authoritative or mirrored data by other users.

Periodic exports of the database can be produced for all sources. They consist
of a full export of the text of all objects for a source, gzipped and encoded
in UTF-8. Each source can have a different schedule for exports.

NRTM responses can be generated for all sources that have `keep_journal`
enabled, as the NRTM response is based on the journal, which records change
to objects. This can be kept for both authoritative sources and mirrors.

Generally, the files exported to `export_destination` are published over FTP
to allow mirrors to load all initial data. After that, NRTM requests can be made
to receive recent changes. If a mirroring client lags behind too far, it may
need to reimport the entire database to catch up.

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

In NRTM version 1, serials for individual operations (on the `ADD`/`DEL` lines are ommitted.

.. caution::
    NRTM version 1 can be ambiguous when there are gaps in NRTM serials. These
    can occur in a variety of situations. It is strongly recommended to always
    use NRTM version 3.

For authoritative databases in IRRd, serials are guaranteed to be sequential
without any gaps. However, various other scenarios can result in gaps in
serials from mirrored databases.


Mirroring other databases
-------------------------

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
A new full import can be forced by setting `force_reload` in the SQL database,
which will also discard the entire local journal.

Periodic full imports
~~~~~~~~~~~~~~~~~~~~~
For sources that do not offer NRTM, simply configuring a source of the data in
`import_source` will make IRRd perform a new full import, every `import_timer`.
Journals can not be generated, NRTM queries by clients for this source will be rejected.

Scheduling and downloads
~~~~~~~~~~~~~~~~~~~~~~~~
The mirror update frequency for each source can be changed with the
`import_timer` setting. A global scheduler runs every 15 seconds, and starts
the mirror updates whose timer has expired. This means the granularity and
minimum frequency are both 15 seconds.

If a previously scheduled update is still running, the next run is delayed
until the current run is finished. This occurs, for example, during the
initial large full import for a source in NRTM mode, where `import_timer`
is usually kept low/default to frequently process NRTM updates.

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
