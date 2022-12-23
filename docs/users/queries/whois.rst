=============
Whois queries
=============

IRRd accepts whois queries in two ways:

* Raw TCP sockets on (by default) port 43
* HTTPS requests


Making queries
--------------
HTTPS
^^^^^
To make whois queries over HTTPS, make a GET request to ``/v1/whois/``
with your query in the ``q`` parameter. For example, if the IRRd instance
is running on ``rr.example.net``, you can query ``!iAS-DEMO`` on::

    https://rr.example.net/v1/whois/?q=!iAS-DEMO

For some queries you may need to do URL encoding of the whois query,
but many libraries can do that for you if needed.

Raw TCP sockets
^^^^^^^^^^^^^^^
To query over raw TCP sockets, make a TCP connection to port 43 (by default)
and submit your query, ending with a single newline (``\n``).

IRRd vs RIPE style
------------------
IRRd supports two styles of queries:

* IRRd style queries, many of which return processed data
  rather than raw RPSL object text. For example,
  ``!iRS-EXAMPLE,1`` recursively finds all members of route-set `RS-EXAMPLE`,
  and returns them as a space-separated list of prefixes.
* RIPE style queries, which you may know from the RIPE whois database and many
  similar implementations. For example, ``-s APNIC -M 192.0.2/21`` finds
  all more specific objects of 192.0.2/21 from source APNIC.

The two styles can not be combined in a single query, but can be mixed in
a single TCP connection.

IRRd style queries
------------------
* ``!!`` activates multiple command mode for raw TCP sockets. The connection
  will be kept open after a query has been sent. Queries are answered in the
  order they were submitted. Takes no parameters. In deviation from all other
  queries, this query will return no response at all.
* ``!t<timeout>`` sets the timeout for a raw TCP connection.
  The connection is closed when no activity on the connection has occurred for
  this many seconds and there are neither running queries nor queries in the
  pipeline. Valid values range from 1 to 1000. The default is 30 seconds.
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
  prefixes of the routes are returned, separated by spaces.
* ``!6AS<asn>`` finds all IPv6 routes for an origin AS. Only distinct
  prefixes of the routes are returned, separated by spaces.
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
  recent export serial from this IRRd instance. This can be used to verify
  whether the local IRRd instance is up to date with a mirror. The lowest
  serial is always set to zero. The highest serial is the most recent
  serial imported from the mirror. The serial of the last export is based
  on the local serial, and may be in an entirely different range - IRRd uses
  its own set of serials, independent from serials used by mirrors.
  Usage of the ``!J`` command is strongly recommended over ``!j``.
  For all sources, query ``!j-*``, for a specific source, query
  ``!jEXAMPLE-SOURCE``.
* ``!J`` returns status information for each source. This can be used to check
  the mirroring status, which databases are authoritative, whether certain
  object classes are excluded, and various other settings.
  The query syntax is identical to ``!j``, the output is JSON data, with the
  following keys for each valid source:

  * ``authoritative``: true if this source is authoritative in this IRRd
    instance, i.e. whether local changes are allowed. False if the source
    is mirrored from elsewhere.
  * ``object_class_filter``: may be a list of object classes that are
    ignored by this IRRd instance, when mirroring from a remote source.
  * ``rpki_rov_filter``: whether RPKI validation is enabled for this source.
  * ``scopefilter_enabled``: whether the scope filter is enabled on this instance,
    and is also enabled for this source.
  * ``route_preference``: the route order preference setting for this source,
    if any is set.
  * ``local_journal_kept``: whether this IRRd instance keeps a local journal
    of the changes in this source, allowing it to be mirrored over NRTM.
  * ``serial_oldest_journal`` / ``serial_newest_journal``: the oldest and
    newest serials in the local journal on this IRRd instance for this source.
    IRRd does not guarantee that all changes in this range are available over
    NRTM. This serial range is entirely independent of that used by the
    mirror source, if any.
  * ``serial_last_export``: the serial at which the last export for this
    source took place, if any.
  * ``serial_newest_mirror``: the newest serial seen from a mirroring source,
    i.e. the local IRRd has updated up to this serial number from the mirror.
    This number can be compared to the serials reported by the mirror
    directly, to see whether IRRd is up to date. This number is independent
    from the range in the local journal.
  * ``last_update``: the time of the last change to this source. This may be
    an authoritative change, an update from a mirror, a re-import, a change
    in the RPKI status of an object, or something else.
  * ``synchronised_serials``: whether or not a mirrored source is running with
    :ref:`synchronised serials <mirroring-nrtm-serials>`.
