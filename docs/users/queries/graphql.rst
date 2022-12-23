==========================
Querying IRRd over GraphQL
==========================

IRRd has an HTTP interface which accepts GraphQL_ queries.

.. _GraphQL: https://graphql.org/
.. _introspected: https://graphql.org/learn/introspection/
.. _graphqurl: https://github.com/hasura/graphqurl
.. _clients listed on the GraphQL website: https://graphql.org/code/#graphql-clients
.. _awesome-graphql: https://github.com/chentsulin/awesome-graphql
.. _graphql-playground: https://github.com/graphql/graphql-playground
.. _GraphQL introduction: https://graphql.org/learn/
.. _inline fragment: https://graphql.org/learn/queries/#inline-fragments
.. _GraphQL types: https://graphql.org/learn/schema/#object-types-and-fields
.. _aliases: https://graphql.org/learn/queries/#aliases
.. _fragments: https://graphql.org/learn/queries/#fragments
.. _variables: https://graphql.org/learn/queries/#variables
.. _graphql-cli: https://github.com/Urigo/graphql-cli

Quick start
-----------
GraphQL runs on ``/graphql``. For example, if the IRRd instance
is running on ``rr.example.net``, you can find the GraphQL API on::

    https://rr.example.net/graphql

Opening this in a browser shows the GraphQL playground, which lets you
execute queries, like this::

    query {
      rpslObjects(asn: [65539, 65540]) {
        rpslPk
        objectClass
        source
        mntByObjs {
          objectText
        }
        ... on RPSLRoute {
          prefix
          rpkiStatus
        }
      }
    }

This query:

* Looks for RPSL objects that match either AS65539 or 65540.
* Retrieves the RPSL primary key, object class and source of all objects found.
* Retrieves the object text of all maintainers referred by each object.
* For RPSL route objects, also retrieves the prefix and RPKI status.

As the example shows, GraphQL lets you query individual attributes, which
means you don't have to parse RPSL yourself. You can also directly query
related objects. The output of GraphQL is always JSON.

You can use the "copy curl" button to copy a curl command line that runs the
same query. For more flexible use, use a dedicated GraphQL client like
`graphql-cli`_ or a HTTP or GraphQL client library.

The GraphQL playground has partial auto-complete to help you write your query,
and syntax validation.


Introduction to GraphQL
-----------------------
* GraphQL_ is a query language. Under the hood, queries are sent with an HTTP
  POST request, where the payload is the query in GraphQL language. This
  language is inspired by JSON.
* The response is always JSON data.
* GraphQL uses a schema that defines exactly which queries and responses exist.
  The schema can be introspected_. All query fields and response fields are
  defined in this schema, including their types. You can use the schema to learn
  exactly what queries you can run, and what responses can look like.
* Typically, you do not write the HTTP payloads yourself, but use a client
  library. There are several `clients listed on the GraphQL website`_, and
  the awesome-graphql_ repository has even more. However, any HTTP library
  will work.
* In GraphQL, you always specify exactly which fields you want the API to return.
  It uses camel case for names, so an RPSL attribute like ``tech-c`` will
  be referred to as ``techC`` in the GraphQL API.

Here's an example IRRd GraphQL query::

    query {
      rpslObjects(asn: [65539, 65540]) {
        rpslPk
        objectClass
        source
      }
    }

