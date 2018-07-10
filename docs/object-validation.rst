=====================
Validation of objects
=====================

In general, IRRD follows RFC 2622, 2650, 2726, 2725, 4012 and 2769.
However, a few deviations were needed from these standards.

The ``irrd.rpsl`` module deals with parsing and validation in general.
The general requirements for validation are:

* Any objects submitted to IRRD directly (i.e. not from mirrors)
  should always be entirely valid. If they are not, the end user
  can fix their object and continue from there.
* The NTTCOM database has some legacy objects which require more
  leniency with an initial import, but we aim to be as restrictive
  as reasonably possible. It should not be possible to update invalid
  objects without correcting their issues.
* Mirrors contain wildly variant objects, so IRRD performs the minimal
  level of validation needed to correctly index and query them.
* Under no condition may IRRD provide responses to any query, which
  are missing certain objects because indexed data could not be extracted
  from them, without raising errors with the administrator.
* If objects are received from mirrors that can not be accepted, e.g.
  a route object with an invalid prefix, the object will be ignored and
  IRRD will raise errors with the administrator of the IRRD instance.

The parser/validator has two modes:

* Non-strict: includes validation of the presence of all primary key
  fields, and the correct syntax of all primary key and look-up fields.
  Object classes that are unknown are ignored. The syntax of an attribute
  name is validated, i.e. whether it contains valid characters only,
  but values are usually not validated.
* Strict: validates presence, count, and correct syntax of all fields.
  Validation fails on attributes that are not known, or object classes
  that are not known. Values of all fields are validated.

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
to their databases. So with non-strict mode, we don't care whether
a ``notify`` attribute actually contains a valid e-mail address,
for example. However, primary and look-up keys need to be indexed,
and therefore valid, as otherwise IRRD would give incomplete responses
to queries.


Notable deviations from RFC or common practice
----------------------------------------------

* Trailing commas are permitted in lists, e.g. ``members: AS1, AS2,``.
  These are used on some occasions, and harmless to permit.
* RFC 2622 speaks of "sequence of ASCII characters" for free-form data.
  IRRD allows UTF-8 characters.
* In non-strict mode, `nic-hdl` attributes, and attributes that refer
  to them (`admin-c`, `tech-c`, `zone-c`) are allowed to contain any
  valid string, instead of being limited to an RPSL object name.
