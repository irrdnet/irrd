=========================
Object validation in IRRd
=========================

In general, IRRd follows RFC 2622, 2650, 2726, 2725, 4012 and 2769.
However, most current IRR databases violate these RFCs in some
ways, meaning some flexibility is needed.

In addition to the validations as described below, IRRd supports
:doc:`object suppression </admins/object-suppression>` where objects are also
filtered or validated against ROAs, a scope filter, or other route objects.


General requirements
--------------------
The ``irrd.rpsl`` module deals with parsing and validation in general.
The general requirements for validation are:

* Any objects submitted to IRRd directly (i.e. not from mirrors)
  should always be entirely valid. If they are not, the end user
  can fix their object and continue from there.
* Many databases have some legacy objects which require more
  leniency with an initial import, but we aim to be as restrictive
  as reasonably possible. It should not be possible to update invalid
  authoritative objects without correcting their issues.
* Mirrors contain wildly variant objects, so IRRd performs the minimal
  level of validation needed to correctly index and query them.
* IRRd must never provide responses to any query, which
  are missing certain objects because indexed data could not be extracted
  from them, without logging errors about failing to import these objects.
* If objects are received from mirrors that can not be accepted, e.g.
  a route object with an invalid prefix, the object will be ignored and
  IRRd will record errors in the logs.


Validation modes
----------------
The parser/validator has two modes:

* **Non-strict**: includes validation of the presence of all primary key
  fields, and the correct syntax of all primary key and look-up fields.
  Object classes that are unknown are ignored. The syntax of an attribute
  name is validated, i.e. whether it contains valid characters only,
  but values are usually not validated.
* **Strict**: validates presence, count, and correct syntax of all fields.
  Validation fails on attributes that are not known, or object classes
  that are not known. Values of all fields are validated.
  Unknown object classes that start with ``*xx`` are silently ignored,
  as these are harmless artefacts from certain legacy IRRd versions.
  Strong references to other objects are enforced, like the reference
  to a `tech-c` from a `route` object.

In addition, the following validation changes to primary/lookup keys apply
in non-strict mode:

* RPSL names are allowed to contain reserved prefixes (e.g. RS-FOO as
  a maintainer name) and can be reserved words.
* In names for sets (route-set, as-set, etc.) reserved words, reserved
  words are allowed, and there is no requirement that at least one
  component starts with the actual prefix (RS-, AS-, etc.), so
  "AS123" or "FOOBAR" are accepted.

Non-strict mode is used for mirroring, because a significant number
of objects are not RFC-compliant, and some IRRs add custom fields
to their databases. For example, in non-strict mode, IRRd accepts a
``notify`` attribute that does not contain a valid e-mail address.
However, primary and look-up keys need to be indexed,
and therefore valid, as otherwise IRRd would give incomplete responses
to queries.

Other changes from RFCs:

* Trailing commas are permitted in lists, e.g. ``members: AS1, AS2,``.
  These are used on some occasions, and harmless to permit.
* RFC 2622 speaks of "sequence of ASCII characters" for free-form data.
  IRRd allows UTF-8 characters.
* In non-strict mode, `nic-hdl` attributes, and attributes that refer
  to them (`admin-c`, `tech-c`, `zone-c`) are allowed to contain any
  valid string, instead of being limited to an RPSL object name.
* Hierarchical objects, like `as-set` names, are limited to five
  components.
* IRRd does not accept prefixes with host bits set. RFCs are unclear
  on whether these are allowed.


Modifications to objects
------------------------
There are a few cases where IRRd makes changes to the object text.

Reformatting
^^^^^^^^^^^^
In all modes, values like prefixes are rewritten into a standard format.
If this results in changes compared to the original submitted text, the
parser will emit info messages, which are included in e.g. a report sent
to the submitter of a requested change.

rpki-ov-state
^^^^^^^^^^^^^
The ``rpki-ov-state`` attribute, which is used to indicate the
:doc:`RPKI validation status </admins/rpki>`, is always discarded from all
incoming objects. Where relevant, it is added to the output of queries.
This applies to authoritative and non-authoritative sources.
This attribute is not visible over NRTM and in exports.

key-cert objects
^^^^^^^^^^^^^^^^
In `key-cert` objects, the ``fingerpr`` and ``owner`` attributes are
updated to values extracted from the PGP key. The ``method`` attribute is
always set to PGP. This applies to objects from authoritative sources and
sources for which ``strict_import_keycert_objects`` is set.

.. _last-modified:

last-modified
^^^^^^^^^^^^^
For authoritative objects, the ``last-modified`` attribute is set when
the object is created or updated. Any existing ``last-modified`` values are
discarded. This timestamp is not updated for changes in object suppression
status. This attribute is visible over NRTM and in exports.

By default, this attribute is only added when an object is changed or
created. If you have upgraded to IRRd 4.1, you can use the
``irrd_set_last_modified_auth`` command to set it to the current time on
all existing authoritative objects.

This may take in the order of 10 minutes, depending
on the number of objects to be updated. This only needs to be done once.
It is safe to execute while other IRRd processes are running.
Journal entries are not created when running this command, i.e. the bulk
updates to ``last-modified`` are not visible over NRTM until the object
is updated for a different reason.
