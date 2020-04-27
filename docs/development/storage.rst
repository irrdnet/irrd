==============
Storage design
==============

This document lays out the storage backend behind IRRd, which facilitates
essentially all IRRd operations, and future expansions.
Migrations are used to create the initial database, and support future
changes.

PostgreSQL database structure
-----------------------------
The PostgreSQL database consists of a few tables:

* ``RPSLDatabaseObject`` / ``rpsl_objects``: stores current/live RPSL
  objects, i.e. those that would be considered in answers to queries.
  Heavily indexed to support a wide range of queries. Most object data is
  extracted and stored separately for complex queries.
* ``RPSLDatabaseJournal`` / ``rpsl_database_journal``: stores changes to
  RPSL objects, if the ``keep_journal`` setting is enabled for a source.
  This contains less processed information, although all information can
  be derived from the original RPSL text.
* ``RPSLDatabaseStatus`` / ``database_status``: stores status information
  on the different authoritative and mirrored sources. This includes which
  serial range is available in the journal, or the last import error.


RPSL objects
~~~~~~~~~~~~
The current RPSL objects are stored in a single table, `rpsl_objects`,
which records:

* `pk`: a random UUID, primary key of the table.
* `rpsl_pk`: the primary key for the object, e.g. ``AS1 - AS200``.
  for an as-block, or ``192.0.2.0/24AS23456`` for a route object.
* `source`: the object's source attribute, e.g. ``NTTCOM``.
* `object_class`: the RPSL object class, e.g. ``route6``.
* `parsed_data`: a dict stored in JSONB, with all parsed attribute
  values. Comments are stripped, multiple lines and line continuation
  flattened to a single multi-line string.
  For fields like `members`, the value is recorded as a list,
  in other cases the value is a string. This allows for queries like
  "all objects where `mnt-by` contains a certain value".
* `object_text`: the full text of the object as a single text.
* `ip_version`, `ip_first`, `ip_last`, `ip_size`, `prefix_length`,
  `asn_first`, `asn_last`: a int / INET / int value describing which
  resources the objects refers to. For example, in a route with primary
  key ``192.0.2.0/24AS23456`` these columns would record: ``4``,
  ``192.0.2.0``, ``192.0.2.255``, ``256``, ``24``, ``23456``, ``23456``.
  Note that `prefix_length` is only filled for `route(6)` objects.
* `rpki_status`: the RPKI status of this object, which can be valid,
  invalid or not_found. For objects other than `route(6)`, this is always
  not_found.
  When :doc:`RPKI-aware mode </admins/rpki>` is disabled, this is
  set to not_found for all objects.

The columns `rpsl_pk` and `source` must be unique together.
The columns `pk`, `rpsl_pk`, `source`, `ip_version`, `ip_first`,
`ip_last`, `asn_first`, `asn_last` and `rpki_status`  are indexed with
several kinds of indexes. In addition, all lookup keys in `parsed_data`
are indexed, so the following query uses an efficient index too::

    SELECT * FROM rpsl_objects where parsed_data->'mnt-by' ? 'MY-MNTNER';

When building queries using `ip_first` and `ip_last`, note that only
certain operations are `supported by the inet_ops index class`_
used for these columns.

When RPSL objects are updated, their record in this table is replaced
with the new information. Deletions of objects result in deletion from
this table. If enabled, records may be kept of this in the RPSL journal.

.. _supported by the inet_ops index class:
   https://www.postgresql.org/docs/10/static/gist-builtin-opclasses.html

RPSL journal
~~~~~~~~~~~~
The journal keeps changes to objects, which are used to provide
NRTM streams to other mirrors. It keeps much less extracted data.
Specifically, it records:

* `pk`: a random UUID, primary key of the table.
* `rpsl_pk`: the primary key for the object, e.g. ``AS1 - AS200``.
  for an as-block, or ``192.0.2.0/24AS23456`` for a route object.
* `source`: the object's source attribute, e.g. ``NTTCOM``.
* `origin`: the origin of the operation, i.e. what caused this change.
  Options are:
  * `UNKNOWN`: entry was created before origin field was added
  * `MIRROR`: change received from a mirror, over NRTM or by file import
  * `SYNTHETIC_NRTM`: change derived from synthesised NRTM
  * `PSEUDO_IRR`: change derived from changes to pseudo-IRR objects
  * `AUTH_CHANGE`: change made by a user of an authoritative database
  * `RPKI_STATUS`: change triggered by a change in RPKI status
  * `BOGON_STATUS`: change triggered by a change in bogon status
