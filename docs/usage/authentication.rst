=============================
Authentication & notification
=============================

IRRd performs authentication when users submit changes, using `mntner`
objects referred by `mnt-by` attributes.
Additionally, notifications may be sent on attempted or successful changes.

Object maintainers and parent maintainers
-----------------------------------------

In authentication, there are two sets of maintainers to consider:

* Maintainers referred by the affected object itself. In case
  of updates to existing objects, this refers to both the existing
  object maintainers, and the maintainers in the newly submitted version.
* Maintainers of parent objects. These do not apply for all RPSL
  object classes. This applies, for example, to `route` objects:
  the parent maintainers are the maintainers of the first level
  less specific `route` object plus the maintainers of the smallest
  overlapping `inetnum` object.

Parent maintainers are found in the following ways:

* `aut-num`: the `as-block` that contains this AS number
* `as-set`, `filter-set`, `peering-set`, `route-set`, `rtr-set`:
  if the name of the set contains more than one component, e.g.
  ``AS65536:RS-EXAMPLE``: the `aut-num` or other set name that this set is
  hierarchically placed under - in this example, `aut-num` ``AS65536``.
  In case of nested multi-component set names, like
  ``AS65536:RS-EXAMPLE:RS-EXAMPLE2``, the first parent object evaluated is
  ``AS65536:RS-EXAMPLE``, if that does not exist, the parent object is considered
  to be ``AS65536``.
* `domain`, `inetnum`, `inet6num`, `route`, `route6`: the smallest overlapping
  `inet(6)num` object
* `domain`: the first level less specific `domain` object
* `route`, `route6`: the first level less specific `route(6)` object

Where multiple rules apply, each rule must be met. When processing a set of
requested changes, parent maintainers are resolved based on existing entries
in the database. If no parent object exists, the parent authentication
step passes.

Special rules
-------------

There are a few additional special rules:

* Changes can only be made to authoritative databases.
* The override password overrides all other requirements in this document,
  except the authoritative database requirement. Notifications to maintainers
  or the address in the ``notify`` attribute are **not** sent when the override
  password was used.
* an `as-block` may not overlap with an existing `as-block`, even if
  authentication is provided for both blocks
* `mntner`, `person` and `role` can only be created if there are no existing
  (dangling) references to them

Authentication and notification overview
----------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Type of change
     - Authentication must pass
     - Notifications sent to
   * - Create, auth success
     - New object and parent objects
     -
       * ``mnt-nfy`` for all maintainers of new object and parent objects
       * report sent to the submitter of the change
   * - Create, auth fail
     - New object and parent objects
     -
       * ``upd-to`` for all maintainers of new object and parent objects
       * report sent to the submitter of the change
   * - Update or delete, auth success
     - Existing object and new object
     -
       * ``mnt-nfy`` for all maintainers of existing object and parent objects
       * ``notify`` attribute of the existing object
       * report sent to the submitter of the change
   * - Update or delete, auth fail
     - Existing object and new object
     -
       * ``upd-to`` for all maintainers of existing object and parent objects
       * ``notify`` attribute of the existing object
       * report sent to the submitter of the change
   * - Any change, syntax failure
     - ---
     -
       * report sent to the submitter of the change
       * no other notifications sent

"Authentication must pass" means that for each relevant object, at least one
auth method of at least one `mntner` referred by the relevant object
has passed.


Example
-------

* A user tries to create a `route` for ``192.0.2.0/29``, origin ``AS65536``.
* The following existing objects are in the database:

  * `inetnum` for ``192.0.2.0-192.0.2.1``
  * `inetnum` for ``192.0.2.0-192.0.2.255``
  * `route` for ``192.0.2.0/24``
  * `route` for ``192.0.2.0/32``
  * `aut-num` for ``AS65536``

In this case, authentication must pass for the `inetnum` for
``192.0.2.0-192.0.2.1``, the `route` for ``192.0.2.0/24``, and the maintainers
on the newly submitted object.
