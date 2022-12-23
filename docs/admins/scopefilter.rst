===============
Scope filtering
===============

IRRd supports a scope filter, where RPSL objects matching certain prefixes
and AS numbers can be suppressed.

.. note::
   This document only contains details specific to the scope filter, and is
   meant to complement the
   :doc:`object suppression overview </admins/object-suppression>`.

.. contents::
   :backlinks: none
   :local:

Configuring the scope filter
----------------------------
You can enable the scope filter by setting ``scopefilter.prefixes``
and/or ``scopefilter.asns``. See the
:doc:`configuration documentation </admins/configuration>` for their
exact syntax.

As soon as this is enabled and you (re)start IRRd or send a SIGHUP,
IRRd will check all objects in the database against the scope filter.

You can exclude sources by setting ``sources.{name}.scopefilter_excluded``.
Objects from these sources are always seen as in scope.

To disable the scope filter, set ``scopefilter_excluded`` for all sources
to reset the state of all objects to in scope. Once the periodic
import has updated the status for all objects, unset ``scopefilter.prefixes``
and ``scopefilter.asns`` to disable the update process.

Validation
----------
RPSL objects that are out of scope are suppressed:

* A `route(6)` object is out of scope if the origin is out of scope,
  or the prefix overlaps with any out of scope prefix.
* An `aut-num` object is out of scope if its primary key is an out of
  scope ASN.
* Other object classes are never out of scope.

"Overlaps" for prefixes includes an exact match, less specific or more
specific of a prefix in ``scopefilter.prefixes``.