It retrieves all RPSL objects relating to ASN 65539 or 65540, and retrieves
their RPSL primary key, object class and source. The response to this is::

    {
      "data": {
        "rpslObjects": [
          {
            "rpslPk": "2001:db8::/38AS65540/ML64",
            "objectClass": "route6",
            "source": "RPKI"
          },
          ...
      }
    }

To help you in exploring the GraphQL interface, IRRd includes
graphql-playground_. This is a web interface that allows you to experiment
with GraphQL queries. It features partial auto-completion, though there are
some cases where this does not work, and lets you inspect the schema
(schema tab on the right).

IRRd queries
------------
IRRd supports a few different queries:

* ``databaseStatus`` to query the database status (similar to ``!J`` in whois).
* ``rpslObjects`` to retrieve RPSL objects.
* ``asnPrefixes`` to query prefixes originated by one or more ASNs
  (similar to ``!g/!6`` in whois).
* ``asSetPrefixes`` to query prefixes that are part of one or more AS sets
  (similar to ``!a`` in whois).
* ``recursiveSetMembers`` to recursively resolve the members of a
  route or AS set (similar to ``!i`` in whois).

Some of the latter queries could also be answered using a ``rpslObjects``
query. However, the specific purposes queries are much more efficient,
both in query execution and output format.

The GraphQL API only has few queries compared to whois, because the queries
themselves are much more flexible. Particularly, the ``rpslObjects`` query
is the most feature rich, allowing advanced and
complex queries on RPSL data. This document walks through the various
queries, explaining some basics of GraphQL along the way.

.. tip::
    This documentation will highlight some of the basics of GraphQL that
    are the most relevant for writing IRRd queries. However, you are
    recommended to read the `GraphQL introduction`_ which has much more
    detail on general GraphQL features.

Database status query
---------------------
The ``databaseStatus`` query returns the status of the various sources known
to IRRd. It is defined in the schema::

    type Query {
      databaseStatus(sources: [String!]): [DatabaseStatus]
      ...
    }

This means it takes one argument, sources, which is a array of non-null
strings - that is what the exclamation mark means. The array itself can be
empty or null, which also means the argument is optional.

It returns an array of ``DatabaseStatus`` GraphQL objects, which are also
defined in the schema::

    type DatabaseStatus {
      source: String!
      authoritative: Boolean!
      objectClassFilter: [String!]
      rpkiRovFilter: Boolean!
      scopefilterEnabled: Boolean!
      localJournalKept: Boolean!
      serialOldestJournal: Int
      serialNewestJournal: Int
      serialLastExport: Int
      serialNewestMirror: Int
      lastUpdate: String
      synchronisedSerials: Boolean!
    }

These are all the fields that can be queried, and their return types.

An example query that returns all current fields for all sources::

    query {
      databaseStatus {
        source
        authoritative
        objectClassFilter
        rpkiRovFilter
        scopefilterEnabled
        localJournalKept
        serialOldestJournal
        serialNewestJournal
        serialLastExport
        serialNewestMirror
        lastUpdate
        synchronisedSerials
      }
    }

Which might return::

    {
      "data": {
        "databaseStatus": [
          {
            "source": "NTTCOM",
            "authoritative": false,
            "objectClassFilter": null,
            "rpkiRovFilter": true,
            "scopefilterEnabled": true,
            "localJournalKept": true,
            "serialOldestJournal": 1,
            "serialNewestJournal": 177881,
            "serialLastExport": null,
            "serialNewestMirror": 1228527,
            "lastUpdate": "2020-09-26T15:22:13.977916+00:00",
            "synchronisedSerials": false
          }
        ]
      },
      ....
    }

You can also query for a specific source, or only certain fields::

    query {
      databaseStatus(sources: "NTTCOM") {
        source
        serialOldestJournal
        serialNewestJournal
        serialLastExport
      }
    }

Or a set of sources::

    query {
      databaseStatus(sources: ["NTTCOM", "RIPE"]) {
        ....
      }
    }

.. tip::
    In the schema, the sources argument is defined as ``[String!]``:
    an array of strings, where the elements can not be null, but the list is
    allowed to be empty. This means the argument is optional.
    However, if you pass a single string instead, the API
    will accept this as well. This works for all array types, i.e. those
    defined with ``[...]``.

The fields have the following meaning:

* ``source``: the name of the source
* ``authoritative``: true if this source is authoritative in this IRRd
  instance, i.e. whether local changes are allowed. False if the source
  is mirrored from elsewhere.
* ``objectClassFilter``: may be a list of object classes that are
  ignored by this IRRd instance, when mirroring from a remote source.
* ``rpkiRovFilter``: whether RPKI validation is enabled for this source.
* ``localJournalKept``: whether this IRRd instance keeps a local journal
  of the changes in this source, allowing it to be mirrored over NRTM.
* ``serialOldestJournal`` / ``serialNewestJournal``: the oldest and
  newest serials in the local journal on this IRRd instance for this source.
  IRRd does not guarantee that all changes in this range are available over
  NRTM. This serial range is entirely independent of that used by the
  mirror source, if any.
* ``serialLastExport``: the serial at which the last export for this
  source took place, if any.
* ``serialNewestMirror``: the newest serial seen from a mirroring source,
  i.e. the local IRRd has updated up to this serial number from the mirror.
  This number can be compared to the serials reported by the mirror
  directly, to see whether IRRd is up to date. This number is independent
  from the range in the local journal.
* ``lastUpdate``: the time of the last change to this source. This may be
  an authoritative change, an update from a mirror, a re-import, a change
  in the RPKI status of an object, or something else.
* ``synchronisedSerials``: whether or not a mirrored source is running with
  :ref:`synchronised serials <mirroring-nrtm-serials>`.

ASN prefixes query
------------------
This query queries the prefixes originated by one or more ASNs.
It's analogous to the ``!g`` and ``!6`` queries in whois.

The query is defined as::

    type Query {
      asnPrefixes(asns: [ASN!]!, ipVersion: Int, sources: [String!]): [ASNPrefixes!]
      ...
    }

It accepts three arguments:

* ``asns``: a not null and not empty array of ``ASN`` values, where
  each value must also be not null (hence the two exclamation marks).
* ``ipVersion``: a single integer, which is allowed to be null, and therefore
  can also be skipped. Valid values in IRRd are ``4`` or ``6``.
* ``sources``: an optional list of not null strings.

The return type is an array of ``ASNPrefixes`` objects, which is defined in
the schema as::

    type ASNPrefixes {
      asn: ASN!
      prefixes: [IP!]
    }

Each returned object will have one ``asn``, and a list of ``IP`` objects,
which are not null, but the list may be empty.

This query will return all prefixes originated by each ASN in ``asns``,
filtered by ``ipVersion`` if provided, filtered by objects from only the
sources in ``sources`` if provided.

An example query::

    query {
      asnPrefixes(asns: [25152, 3557]) {
        asn
        prefixes
      }
    }

For which the result is::

    {
      "data": {
        "asnPrefixes": [
          {
            "asn": 25152,
            "prefixes": [
              "2001:7fd:17::/48",
              "193.0.14.0/23",
              ...
            ]
          },
          {
            "asn": 3557,
            "prefixes": [
              "2001:500:6f::/48",
              "199.212.90.0/23",
              ...
            ]
          }
        ]
      }
    }

As the result shows, you can send one GraphQL query and get the results for
one or multiple ASNs, separated by ASN.

Recursive set members query
---------------------------
This query recursively resolves all members of an as-set or route-set
to their prefixes or AS numbers. It's analogous to ``!i`` in whois.

The GraphQL query definition is::

    type Query {
      recursiveSetMembers(
        setNames: [String!]!
        depth: Int
        sources: [String!]
        excludeSets: [String!]
        sqlTrace: Boolean
      ): [SetMembers!]
    }

The response type is::

    type SetMembers {
      rpslPk: String!
      rootSource: String!
      members: [String!]
    }

The query will recursively resolve all members of each name in ``setNames``,
and return the result for each resolved set separately.
You can also limit the recursion depth,
or exclude certain sets from consideration.

If there are multiple sets with the same name in different sources, this
query will return each of them along with their members, with a different
``rootSource``.

An example query::

    query {
      recursiveSetMembers(setNames: ["RS-KROOT-LINX"]) {
        rpslPk
        rootSource
        members
      }
    }

This query has a new argument, ``sqlTrace``, which is explained later on.

AS set prefixes query
---------------------
This query first recursively resolves all members an as-set
to AS numbers, and then returns the prefixes originated
by all ASNs in the as-set. It's basically a combination of
``recursiveSetMembers`` and ``asnPrefixes``, and is faster than
using these queries separately.
It's analogous to ``!a`` in whois.

The GraphQL query definition is::

    type Query {
      asSetPrefixes(
        setNames: [String!]!
        ipVersion: Int
        excludeSets: [String!]
        sources: [String!]
        sqlTrace: Boolean
      ): [AsSetPrefixes!]
      ...
    }

This query is very similar to the ASN prefixes query, except that you
provide one or more as-set names instead of ASNs.

The response type also looks very similar::

    type AsSetPrefixes {
      rpslPk: String!
      prefixes: [IP!]
    }

An example query::

    query {
      asSetPrefixes(setNames: ["AS-AKAMAI"]) {
        rpslPk
        prefixes
      }
    }

RPSL objects query
------------------
The ``rpslObjects`` query is the single query for RPSL objects.
It's very versatile, and replaces many whois queries.
Unlike other queries, it also supports resolving related objects.

Making a query
~~~~~~~~~~~~~~
The query is defined as follows::

    type Query {
      rpslObjects(
        person: [String!]
        adminC: [String!]
        mntBy: [String!]
        mpMembers: [String!]
        rpslPk: [String!]
        role: [String!]
        members: [String!]
        origin: [String!]
        mbrsByRef: [String!]
        objectClass: [String!]
        sources: [String!]
        zoneC: [String!]
        memberOf: [String!]
        techC: [String!]
        ipExact: IP
        ipLessSpecific: IP
        ipLessSpecificOneLevel: IP
        ipMoreSpecific: IP
        ipAny: IP
        asn: [ASN!]
        rpkiStatus: [RPKIStatus!]
        scopeFilterStatus: [ScopeFilterStatus!]
        routePreferenceStatus: [RoutePreferenceStatus!]
        textSearch: String
        recordLimit: Int
        sqlTrace: Boolean
      ): [RPSLObject!]
      ...
    }

The arguments you can query for include all lookup attributes of RPSL objects
in IRRd, like ``techC``, ``mntBy`` or ``members``. All arguments are optional,
but you must include at least one. Most arguments directly translate
to RPSL attributes. Note that not all objects have all attributes.

The other possible arguments for the query are:

* ``rpslPk``: filter on objects having one of these RPSL primary keys.
* ``sources``: filter on objects from one of these sources.
* ``objectClass``: filter on one of these RPSL object classes.
* ``ip...``: filter on exact match, less specific (including exact match),
  one level less specific, more specific, or any of those prefixes.
* ``asn``: filter on objects matching one of the provided ASNs.
* ``rpkiStatus``: filter on objects that have one of these RPKI validation
  statuses in the database. If omitted, the default is to filter on
  not_found and valid objects. Valid values are defined in the ``RPKIStatus``
  enum in the schema.
* ``scopeFilterStatus``: filter on objects that have one of these scope filter
  statuses in the database. If omitted, the default is to filter on
  in_scope objects. Valid values are defined in the ``ScopeFilterStatus``
  enum in the schema.
* ``routePreferenceStatus``: filter on objects that have one of these
  route preference statuses in the database.
  If omitted, the default is to filter on visible objects. Valid values are
  defined in the ``RoutePreferenceStatus`` enum in the schema.
* ``recordLimit``: limits the query to return this many results. Related
  object query results (explained in detail later) do not count towards
  this limit.

Most arguments expect an array, and this is interpreted as an OR query.
The separate arguments are joined as an AND query.
For example, this query::

    query {
      rpslObjects(
        members: "AS65540",
        mntBy: ["EXAMPLE1-MNT", "EXAMPLE2-MNT"]
        objectClass: ["as-set"]
      ) {
        rpslPk
        mntBy
        source
      }
    }

is evaluated as objects where:

* one of the members on the object matches ``AS65540``, AND
* one of the mnt-by's on the object matches ``EXAMPLE1-MNT`` OR ``EXAMPLE2-MNT``, AND
* the object class of the object is ``as-set``

Selecting fields of various RPSL objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In the schema definition of ``rpslObject`` above, the query returns an array
of ``RPSLObject``. The schema definition of this object is::

    interface RPSLObject {
      rpslPk: String
      objectClass: String
      objectText: String
      updated: String
      remarks: [String!]
      mntByObjs: [RPSLMntner!]
      mntBy: [String!]
      changed: [String!]
      notify: [String!]
      source: String
      journal: [RPSLJournalEntry]
    }

This is a mix of attributes that are common to every RPSL object known to
IRRd, like ``mntBy`` and ``notify``, combined with metadata like the
object class. ``objectText`` is the full plain RPSL text of the object.
The ``mntByObjs`` and ``journal`` fields are explained later.

Note that many of these fields return an array. This applies to all fields
that can occur multiple times, or contain multiple values. IRRd extracts
the individual values automatically.
For example, this value in an RPSL object::

    mnt-by: DEMO1-MNT, DEMO2-MNT
    mnt-by: DEMO3-MNT

Will appear in the query output as::

    "mntBy": [
      "DEMO1-MNT",
      "DEMO2-MNT",
      "DEMO3-MNT",
    ]

Class-specific fields
~~~~~~~~~~~~~~~~~~~~~
The example query in the last section queried for as-set objects. They
have a ``members`` attribute. You'd expect to be able to query::

    query {
      rpslObjects(
        members: "AS65540",
        mntBy: ["EXAMPLE1-MNT", "EXAMPLE2-MNT"]
        objectClass: ["as-set"]
      ) {
        rpslPk
        mntBy
        members
        source
      }
    }

However, this fails, with the following GraphQL error:
*"Cannot query field 'members' on type 'RPSLObject'. Did you mean to use an
inline fragment on 'RPSLAsSet', 'RPSLRouteSet', or 'RPSLRtrSet'?"*.

.. tip::
    GraphQL makes a decent effort at trying to determine what you were trying
    to query for, including issues like field misspellings.

``RPSLObject`` only contains the fields listed above, and not ``members``.
To query that, you need to inform GraphQL that you would like some fields
from the ``RPSLAsSet`` object, using an `inline fragment`_.
For this particular example::

    query {
      rpslObjects(
        members: "AS65540",
        mntBy: ["EXAMPLE1-MNT", "EXAMPLE2-MNT"]
        objectClass: ["as-set"]
      ) {
        rpslPk
        mntBy
        source
        ... on RPSLAsSet {
          members
        }
      }
    }

Now as-set objects that the query returns, include a ``members`` attribute.
Note that if you also expect ``RPSLRouteSet`` objects, that also have a
``members`` attribute, you need to specify them both::

    query {
      rpslObjects(mntBy: "EXAMPLE1-MNT") {
        rpslPk
        mntBy
        source
        ... on RPSLAsSet {
          members
        ... on RPSLRouteSet {
          members
        }
        }
      }
    }

You can query a different set of fields from each type of object.

The ``RPSL...`` objects are all defined in the GraphQL schema, and there is one
for each RPSL object class known to IRRd. You can see in the schema which
fields each of them has. Other than RPSL attributes, some objects have fields
like ``ipFirst``, ``prefix`` or ``asn``: they contain the extracted metadata
from that object and the IPs and/or ASN it relates to. For example, on an
``RPSLRoute`` you can retrieve the ``origin`` field to get ``"AS64512"``,
and the ``asn`` field to get ``64512``.

Related object queries
~~~~~~~~~~~~~~~~~~~~~~
RPSL object queries also support retrieving related objects, through special
fields, which all end in ``Objs``. Let's take the following query::

    query {
      rpslObjects(rpslPk: "AS-DEMO") {
        mntBy
      }
    }

Which returns::

    {
      "data": {
        "rpslObjects": [
          {
            "mntBy": [
              "EXAMPLE-MNT"
            ]
          }
        ]
      }
    }

Related object queries can be used to dig deeper into related objects, like
the maintainer. The ``mntBy`` field just retrieves the text in the ``mnt-by``
attribute, the ``mntByObjs`` field will try to retrieve the actual object,
from which you can then in turn query fields.

For example::

    query {
      rpslObjects(rpslPk: "AS-DEMO") {
        mntByObjs {
          rpslPk
          mntNfy
        }
      }
    }

Will return::

    {
      "data": {
        "rpslObjects": [
          {
            "mntByObjs": [
              {
                "rpslPk": "EXAMPLE-MNT",
                "mntNfy": [
                  "nfy@example.com"
                ]
              }
            ]
          }
        ]
      }
    }

This query has retrieved ``EXAMPLE-MNT``, then for each ``mnt-by``, looked
up the ``mntner`` object, and then retrieved the RPSL primary key and
``mnt-nfy`` attribute. In this case, you don't have to use an inline fragment
to retrieve fields specific to maintainers, because of how the ``mntByObjs``
field is defined in the schema::

    mntByObjs: [RPSLMntner!]

This means that the field will always produce an array of ``RPSLMntner``
objects, which have an ``mntNfy`` field in the schema. You can check the return
types of each ``...Objs`` field in the schema.

You can chain these related object retrievals as well::

    query {
      rpslObjects(rpslPk: "AS-DEMO") {
        ... on RPSLAsSet {
          membersObjs {
            membersObjs {
              rpslPk
              mntByObjs {
                notify
              }
            }
          }
        }
      }
    }


This query means:

* Retrieve the object with RPSL PK ``EXAMPLE-MNT``.
* Then, retrieve each member object from each returned as-set.
  (Note that only other as-sets are looked up by ``membersObjs`` on
  ``RPSLASSet``, i.e. AS numbers are ignored by ``membersObjs`` as they
  do not reference other objects.)
* Then, retrieve each member object from each of the member objects from
  the previous step.
* Then, for each member object from the previous step, retrieve the primary key
  and each maintainer object referred by each as-set retrieves in the previous step.
* For each maintainer, retrieve the notify attribute.

To see which ``...Objs`` queries exist on a GraphQL object, consult the schema.
This will also tell you what return type to expect. The GraphQL playground
can also help you with auto-complete.

.. warning::
    Each deeper layer can dramatically increase the number of database
    queries run. Therefore, there are limits to the use on large data sets.
    In general, for set resolving, use the specialised set resolving queries
    instead of ``rpslObject``, as their performance is orders of magnitude
    better.

There is one special case for retrieving ``admin-c`` and ``tech-c``
references. These are very common, and may return a ``RPSLPerson`` or
``RPSLRole``, and have nearly identical fields. If you are querying the
common fields between these objects, instead of writing::

    query {
      rpslObjects(rpslPk: "AS-DEMO") {
        ... on RPSLAsSet {
          adminCObjs {
            ... on RPSLPerson {
              phone
            }
            ... on RPSLRole {
              phone
            }
          }
        }
      }
    }

You can use the ``RPSLContact`` object::

    query {
      rpslObjects(rpslPk: "AS-DEMO", sqlTrace: true) {
        ... on RPSLAsSet {
          adminCObjs {
            ... on RPSLContact {
              phone
            }
          }
        }
      }
    }

.. note::
    The ``...Objs`` fields only return data for objects that were actually
    found in the database. For example, if an object has ``mnt-by`` set to
    ``DEMO-MNT``, but that maintainer does not exist, or does not exist in
    the local IRRd database because it was not mirrored, ``mntBy`` will show
    the reference to ``DEMO-MNT``, but ``mntByObjs`` will be empty.

.. _graphql-journal:

Journal queries
~~~~~~~~~~~~~~~
``RPSLObject`` also has a field ``journal``, which returns an array of
``RPSLJournal`` objects. This allows you to query the history of objects
as seen in the local IRRd database. This is the same journal that is used
for serving NRTM queries. This feature may be restricted by
the IRRd instance administrator. An example::

    query {
      rpslObjects(asn: 64512) {
        rpslPk
        journal {
          origin
          operation
          serialNrtm
          timestamp
        }
      }
    }

Might return::

    {
      "data": {
          {
            "rpslPk": "AS64512",
            "journal": [
              {
                "origin": "mirror",
                "operation": "add_or_update",
                "serialNrtm": 48768744,
                "timestamp": "2020-09-16 10:31:29.524289+02:00"
              }
            ]
          }
        ]
      }
    }

