========
Database
========

.. caution::
   At this time, this is a plan for the database, and this
   may evolve as the project progresses and new insights are gained.

Requirements
------------

The database backend of IRRDv4 has to store sufficient metadata about
each object, to ensure it can be reconstructed as provided by the user
(except for intentional formatting changes).

A few fundamental types of queries can be distinguished:

* Direct searches on an RPSL primary key.
* Searches for objects where the PK contains or encloses a certain
  prefix, IP address or AS number.
* Resolving all members of a set, recursively.
* Inverse lookups, like finding all objects maintained by a certain
  mntner, or all objects where the tech-c is a certain person.
* Finding authorisation-related or contact objects for a given
  RPSL object.

As all data making up an RPSL object is stored in the database,
additional forms of indexing or additional lookup fields can
theoretically always be added on an existing database.

Database structure
------------------
The RPSL objects are stored in a single table, which records:

* `pk`: a random UUID, primary key of the table
* `rpsl_pk`: the primary key for the object, e.g. ``AS1 - AS200``
  for an as-block, or ``192.0.2.0/24,AS23456`` for a route object.
* `source`: the object's source attribute, e.g. ``NTTCOM``
* `object_class`: the RPSL object class, e.g. ``route6``
* `parsed_data`: a dict stored in JSONB, with all parsed attribute
  values. Comments are stripped, multiple lines and line continuation
  flattened to a single multi-line string.
  For fields like `members`, the value is recorded as a list,
  in most cases the value is a string.
  In non-strict mode (i.e. for mirrored databases) this only
  contains values for primary and lookup keys, as other attributes
  are not parsed.
* `object_txt`: the full text of the object as a single text.
* `ip_version`, `ip_first`, `ip_last`, `asn_first`, `asn_last`:
  a int / INET / int value describing which resources the objects refers
  to. For example, in a route with primary key ``192.0.2.0/24,AS23456``
  these columns would record: ``4``, ``192.0.2.0``, ``192.0.2.255``,
  ``23456``, ``23456``.

The columns `rpsl_pk` and `source` must be unique together.
The columns `pk`, `rpsl_pk`, `source`, `ip_version`, `ip_first`,
`ip_last`, `asn_first`, and `asn_last` are indexed. In addition,
all lookup keys in `parsed_data` are indexed, so the following query
uses an efficient index too::

    SELECT * FROM rpsl_objects where parsed_data->'mnt-by' ? 'MY-MNTNER';

When building queries using `ip_first` and `ip_last`, note that only
certain operations are `supported by the inet_ops index class`_
used for these columns - notably ``<`` and ``>`` can not use the index
on these columns and will result in a sequential scan.

.. _supported by the inet_ops index class:
   https://www.postgresql.org/docs/10/static/gist-builtin-opclasses.html

Updating the database
---------------------
The database uses alembic for migrations. If you make a change to
the database, run alembic to generate a migration::

    alembic revision --autogenerate -m "Short message"

The migrations are Python code, and should be reviewed after
generation - alembic is helpful but far from perfect.
The migration files also need to be in source control.

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
a hardcoded list of expected fields. If these are inconsistent, indexes may
be missing, and so IRRD will fail to start with the error:
`Field names of lookup fields do not match expected set. Indexes may be missing.`
Therefore, after creating your index, also add your field to
``expected_lookup_field_names``.

