=====================
Running whois queries
=====================

IRRd accepts whois queries on port 43 (by default).
The encoding used is always UTF-8, though many objects fit 7-bit ASCII.
Line seperators are a single newline (``\n``) character.

.. note::
   Due to caching in IRRd, it can take up to 60 seconds for some types
   of changes to be visible in the result of some queries.

.. contents:: :backlinks: none

IRRd vs RIPE style
------------------
IRRd supports two styles of queries:

* IRRd style queries, many of which return processed data
  rather than raw RPSL object text. For example,
  ``!iRS-EXAMPLE,1`` finds all members of route-set `RS-EXAMPLE`,
  recursively and returns them as a space-separated list of prefixes.
* RIPE style queries, which you may know from the RIPE whois database and many
  similar implementations. For example, ``-s APNIC -M 192.0.2/21`` finds
  all more specific objects of 192.0.2/21 from source APNIC.

The two styles can not be combined in a single query, but can be mixed in
a single connection.

IRRd style queries
------------------
* ``!!`` activates multiple command mode. The connection will be kept open
  after a query has been sent. Queries are answered in the order they were
  submitted. Takes no parameters. In deviation from all other queries,
  this query will return no response at all.
* ``!t<timeout>`` sets the timeout of the connection. The connection is closed when no activity on the connection has occurred for this many seconds and there are neither running queries nor queries in the pipeline. Valid values range from 1 to 1000. The default is 30 seconds.
* ``!a<as-set-name>`` recursively resolves an `as-set`, then resolves all
  combined unique prefixes originating from any of the ASes in the set. Returns
  both IPv4 and IPv6 prefixes. Can be filtered to either IPv4 or IPv6 with
  ``!a4`` and ``!a6``, e.g. ``!a6AS-EXAMPLE`` recursively resolves AS-EXAMPLE
  into ASes, and then returns all IPv6 prefixes originating from any of these
  ASes. Essentially, this is a combination of ``!i``, ``!g`` and/or ``!6``.
  However, the performance is much better than separate queries, as overhead
  is drastically reduced.
  *Note*: this type of query can take very long to run, due to the amount of
  information it retrieves. Queries may take several minutes to resolve, and
  return up to 10-20 MB of text. Ensure that your client will not time out
  in this period.
* ``!gAS<asn>`` finds all IPv4 routes for an origin AS. Only distinct
  prefixes of the routes are returned, seperated by spaces.
* ``!6AS<asn>`` finds all IPv6 routes for an origin AS. Only distinct
  prefixes of the routes are returned, seperated by spaces.
* ``!i<set-name>`` returns all members of an `as-set` or a `route-set`. If
  ``,1`` is appended, the search is performed recursively. Returns all members
  (and possibly names of other sets, if the search was not recursive),
  separated by spaces. For example:
  ``!iRS-EXAMPLE,1`` returns all members of `RS-EXAMPLE`, recursively.
  If a `route-set` has `as-sets` or AS number as members, the response includes
  the prefixes originating from that AS, or the ASes in that set.
  If the ``compatibility.ipv4_only_route_set_members`` setting is enabled,
  IPv6 prefixes will not be returned.
* ``!j`` returns the serial range for each source, along with the most
  recent export serial from this IRRd instance. The serial range concerns the
  lowest and highest serial number seen for this database. It is unrelated
  to the range available in the journal, if any (which is used for NRTM).
  For all sources, query ``!j-*``, for a specific source, query
  ``!jEXAMPLE-SOURCE``.
* ``!m<object-class>,<primary-key>`` searches for objects exactly matching
  the primary key, of the specified RPSL object class. For example:
  ``!maut-num,AS23456``. Stops at the first object. The key is case
  sensitive.
* ``!o<mntner-name>`` searches for all objects with the specified maintainer
  in its `mnt-by` attribute.
* ``!n<free-text>`` identifies the client querying IRRd. Optional, but may
  be helpful when debugging issues.
* ``!r<prefix>[,<option>]`` searches for `route` or `route6` objects. The options
  are:

  * no option, e.g. ``!r192.0.2.0/24``, to find exact matching objects and
    return them
  * ``o``, e.g. ``!r192.0.2.0/24,o``, to find exact matching objects, and
    return only the distinct origin ASes, separated by spaces
  * ``l``, e.g. ``!r192.0.2.0/24,l``, to find one level less specific objects,
    excluding exact matches, and return them
  * ``L``, e.g. ``!r192.0.2.0/24,L``, to find all level less specific objects,
    including exact matches, and return them
  * ``M``, e.g. ``!r192.0.2.0/24,M``, to find one level more specific objects,
    excluding exact matches, and return them
* ``!s<sources>`` restricts all responses to a specified list of sources,
  comma-separated, e.g. ``!sRIPE,NTTCOM``. In addition, ``!s-lc`` returns the
  sources currently selected. This persists across queries.