* ``!m<object-class>,<primary-key>`` searches for objects exactly matching
  the primary key, of the specified RPSL object class. For example:
  ``!maut-num,AS23456``. Stops at the first object. The key is case
  sensitive. If the object class is `route` or `route6`, any spaces or dashes
  in the key are ignored for legacy IRRd compatibility in composite keys.
  This allows querying for e.g. ``!mroute,192.0.2.0/24AS65530``, but also
  the legacy options ``192.0.2.0/24 AS65530`` and ``!mroute,192.0.2.0/24-AS65530``
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
* ``!fno-rpki-filter``, ``!fno-scope-filter``, and ``!fno-route-preference-filter``
  disables the filtering of :doc:`suppressed objects </admins/object-suppression>`
  for the remainder of the connection. Disabling the filter only applies to ``!r``
  queries and all RIPE style queries. This is only intended as a debugging aid.
* ``!fno-scope-filter`` disables filtering out-of-scope objects. If
  the scope filter is enabled, objects that are
  :doc:`out of scope </admins/scopefilter>` are not included in the output of any query by default.
  After using ``!fno-scope-filter``, this filter is disabled for the remainder of
  the connection. Disabling the filter only applies to ``!r`` queries and
  all RIPE style queries. This is only intended as a debugging aid.


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

The queries are:

* ``-l``, ``-L``, ``-M`` and ``-x`` search for `route` or `route6` objects.
  The differences are:

  * ``-x``, e.g. ``-x 192.0.2.0/24``, finds exact matching objects and
    returns them
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

* ``-k`` activates keepalive mode on TCP. The connection will be kept open
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
recursion on whois.


Query responses
---------------

The response format differs for HTTPS and raw TCP queries, and also per
query style for raw TCP queries.

HTTPS responses
^^^^^^^^^^^^^^^

HTTPS queries have four possible responses:

* If the query produced a result, the response content with status
  code 200.
* If the query did not produce a result, but was valid, an empty
  response with status code 204.
* If the query was invalid or missing, an error message with
  status code 400.
* If IRRd encountered an internal error while processing, a generic
  error message with status code 500.

.. tip::
   If you are experimenting with the API in a browser, note that some
   browsers handle a 204 response by keeping the previous content and
   URL visible - even though they are not the output of your latest
   query. Most browsers will have a network inspection console that
   shows the details of each HTTPS request.

Raw TCP responses
^^^^^^^^^^^^^^^^^
The character encoding is always UTF-8, though many objects fit 7-bit ASCII.
Line separators are a single newline (``\n``) character.

IRRd style TCP responses
""""""""""""""""""""""""
For a successful response returning data, the response is::

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


RIPE style TCP responses
""""""""""""""""""""""""
For a successful response returning data, the response is simply the object
data, with different objects separated by a blank line, followed by an
extra newline. RIPE style queries always end with two empty lines, i.e.
two newline characters.

If the query was valid, but no entries were found, the response is::

    %  No entries found for the selected source(s).

If the query was invalid::

    %% <error message>

Source search order
-------------------
IRRd queries have a default set of sources enabled, which can be changed
with the ``!s`` command or the ``-s`` flag. When enabling multiple sources,
the order in which they are listed defines their prioritisation, which can
make a significant difference in some queries. For example, ``!m`` will find
the first object with a given primary key, from the highest priority source
in which it was found.

The currently enabled sources and their priority can be seen with ``!s-lc``.