This means one change was recorded. Note that the journal only contains
what the local IRRd database has seen, so this is not a complete history.

``RPSLJournalEntry`` has fewer fields than ``RPSLObject``, because limited
metadata is kept in the journal. Worth noting are the fields:

* ``operation``: either ``add_or_update`` or ``delete``. This translates to
  the operations known in NRTM.

* ``origin``: the reason this change was recorded. Values include:

  * ``unknown``: made before IRRd recorded the origin
  * ``mirror``: received from a mirror by NRTM or a file import
  * ``synthetic_nrtm``: generated through synthetic NRTM
  * ``pseudo_irr``: generated from pseudo-IRR objects created for RPKI
  * ``auth_change``: generated from an authoritative user-submitted change
  * ``rpki_status``: generated because the :doc:`RPKI status </admins/rpki>`
    of the object changed
  * ``scope_filter``: generated because the
    :doc:`scopefilter status </admins/scopefilter>` of the object changed
* ``serialNrtm``: the local serial of this change.

Custom types in IRRd
--------------------
Most queries use the built-in `GraphQL types`_, like ``String`` or ``Int``.
IRRd has a few custom types for specific purposes:

* The ``ASN`` scalar. This is presented and validated as an integer, but
  GraphQL's built-in ``Int`` type is 32-bit signed, and therefore not
  sufficient.
