===============================================
Important notes when migrating from legacy IRRd
===============================================

There are a number of things to keep in mind when migrating from a legacy
(version < 4) IRRd instance to IRRd 4.0.0.

In general, there are many legacy IRRd versions out there. They come with
different versions of documentation, and are not all consistent with each
other or their own documentation.
Therefore, there may be unknown inconsistencies between IRRd version 4 and
a legacy version of IRRd. The significant known changes that may affect
end users are in whois query handling.


Configuration and data storage
------------------------------
The configuration file is different, and some obsolete options have been
dropped. The new format of the configuration file is
:doc:`documented in detail </admins/configuration>`.

The RPSL data is now stored in an SQL database. The migration path for data
is covered in the
``TODO: link to deployment guide``
, but essentially comes down to performing
a fresh import of all data, while initially configuring your authoritative
databases as a simple mirror.


Whois query handling
--------------------
A sample of 230.000 queries from rr.ntt.net were executed against IRRd
version 4 and the version NTT was running at the time, with identical
data. Along with a number of solved bugs, this identified a number of cases where
legacy versions may currently provide different responses. Different responses
are primarily due to bugs in legacy IRRd, which do not occur in version 4.

* When searching for all prefixes with a 4-byte ASN as the origin, some
  results may be missing, because their origin in the RPSL object is
  encoded in ASDOT format, which is not supported.
* A handful of `route` objects from the RIPE database may be missing
  due to invalid unicode characters, which legacy IRRd accepted
  (`GH #52 <https://github.com/irrdnet/irrd4/issues/52>`_)
* Objects of various types have host bits enabled in prefixes, which
  is rejected by IRRd version 4. This may cause them to be missing from
  query responses.
  (`GH #62 <https://github.com/irrdnet/irrd4/issues/62>`_)
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