* ``!v`` returns the current version of IRRd
* ``!fno-rpki-filter`` disables filtering RPKI invalid routes. If
  :doc:`RPKI-aware mode is enabled </admins/rpki>`, `route(6)` objects that
  conflict with RPKI ROAs are not included in the output of any query by default.
  After using ``!fno-rpki-filter``, this filter is disabled for the remainder of
  the connection. Disabling the filter only applies to ``!r`` queries and
  all RIPE style queries.

Responses
^^^^^^^^^
For a succesful response returning data, the response is::

    A<length>
    <response content>
    C

The length is the number of bytes in the response, including the newline
immediately after the response content. Different objects are part of one
lock of response content, each object separated by a blank line.

If the query was valid, but no entries were found, the response is::

    C

If the query was valid, but the primary key queried for did not exist::

    D

If the query was invalid::

    F <error message>

A ``!!`` query will not return any response.

RIPE style queries
------------------
Unlike IRRd style queries, RIPE style queries can combine multiple
parameters in one line, e.g::

    -k -K -s ARIN -L 192.0.2.0/24

will activate keepalive mode, return only key fields, and then find all
less specific objects, from source ARIN.

The query::

    -V my-client -T as-set AS-EXAMPLE

will set the client name to `my-client` and return all as-sets named
`AS-EXAMPLE`.

Queries
^^^^^^^
* ``-l``, ``-L``, ``-M`` and ``-x`` search for `route` or `route6` objects.
  The differences are:

  * ``-x``, e.g. ``-x 192.0.2.0/24``, finds exact matching objects and
    returnss them
  * ``-l``, e.g. ``-l 192.0.2.0/24``, finds one level less specific objects,
    excluding exact matches, and returns them
  * ``-L``, e.g. ``-L 192.0.2.0/24``, finds all level less specific objects,
    including exact matches, and returns them
  * ``-M``, e.g. ``-M 192.0.2.0/24``, finds one level more specific objects,
    excluding exact matches, and returns them
* ``-i <attribute> <value>`` searches for objects where the attribute has this
  particular value. Only available for some fields. For example,
  ``-i origin AS23456`` finds all objects with an `origin` attribute set to
  `AS23456`. In attributes that contain multiple values, one of their values
  must match the value in the query. Note: ``!g`` and ``!6`` are much faster
  than ``-i origin``, as the former benefit from preloading. However, the
  ``-i`` queries are more flexible.
* ``-t <object-class>`` returns the template for a particular object class.
* ``-g`` returns an NRTM response, used for mirroring. See the
  :doc:`mirroring documentation </users/mirroring>`.
* Any other (part of) the query is interpreted as a free text search:

  * If the input is a valid AS number, the query will look for any matching
    `as-block`, `as-set` or `aut-num` objects.
  * If the input is a valid IP address or prefix, the query will look for
    any less specific matches of any object class.
  * Otherwise, the query will look for any exact case insensitive matches
    on the primary key of an object, or a `person` or `role` where their
    name includes the search string, case insensitive.

Supported flags
^^^^^^^^^^^^^^^
* ``-k`` activates keepalive mode. The connection will be kept open
  after a query has been sent. Queries are answered in the order they were
  submitted.
* ``-s <sources>`` and ``-a`` set the sources used for queries. ``-s``
  restricts all responses to a specified list of sources,
  comma-separated, e.g. ``-s RIPE,NTTCOM``. ``-a`` enables all sources.
  This persists across queries.
* ``-T <object-classes>`` restricts a query to certain object classes,
  comma-separated. This does not persist across queries.
* ``-K`` restricts the output to primary key fields and the `members` and
  `mp-members` attributes.
* ``-V <free-text>`` identifies the client querying IRRd. Optional, but may
  be helpful when debugging issues.

Flags are placed before the query, i.e. ``-s`` should precede ``-x``.

The ``-F`` and ``-r`` flags are accepted but ignored, as IRRd does not support
recursion.

Responses
^^^^^^^^^
For a succesful response returning data, the response is simply the object
data, with different objects separated by a blank line, followed by an
extra newline.

If the query was valid, but no entries were found, the response is::

    %  No entries found for the selected source(s).

If the query was invalid::

    %% <error message>

Source search order
-------------------
IRRd queries have a default set of sources enabled, which can be changed
with the ``!s`` command or the ``-s`` flag. When enabling multiple sources,
the order in whch they are listed defines their prioritisation, which can
make a significant difference in some queries. For example, ``!m`` will find
the first object with a given primary key, from the highest priority source
in which it was found.

The currently enabled sources and their priority can be seen with ``!s-lc``.

Data preloading and warmup time
-------------------------------
After startup, IRRd needs some time before certain queries can be answered.
The ``!g``, ``!6``, ``!a`` and in some cases ``!i`` queries use preloaded
data, which needs to be loaded before these queries can be answered.
If these queries are used before the preloading is complete, IRRd will
answer them after preloading has completed. The time this takes depends
on the load and speed of the server on which IRRd is deployed, and can
range between several seconds and one minute.

Once the initial preload is complete, updates to the database do not cause
delays in queries. However, they may cause queries to return responses
based on slightly outdated data, typically 5-15 seconds.
