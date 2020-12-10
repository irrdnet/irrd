================
HTTP status page
================

A status page is available on the HTTP server in IRRd.
This page is only accessible to IPs :doc:`configured </admins/configuration>`
in the access list set in the ``server.http.status_access_list`` setting.

The URL of the status page is: ``/v1/status/``.

Statistics overview
-------------------
The first part of the status page is an overview of statistics for the known
sources in IRRd. This includes:

* `total obj`: total number of objects in this source, of any class
* `rt obj`: total number of `route` objects in this source
* `aut-num obj`: total number of `aut-num` objects in this source
* `serial`: latest serial seen for this source. May be unknown for sources
  using :doc:`periodic full import mode </users/mirroring>`.
* `last export`: serial at which this IRRd instance last created an export
  for this source

Details for each source
-----------------------
The next part of the page has further details for each source.

The local information shows:

* `Authoritative`: whether this source is authoritative per the
  :doc:`configuration </admins/configuration>`.
* `Object class filter`: which object classes are included in mirroring,
  or `None` if no filters are applied.
* `Oldest/newest serial seen`: the oldest and newest serial which this IRRd
  has seen from this source. Note that this is distinct from the local journal,
  as when journal keeping is disabled for a source, these numbers still update,
  e.g. when NRTM operations are processed. May be unknown for sources using
  :doc:`periodic full import mode </users/mirroring>`.
* `Oldest/newest journal serial number`: the oldest and newest serial which
  this IRRd has in the local journal. This is the range that can be requested
  with NRTM queries. Note that for mirrored sources, it is not possible
  to guarantee that all operations in this range are in the local journal.
  NRTM serials can have gaps, which means it is not possible to be certain
  whether a gap is intentional, or because an NRTM operation was not processed,
  or is missing due to temporary disabling of journal keeping.
* `Last export at serial number`: serial at which this IRRd instance last
  created an export for this source, if any.
* `Last update`: the last time when a change was processed for this source,
  either by user submitted changes, NRTM operations, or a full import.
* `Local journal kept`: whether local journal keeping is enabled.
* `Last import error occurred at`: when the most recent import error occurred,
  for mirrored sources. An import error means an object
  :doc:`was invalid </admins/object-validation>`, and therefore could not be
  imported. Full details are provided in the logfile.

The remote information shows:

* `NRTM host`: the host on which NRTM queries are run, if configured.
* `Mirror-able`: whether the `!j` response of the NRTM host indicated this
  source is mirror-able.
* `Oldest/newest journal serial number`: the oldest and newest serial which
  the NRTM host has in its own journal.
* `Last export at serial number`: serial at which the NRTM host last created
  an export for this source.

Not all remote information may be available for all sources.
