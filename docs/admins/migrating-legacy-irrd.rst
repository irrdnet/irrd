==========================
Migrating from legacy IRRd
==========================

There are a number of things to keep in mind when migrating from a legacy
(version < 4) IRRd instance to IRRd 4.

In general, there are many legacy IRRd versions out there. They come with
different versions of documentation, and are not all consistent with each
other or their own documentation.
Therefore, there may be an unknown number of unknown inconsistencies
between IRRd version 4 and a legacy version of IRRd. The significant
known changes are listed below.


Migrating existing data
-----------------------
To migrate data from a legacy IRRd instance, see option 1 documented in
:doc:`availability and data migration </admins/availability-and-migration>`.


Configuration and data storage
------------------------------
The configuration file is different, and some obsolete options have been
dropped. The new format of the configuration file is
:doc:`documented in detail </admins/configuration>`.
The RPSL data is now stored in an SQL database.


Whois query handling
--------------------
A sample of 230.000 queries from rr.ntt.net were executed against IRRd
version 4.0.0 and the 2.x version NTT was running at the time, with identical
data. Along with a number of solved bugs, this identified a number of cases where
legacy versions may currently provide different responses. Different responses
are primarily due to bugs in legacy IRRd, which do not occur in version 4.

* When searching for all prefixes with a 4-byte ASN as the origin, some
  results may be missing, because their origin in the RPSL object is
  encoded in ASDOT format, which is not supported.
* A handful of `route` objects from the RIPE database may be missing
  due to invalid Unicode characters, which legacy IRRd accepted
  (`GH #52 <https://github.com/irrdnet/irrd/issues/52>`_)
* Objects of various types have host bits enabled in prefixes, which
  is rejected by IRRd version 4. This may cause them to be missing from
  query responses.
  (`GH #62 <https://github.com/irrdnet/irrd/issues/62>`_)
* Various invalid query formats, like ``!i,AS-EXAMPLE`` or
  ``-i origin 65536`` were accepted by legacy IRRd, but are considered
  invalid in version 4.
* In ``!i`` set expansion queries, legacy IRRd does not consistently follow
  the source order prioritisation when resolving sets. This may cause
  unexpected empty responses or different responses, as set expansion can
  produce dramatic differences based on source order prioritisation.
  For example: ``AS-AKAMAI`` exists in RADB and RIPE, but the RADB object
  has no members. When the RADB source is prioritised, IRRd version 4
  correctly answers ``!iAS-AKAMAI`` with an empty response, but legacy
  IRRd refers to the RIPE object instead.
* Some ``!i`` set expansion queries return smaller results in version 4,
  because legacy IRRd incorrectly included the value(s) of the `mbrs-by-ref`
  attribute.
* Some legacy IRRd queries that returned a processed list of items, could
  contain a bogus comma and space at the start of the list. This does not
  occur in version 4.
* Masking of `auth` lines in `mntner` objects returned from queries has
  changed slightly.
* In some queries, less specific filters in legacy IRRd actually filtered for
  "exact match or less specific". This has been resolved in version 4, which
  may lead to smaller responses.
* Responses to queries like ``AS2914``, ``193/21`` or ``193.0.0.1`` include
  more objects in version 4, because version 4 includes less specific objects.
* Queries for `route6` objects may provide different results, because legacy
  IRRd allows multiple objects to exist with the same source and primary key,
  which are therefore all returned. IRRd version 4 ensures that this bug can
  not occur, and therefore will not return these duplicates. This particularly
  affected the ARIN-WHOIS and RPKI sources.
* Prefixes returned for ``!i`` queries on route sets may be different.
  By default, the response includes all IPv4 and IPv6 prefixes listed in
  `members`, `mp-members` and those referenced with `member-of`/`mbrs-by-ref`.
  In some legacy versions of IRRd, this would only return IPv4 prefixes,
  and also ignore IPv4 prefixes in `mp-members` attributes.
  Some compatibility with these versions is provided with the
  ``compatibility.ipv4_only_route_set_members`` setting, which will limit
  the response to only include IPv4 prefixes. However, this will also include
  IPv4 prefixes listed in `mp-members`. Therefore, responses may still differ.
* ``!i6`` queries are not supported, as they were partially broken in
  previous IRRd versions.


Other known changes
-------------------
* Some legacy IRRd versions supported `MAIL-FROM` authentication. This
  is considered an invalid authentication scheme in version 4,
  due to its poor security.
* When filtering objects from a mirror using `object_class_filter` /
  `irr_database <source> filter` legacy IRRd would not apply the filter
  consistently. In version 4, filtered objects are discarded immediately
  in the import parsing process, and not recorded in the database or any
  kind of exports.