* The ``IP`` scalar. This is presented as a string. When used in query
  arguments, the value is validated to be a valid IP address or prefix.
* The enums ``RPKIStatus``, ``ScopeFilterStatus``, and ``RoutePreferenceStatus``
  for querying and returning these statuses on RPSL objects.

Tips
----
* The fields you can query in ``rpslObjects`` only include fields IRRd knows
  about. For example, ``sponsoring-org`` is a RIPE-specific field, and not
  processed by IRRd. Therefore, you can't query it as a field. It will be
  included in the ``objectText`` field.
* You can run multiple queries in one request. The ``asnPrefixes``,
  ``asSetPrefixes`` and ``recursiveSetMembers`` already support retrieving
  for multiple ASNs/sets in one query. However, you can send multiple
  queries of any type in one request, with different parameters, using
  aliases_. This reduces latency.
* Many queries will be based on user input. Composing a string to embed
  the query arguments is frowned upon in GraphQL. You can use variables_
  to work with user input.
* If you end up with repetition in your queries, you can use fragments_
  to reuse the common parts.

SQL tracing
-----------
Several queries accept an optional ``sqlTrace`` argument. Setting this
to ``true`` enables SQL tracing. This means that IRRd will record all
SQL queries made during the execution of this query, and return them in
the output. The main purpose is to allow debugging by IRRd developers,
but there may be cases where it can help you understand how a GraphQL
query is being executed.

SQL tracing has a significant performance impact, and increases the size
of the result, so this should generally not be enabled.
