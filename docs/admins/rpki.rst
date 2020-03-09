================
RPKI integration
================

IRRd can operate in RPKI-aware mode, where it imports ROA objects which
are used to validate `route(6)` objects. IRRd also generates pseudo-IRR
objects that represent ROA data.

.. contents:: :backlinks: none

Enabling RPKI-aware mode
------------------------
RPKI-aware mode is enabled by setting the ``rpki.roa_source`` setting
to a URL of a ROA export in JSON format.

As soon as this is enabled and IRRd is (re)started or a SIGHUP is sent,
IRRd will import the ROAs and mark any invalid existing `route(6)` as
such in the database.

Pseudo-IRR objects
------------------
A pseudo-IRR object is created for each ROA. These can be queried like
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
* For each NRTM update, the validation status is set using the current
  known ROAs, both on creations or changes.
* Creation of objects in authoritative databases is checked
  against the ROAs, and rejected when they are invalid.
* Changes or deletions of RPKI-invalid object are permitted,
  but a warning will be issued to the user.
* Objects from sources listed in ``rpki.validation_excluded_sources`` are
  always set to status unknown.
* Database exports and NRTM streams always include all objects in the
  database, including RPKI invalid objects.

.. note::
    When RPKI-aware mode is first enabled, the import and validation process
    will take considerably longer than on subsequent runs. On the first run,
    a large number of objects in the database need to be updated, whereas this
    number is much smaller on subsequent runs.
    The first full import after changing ``rpki.validation_excluded_sources``
    may also be slower, for the same reason.

.. warning::
    When RPKI-aware mode is enabled and **at the same time** a new source is added,
    the objects for the new source may not have the correct RPKI status
    initially. This happens because in the new source import process, no ROAs
    are visible, and to the periodic ROA update, the objects in the new source
    are not visible yet. This situation automatically resolves itself upon
    the next periodic ROA update, but may cause objects that should be marked
    RPKI-invalid to be included in responses in the mean time.

    This issue only occurs when RPKI-aware mode is enabled for the first time,
    and at the same time a new source is added. At other times, the RPKI
    status of new sources will be correct.

