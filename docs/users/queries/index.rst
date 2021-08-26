IRRd query overview
===================

There are three ways to query data from IRRd:

* GraphQL queries over HTTPS
* Whois queries over HTTPS
* Whois queries over plain TCP sockets

The three methods are documented in detail on their own pages.

GraphQL over HTTPS
------------------
:doc:`GraphQL over HTTPS <graphql>` is the newest and most flexible query option.
It supports
complex RPSL queries that can combine any set of criteria and supports related
object queries, where you can explore the graph of IRR data.
RPSL attributes are returned in a structured format, which means you do not
need to parse RPSL objects in most cases.

GraphQL is a small query language on top of HTTPS. You will benefit from using
a specific GraphQL client library, but any HTTPS client library will work.
The query language is similar to JSON, the output is JSON.
For reduced latency you can make multiple queries with one request.
GraphQL is also where new expansions are most likely to be added.

If you are new to querying IRR data, this is the simplest place to start.
As queries are served over HTTPS, transport is encrypted and authenticated.

Whois queries over HTTPS
------------------------
:doc:`Whois queries <whois>`, in the form of ``!iAS-EXAMPLE,1`` or
``-i mnt-by DEMO-MNT``,
can be executed over a small HTTPS API.
This API offers exactly the same query functionality as whois queries over
plain TCP sockets, at a small performance cost. However, clients can use
any standard HTTPS client library.

The output can be RPSL object text, or space separated lists of items.
To extract RPSL attributes, you need to use your own RPSL parser.
As queries are served over HTTPS, transport is encrypted and authenticated.

Whois queries over plain TCP sockets
------------------------------------
:doc:`Whois queries <whois>` can also be executed over plain TCP sockets,
typically on
port 43. This is the most well known and traditional whois query method,
and used by many existing tools.

This method has the best performance, as raw TCP sockets have less
overhead. However, it provides no authentication or encryption, i.e.
there is no way to verify the server connection or the data,
and clients are more complex than for other methods.

The output can be RPSL object text, or space separated lists of items.
There are two different output formats, RIPE and IRRd, which both have
different ways of detecting the end of a response.
As these are raw TCP sockets, you will have to write your own client
that handles the two different output formats.
To extract RPSL attributes, you need to use your own RPSL parser.

.. _performance_prefix_queries:

Performance of prefix queries
-----------------------------
Queries for prefixes in IRRd aim to use the most efficient query execution.
Due to internal indexing considerations, prefix queries are much faster if
they do not include `inetnum` objects. The speed improvement can be in the
order of 100x.

High performance prefix queries are used when IRRd is sure that no
`inetnum` objects might need to be included in the response. It can
determine this when you:

* use the ``-t`` parameter in RIPE queries; or
* use type-specific queries like ``!r`` or ``-L``; or
* as the server admin, set ``compatibility.inetnum_search_disabled``.

Note that this is specific to `inetnum`, not `inet6num`.

Data preloading and warm-up time
--------------------------------
After startup, IRRd needs some time before certain queries can be answered.
Some queries use preloaded data, which needs to be loaded before these queries
can be answered. If these queries are used before the preloading is complete,
IRRd will answer them after preloading has completed. The time this takes depends
on the load and speed of the server on which IRRd is deployed, and can
range between several seconds and one minute.

This concerns the whois queries ``!g``, ``!6``, ``!a`` and in some cases ``!i``,
and the GraphQL queries ``asnPrefixes`` and ``asSetPrefixes``.

Once the initial preload is complete, updates to the database do not cause
delays in queries. However, they may cause queries to return responses
based on slightly outdated data, typically 15-60 seconds.
