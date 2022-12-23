===========================
Object suppression overview
===========================

IRRd supports three methods to suppress objects:

* :doc:`RPKI </admins/rpki>`, where IRRd suppresses objects that are
  invalid according to
  `RFC6811 origin validation <https://tools.ietf.org/html/rfc6811>`_.
  In addition, IRRd will create pseudo-IRR objects representing ROAs.
* The :doc:`scope filter </admins/scopefilter>`, which suppresses objects
  matching certain configured prefixes and/or AS numbers.
* The :doc:`route object preference </admins/route-object-preference>`,
  which suppresses objects that overlap with other route objects from
  sources with a higher preference.

Suppression is a kind of pseudo delete/create: IRRd will act as if the
object was deleted, but it may become visible again later.
One exception is that suppressed objects may still be deleted and can
still conflict on primary key.
Unlike normal deletions and creations,
this visibility change may have an external cause, e.g. a new ROA created
by the address space holder, or a change in scope filter configuration.
Suppression can also apply to objects for which the instance
is not authoritative.

When IRRd evaluates suppression
-------------------------------
* RPKI and route object preference periodically update the status for all
  relevant objects in the database. This resolves issues around temporary
  inconsistencies and, for RPKI, is also the moment when the local ROA
  storage is updated.
* For RPKI, this happens every ``rpki.roa_import_timer`` and for route object
  preference every ``route_object_preference.update_timer``.
  The scope filter updates all statuses on startup and then after any
  configuration change.
* When IRRd receives objects from mirrors, in full imports or over NRTM,
  the RPKI, scope filter and route preference status of these objects is updated.
* When users create an object for which the IRRd instance is authoritative,
  the scope filter and RPKI will reject creation of a suppressed object.

Scope of suppression
--------------------
Suppressed objects are not visible in the responses to queries,
database exports, NRTM streams, or the event stream.

To aid in debugging, it is possible to include suppressed objects in some
query responses. On whois queries, you can use the ``!fno-rpki-filter``,
``!fno-scope-filter``, and/or ``!fno-route-preference-filter`` commands.
The filter is then disabled only for ``!r`` queries and all RIPE style
queries. In GraphQL ``rpslObjects`` queries, you can pass a specific list of
``rpkiStatus``, ``scopeFilterStatus``, and/or ``routePreferenceStatus``
to include in the response.

Recording in the local journal
------------------------------
Object suppression is reflected in the journal so that mirrors from
the IRRd instance follow with the suppression. This means that
IRRd does not record an ADD for suppressed objects, and if an existing
object changes from visible to suppressed, IRRd records a DEL.
If an already suppressed object is deleted by the mirror source,
IRRd does not record any journal entry.

An example: your IRRd
mirrors source DEMO from the authoritative source, you keep a local journal, and
a third party mirrors DEMO from you. When the authoritative source for
DEMO sends an NRTM ADD for an RPKI invalid route, that update is not
recorded in your IRRd's local journal. The third party that mirrors from
you will not see this ADD over NRTM.

If a ROA is added the next day that results in the route being RPKI valid
or not_found, an ADD is recorded in the local journal, and the third party
can pick up the change from an NRTM query to your IRRd. If that ROA is
deleted again, causing the route to return to RPKI invalid, a DEL is
recorded in your local journal.

Therefore, both the local state of your IRRd, and anyone mirroring from
your IRRd, will be up to date with the RPKI status.

For route object preference, there are cases where IRRd records an ADD
and then immediately a DEL for the same object.

Interaction between suppression statuses
----------------------------------------
Each suppression status is independent, but for the visibility in
the journal and query responses, IRRd considers the combined state:
an object is suppressed if any of the suppression methods see it as
suppressed.

Following on the previous example: if along with the RPKI state,
the object is out of scope according to the scope filter, IRRd will
not generate an ADD in the journal at any point, and the object
will never be visible in query responses.

Important considerations when enabling
--------------------------------------
When you enable one of these features for the first time, the periodic
task will usually take considerably longer than on subsequent runs.
On the first run, a large number of objects in the database may need to
be updated, whereas this number is much smaller on subsequent runs.
The same may occur after changing settings, if these change a large number
of objects.

While the import and validation is running, processing other
database changes may be delayed.

These large status changes may also generate a significant amount
of local journal entries, which are used to generate NRTM responses
for anyone mirroring any source from your IRRd. Depending on the
sources, there may be in the order of 100K-1M journal entries.
NRTM is really not designed for this scale, and therefore it is
likely faster to have mirrors reload their copy.

Writing such huge numbers of changes to the journal also takes
considerable time.
If you are planning to require mirrors to reload their copies,
you may want to disable the ``keep_journal``
setting on one or more sources for the initial status update.
This speeds up the process dramatically, but means you must
make sure all mirrors reload their copy after you have re-enabled
the journal. Otherwise, they will desynchronise silently.

Temporary inconsistencies
-------------------------
There are a number situations that can cause temporary inconsistencies for
RPKI and route object preference, because multiple processes depend on
each other's state. These are usually small, and automatically resolved
on the next periodic update, which considers the state of the whole database.

For example:
when you enable RPKI-aware mode and **at the same time** add a new source,
the objects for the new source may not have the correct RPKI status
initially. This happens because in the new source import process, no ROAs
are visible, and to the periodic ROA update, the objects in the new source
are not visible yet. This situation automatically resolves itself upon
the next periodic ROA update, but may cause objects that should be marked
RPKI-invalid to be included in responses in the mean time.

Similarly: a case where two mirror imports with different route object
preferences run at the precise same time, and both include a `route` object
for there same prefix. IRRd will record both as visible, because neither
mirror process was able to see the other's object. This also resolves
on the next periodic full route object preference update.
Generally, the timing of these processes is slightly different, making
this a rare issue.
