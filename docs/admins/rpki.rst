================
RPKI integration
================

IRRd can operate in RPKI-aware mode, where it imports ROA objects which
are used to validate `route(6)` objects. IRRd also generates pseudo-IRR
objects that represent ROA data.

.. contents:: :backlinks: none

Enabling RPKI-aware mode
------------------------
You can enable RPKI-aware mode by setting the ``rpki.roa_source`` setting
to a URL of a ROA export in JSON format.

As soon as this is enabled and IRRd is (re)started or a SIGHUP is sent,
IRRd will import the ROAs and mark any invalid existing `route(6)` as
such in the database.

Pseudo-IRR objects
------------------
IRRd creates a pseudo-IRR object for each ROA. These can be queried like
any other IRR object, and are included in the output of queries like
``!g``. Their source is set to ``RPKI``, and therefore it is invalid
to add a regular IRR source with that name, when RPKI-aware mode
is enabled. The ``RPKI`` source can be enabled or disabled like any
other source with ``!s`` and ``-s``, and can be included in the
``sources_default`` setting to be included in responses by default.

Query responses
---------------
By default, `route(6)` objects that conflict with a ROA are not included
in any query response. This is determined using
`RFC6811 origin validation <https://tools.ietf.org/html/rfc6811>` and
applies to all query types.

To include invalid objects in the response, this filter can be disabled
for a connection with the ``!fno-rpki-filter`` command. The filter is
disabled only for ``!r`` queries and all RIPE style queries.

Where validation takes place
----------------------------
* Every ``rpki.roa_import_timer``, IRRd reimports the ROA file, and then
  updates the validation status of all `route(6)` objects in the IRR database.
  This ensures that the status is correct when ROAs are added or removed.
* For each received NRTM update, IRRd sets the validation status using the
  current known ROAs, both on creations or changes.
* IRRd checks creation or modification of objects in authoritative databases
  against the ROAs, and rejects the objects when they are RPKI invalid.
* Deletions of RPKI invalid object are permitted, both for authoritative
  database and when receiving deletions over NRTM.
* IRRd will always set objects from sources listed in
  ``rpki.validation_excluded_sources`` to status not_found,
  i.e. they are never regarded as RPKI invalid objects at any time.
* Database exports and NRTM streams will not include RPKI invalid objects.
* If the validation state changes, e.g. due to a new ROA, an NRTM ADD
  or DEL is created in the journal.

An example of validation in the context of mirroring: your IRRd
mirrors source DEMO the authoritative source, you keep a local journal, and
a third party mirrors DEMO from you. When the authoritative source for
DEMO sends an NRTM ADD for an RPKI invalid route, that update is not
recorded in your IRRd's local journal. The third party that mirrors from
you will not see this ADD over NRTM.

If a ROA is added the next day that results in the route being RPKI valid
or not_found, an ADD is recorded in the local journal, and the third party
can pick up the change from an NRTM query to your IRRd. If that ROA is
deleted again, causing the route to return to RPKI invalid, a DEL is
recorded in the journal.

Therefore, both the local state of your IRRd, and anyone mirroring from
your IRRd, will be up to date with the RPKI status.
This does not apply to excluded sources, whose objects are never seen
as RPKI invalid.

First import with RPKI-aware mode
---------------------------------
When you first enable RPKI-aware mode, the import and validation process
will take considerably longer than on subsequent runs. On the first run,
a large number of objects in the database need to be updated, whereas this
number is much smaller on subsequent runs.
The first full import after changing ``rpki.validation_excluded_sources``
may also be slower, for the same reason.

Temporary inconsistencies
-------------------------
There are three situations that can cause temporary RPKI inconsistencies.

First, when you enable RPKI-aware modeand **at the same time** add a new source,
the objects for the new source may not have the correct RPKI status
initially. This happens because in the new source import process, no ROAs
are visible, and to the periodic ROA update, the objects in the new source
are not visible yet. This situation automatically resolves itself upon
the next periodic ROA update, but may cause objects that should be marked
RPKI-invalid to be included in responses in the mean time.
This issue only occurs when RPKI-aware mode is enabled for the first time,
and at the same time a new source is added. At other times, the RPKI
status of new sources will be correct.

Second, when someone adds a ROA and a `route` object in a mirrored source,
the ROA may not be imported by the time the `route` object is received
over NRTM. The object may initially be marked as RPKI not found, or, depending
on the ROA change, as invalid. This will be resolved at the next ROA import.

Third, when someone attempts to create a `route` object and has just created
or modified a ROA, the ROA may not have been imported yet. This can cause
the object to be initially marked as RPKI not found, or if the `route` is
RPKI invalid without the ROA change, rejected for being invalid. This will
be resolved at the next ROA import, allowing the user to create the `route`.
When a user attempts to create any `route` that is RPKI invalid, the error
messages includes a note of the configured ROA import time.

.. note::
    In IRRd logs, you may see things like ``RPKI status NOT_FOUND`` for objects
    for which RPKI validation does not apply, like `person` objects. This is
    intentional and not a bug, as IRRd uses this status for any object for
    which there is no RPKI information.
