=======
Queries
=======

IRRd accepts queries on port 43. The encoding used is always UTF-8, though
many objects are 7-bit ASCII. Line seperators are a single newline (``\n``)
character.

IRRd vs RIPE style
------------------
IRRd supports two styles of queries:

* IRRd style queries, which are powerful but quite specific. For example,
  ``!iRS-EXAMPLE,1`` finds all members of route-set `RS-EXAMPLE`,
  recursively.
* RIPE style queries, which you may know from the RIPE whois database and many
  similar implementations. For example, ``-s APNIC -M 192.0.2/21`` finds
  all more specific objects of 192.0.2/21 from source APNIC.

IRRd style queries
------------------

* ``!!`` activates multiple command mode. The connection will be kept open
  after a query has been sent. Queries are answered in the order they were
  submitted. Takes no parameters.
* ``!gAS<asn>`` finds all IPv4 routes for an origin AS. Only distinct
  prefixes of the routes are returned, seperated by spaces.
* ``!6AS<asn>`` finds all IPv6 routes for an origin AS. Only distinct
  prefixes of the routes are returned, seperated by spaces.
* ``!i<set-name>`` returns all members of an as-set or a route-set. If
  ``,1`` is appended, the search is performed recursively. Returns all members
  (and possibly names of other sets, if the search was not recursive or
  member sets could not be resolved), separated by spaces. For example:
  ``!iRS-EXAMPLE,1`` returns all members of `RS-EXAMPLE`, recursively.
* ``!j`` TBD
* ``!m<object-class>,<primary-key>`` searches for objects exactly matching
  the primary key, of the specified RPSL object class. For example:
  ``!maut-num,AS23456``. Stops at the first object. The key is case
  sensitive.
* ``!o<mntner-name>`` searches for all objects with the specified maintainer
  in it's `mnt-by` attribute.
* ``!n<free-text>`` identifies the client querying IRRd. Optional, but may
  be helpful when debugging issues.
* ``!r<prefix>,<option>`` searches for route or route6 objects. The options
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

Responses
^^^^^^^^^

For a succesful response returning data, the response is::

    A<length>
    <response content>
    C

The length is the number of bytes in the response, including the newline
immediately after the response. Different objects are part of one block of
response content, each object separated by a blank line.

If the query was valid, but no entries were found, the response is::

    C

If the query was valid, but the primary key queried for did not exist::

    D

If the query was invalid::

    F <error message>


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

Supported flags
^^^^^^^^^^^^^^^

* ``-k`` activates keepalive mode. The connection will be kept open
  after a query has been sent. Queries are answered in the order they were
  submitted.
* ``-l``, ``-L``, ``-M`` and ``-x`` search for route or route6 objects.
  The differences are:

  * ``-x``, e.g. ``-x 192.0.2.0/24``, to find exact matching objects and
    return them
  * ``-l``, e.g. ``-l 192.0.2.0/24``, to find one level less specific objects,
    excluding exact matches, and return them
  * ``-L``, e.g. ``-L 192.0.2.0/24``, to find all level less specific objects,
    including exact matches, and return them
  * ``-M``, e.g. ``-M 192.0.2.0/24``, to find one level more specific objects,
    excluding exact matches, and return them
* ``-i <attribute> <value>`` searches for objects where the attribute has this
  particular value. Only available for some fields. For example,
  ``-i origin AS23456`` finds all objects with an `origin` attribute set to
  `AS23456`. In attributes that contain multiple values, one of their values
  must match the value in the query.
* ``-s <sources>`` and ``-a`` set the sources used for queries. ``-s``
  restricts all responses to a specified list of sources,
  comma-separated, e.g. ``-s RIPE,NTTCOM``. ``-a`` enables all sources.
  This persists across queries.
* ``-T <object-classes>`` restricts a query to certain object classes,
  comma-separated. This does not persist across queries.
* ``-t <object-class>`` returns the template for a particular object class.
* ``-K`` restricts the output to primary key fields only.
* ``-V <free-text>`` identifies the client querying IRRd. Optional, but may
  be helpful when debugging issues.
* Any other (part of) the query is interpreted as a free text search:

  * If the input is a valid AS number, the query will look for any matching
    `as-block`, `as-set` or `aut-num` objects.
  * If the input is a valid IP address or prefix, the query will look for
    any less specific matches of any object class.
  * Otherwise, the query will look for any exact case insensitive matches
    on the primary key of an object, or a `person` or `role` where their
    name includes the search string, case insensitive.

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

