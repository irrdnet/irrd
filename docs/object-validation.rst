=====================
Validation of objects
=====================

In general, IRRD follows RFC 2622, 2650, 2726, 2725, 4012 and 2769.
However, a few deviations were needed from these standards.

The ``irrd.rpsl`` module deals with parsing and validation in general.
It has two modes:

* Non-strict: includes validation of the presence of all primary key
  fields, and the correct syntax of all primary key and look-up fields.
  Object classes that are unknown are ignored.
* Strict: validates presence, count, and correct syntax of all fields.
  Validation fails on attributes that are not known, or object classes
  that are not known.

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
for example. Primary and look-up keys need to be indexed, and therefore
those still need to be valid, or the parser needs to be more flexible
to handle certain invalid values as well.


Deviations from RFC or common practice
--------------------------------------

* Trailing commas are permitted in lists, e.g. ``members: AS1, AS2,``.
  These are used on some occasions, and harmless to permit.

