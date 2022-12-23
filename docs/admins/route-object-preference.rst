=======================
Route object preference
=======================

IRRd supports a route object preference, where `route(6)` objects can
be suppressed if they overlap with other `route(6)` objects from sources
with a higher route object preference.

.. note::
   This document only contains details specific to the filter, and is
   meant to complement the
   :doc:`object suppression overview </admins/object-suppression>`.

.. contents::
   :backlinks: none
   :local:

Configuring route object preference
-----------------------------------
You can enable route object preference by setting
``sources.{name}.route_object_preference`` on at least one source.
This is a number, where higher numbers have higher preference. See the
:doc:`configuration documentation </admins/configuration>` for the
exact syntax.

You can exclude sources by **not** setting
``sources.{name}.route_object_preference``.
Objects from these sources are always seen as visible.

To disable this feature, set ``route_object_preference`` for all sources
to the same preference to reset the state of all objects to visible.
Once the periodic
import has updated this, unset ``sources.{name}.route_object_preference``
for all sources to disable the update process.

Validation
----------
* In route object preference, each `route(6)` object is assigned a preference
  from its source's ``sources.{name}.route_object_preference`` setting.
* For the objects with a preference: if there is an overlapping
  `route(6)` object with a higher preference, the lower preference object
  is suppressed.
* Overlap means that the prefixes of the objects are an exact match, more
  specific, or less specific.
* If two overlapping objects have the same preference, both are visible
  (assuming there are no further overlaps).
* Origin ASes are not considered.
* Objects from sources without a preference setting are always visible and
  otherwise completely ignored in the validation process. They are also not
  included when considering suppression of other objects.

For example, let's say the preferences are: TEST-H1 and TEST-H2 at
priority 900, TEST-M at 200, TEST-L at 100, TEST-N with no preference,
and the following objects exist:

* A: TEST-H1 192.0.0.0/23 AS65530
* B: TEST-H2 192.0.0.0/24 AS65530
* C: TEST-L 192.0.0.0/23 AS65530
* D: TEST-M 192.0.0.0/22 AS65530
* E: TEST-M 192.0.1.0/24 AS65530
* F: TEST-L 192.0.3.0/24 AS65530
* G: TEST-N 192.0.0.0/22 AS65530

In this case objects C, D, E and F will be suppressed.
C, D and E all overlap directly with A and/or B, and A and B have a higher
preference than all others. A and B have an identical preference so their
objects will both be visible. Object F overlaps with object D, and object D
has a higher preference, therefore object F is also suppressed.
Object G remains visible and is otherwise ignored, as it has no
preference set, so it has no impact on the visibility of other objects.

Log messages and journal order
------------------------------
RPKI and scope filter status are determined per object,
shortly after parsing. Route preference status is rather difference:
it is determined for all affected prefixes just before committing.
This has some practical consequences that may lead to initially
confusing log messages or journal entries.

In RPKI and scope filter, the status of an object can be determined
by evaluating only that object, and the IRRd configuration and/or ROA table.
However, for route preference, an object's status depends on which
other objects exist in other sources. Also, uniquely, one object
being added or deleted, may cause the state of an entirely different
object to change, which was not part of the current change set.

When evaluating the status just before a transaction commit, IRRd
will log a line like:
`route preference updated for a subset of 15 added/removed/changed
routes: 2 regular objects made visible, 8 regular objects suppressed,
0 objects from excluded sources made visible`.
Important to note is that the 15 added/removed/changed routes do not
have to be the same objects as the 2 objects made visible, and the 8 made
suppressed. Similarly, processing NRTM changes from one source, may
lead to journal entries for objects of an entirely different source.
