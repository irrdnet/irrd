===============
Scope filtering
===============

IRRd supports a scope filter, where RPSL objects matching certain prefixes
and AS numbers can be filtered.

.. contents::
   :backlinks: none
   :local:

Enabling the scope filter
-------------------------
You can enable the scope filter by setting ``scopefilter.prefixes``
and/or ``scopefilter.asns``. See the
:doc:`configuration documentation </admins/configuration>` for their
exact syntax.

As soon as this is enabled and you (re)start IRRd or send a SIGHUP,
IRRd will check all RPSL in the database against the scope filter.

Query responses
---------------
By default, RPSL objects that are out of scope are not included in
in any query response.

To aid in debugging, it is possible to include out of scope objects in the
response. The filter can be disabled for a connection with the
``!fno-scope-filter`` command. The filter is
disabled only for ``!r`` queries and all RIPE style queries.

Objects that may be filtered
----------------------------
* A `route(6)` object is out of scope if the origin is out of scope,
  or the prefix overlaps with any out of scope prefix.
* An `aut-num` object is out of scope if its primary key is an out of
  scope ASN.
* Other object classes are never out of scope.

"Overlaps" for prefixes includes an exact match, less specific or more
specific of a prefix in ``scopefilter.prefixes``.

Where validation takes place
----------------------------
* IRRd validates all objects in the database against the scope filter on
  startup, and if the ``scopefilter`` setting is changed and a SIGHUP is sent.
* For each imported object from NRTM, periodic full imports, or manual data
  loading, IRRd sets the scope filter status using the current configuration,
  both on creations or changes.
* IRRd checks creation of objects in authoritative databases
  against the filter, and rejects the objects when they are out of scope.
  Updates and deletions are permitted.
* IRRd will always set objects from sources with
  ``sources.{name}.scopefilter_excluded`` as in scope,
  i.e. they are never regarded as out of scope objects at any time.
* Database exports and NRTM streams will not include out of scope
  objects. NRTM streams will include deletions.
* If the status of an object changes, due to a configuration change,
  an NRTM ADD or DEL is created in the journal.
* The scope filter also applies to
  :doc:`pseudo-IRR objects generated from ROAs </admins/rpki>`.

An example of validation in the context of mirroring: your IRRd
mirrors source DEMO from the authoritative source, you keep a local journal,
and a third party mirrors DEMO from you. When the authoritative source for
DEMO sends an NRTM ADD for an out of scope route, that update is not
recorded in your IRRd's local journal. The third party that mirrors from
you will not see this ADD over NRTM.

If you change the configuration later that results in the route being
in scope, an ADD is recorded in the local journal, and the third party
can pick up the change from an NRTM query to your IRRd. If that route becomes
out of scope again, causing the route to return to out of scope, a DEL is
recorded in your local journal.

Therefore, both the local state of your IRRd, and anyone mirroring from
your IRRd, will be up to date with the filter status.
This does not apply to excluded sources, whose objects are never seen
as out of scope.

.. note::
    When first enabling the scope filter, it may generate a significant amount
    of local journal entries, which are used to generate NRTM responses
    for anyone mirroring any source from your IRRd. Depending on the
    sources, there may be a few thousand NRTM updates.