* `serial_nrtm`: the local NRTM serial of this change.
* `operation`: the type of NRTM operation, either ADD (object was added or
  updated), or DEL (object was deleted).
* `object_class`: the RPSL object class, e.g. ``route6``.
* `object_text`: the full text of the object as a single text.

The columns `serial_nrtm` and `source` must be unique together.

Note that the journal is updated up to and including the current state
of the RPSL objects table. When a new object is created, an ADD operation
is stored in the journal, and a new row is created in the RPSL objects
table. In other words, the journal does not only contain historic objects,
but also current/live ones.

RPSL database status
~~~~~~~~~~~~~~~~~~~~
For each source, a record is kept of:

* `pk`: a random UUID, primary key of the table.
* `source`: the name of the database.
* `serial_oldest_seen`, `serial_newest_seen`: the oldest/newest serial seen
  by IRRd, since the last full import of the database.
* `serial_oldest_journal`, `serial_newest_journal`: the oldest/newest serial
  recorded in the local RPSL journal.
* `serial_last_export`: the serial at which the database was last exported.
* `serial_newest_mirror`: the last serial seen from an NRTM mirror, i.e.
  NRTM queries to the mirror are resumed from the serial.
* `force_reload`: flag that can be set by an admin to force an full re-import
  of a mirrored source. This will be performed at the next update for this mirror.
  The flag will automatically be set back to false.
* `last_error`, `last_error_timestamp`: the last error that occurred on
  NRTM or file imports for this source, and when it occurred. All errors are
  also logged in the IRRd logfile.

The difference between `serial_newest_mirror` and `serial_newest_journal` is
that the former refers to the serial numbers in the remote mirror's journal,
and the latter refers to the local journal. These may be different, e.g. due
to changes in RPKI status.

.. note::
    There is no guarantee that all NRTM operations between
    `serial_oldest_journal` and `serial_newest_journal` are actually in the
    journal. In NRTM, serials may have gaps, and there it's not
    possible to verify whether any operations are missing.

.. danger::
    Setting `force_reload` will discard the entire local journal and all
    local data for this source, and then start a new import from the URLs
    in the configuration. If others mirror the reloaded source from this
    IRRd instance, they will also have to discard their local data and
    re-import, as the journal used for NRTM queries will be reset.


ROAs
~~~~
When :doc:`RPKI-aware mode </admins/rpki>` mode is enabled, the `roa_object`
table is loaded with ROAs. These are periodically reloaded, and the copy
in the database is used when processing change requests from users, NRTM
updates and full mirror imports.

* `pk`: a random UUID, primary key of the table.
* `prefix`: the prefix of the ROA
* `asn`: the valid origin AS recorded in the ROA (can be zero)
* `max_length`: the max prefix length the ROA allows
* `trust_anchor`: the trust anchor for the ROA (free text)
* `ip_version`: the IP version of `prefix`.

The fields `prefix`, `asn`, `max_length` and `trust_anchor`
must be unique together.


Updating the database
---------------------
The database uses alembic for migrations. If you make a change to
the database, run alembic to generate a migration::

    alembic revision --autogenerate -m "Short message"

The migrations are Python code, and should be reviewed after
generation - alembic is helpful but far from perfect.
The migration files also need to be in source control.
Alembic keeps state of which migrations have been run on a particular
database in the `alembic_version` table.

To upgrade or initialise a database to the latest version, run::

    alembic upgrade head

A special exception is the addition of new lookup fields (or marking
existing fields as lookup fields). These indexes are too complicated
for alembic to handle, and so you need to write additional manual
migrations for them. For example, if you want to add a lookup field
named ``country``, you'd add this to ``upgrade()``::

    op.create_index(op.f('ix_rpsl_objects_parsed_data_country'), 'rpsl_objects', [sa.text("((parsed_data->'country'))")], unique=False, postgresql_using='gin')

And this to ``downgrade()``::

    op.drop_index(op.f('ix_rpsl_objects_parsed_data_country'), table_name='rpsl_objects')

Note that the indexes are not differentiated by RPSL object class.

To remind you to do this, ``irrd.db.models`` asks ``irrd.rpsl.rpsl_objects``
for the current set of lookup fields upon initialisation, and compares it to
a hard-coded list of expected fields. If these are inconsistent, indexes may
be missing, and so IRRd will fail to start with the error:
`Field names of lookup fields do not match expected set. Indexes may be missing.`

Therefore, after creating your index, you need to **both**:

    * add an alembic migration that adds/removes your index
    * add your field to ``expected_lookup_field_names`` in ``irrd.db.models``

