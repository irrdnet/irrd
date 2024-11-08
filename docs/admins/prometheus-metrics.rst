==================
Prometheus Metrics
==================

A Prometheus-compatible metrics page is available on the HTTP server in IRRd.
This page is only accessible to IPs :doc:`configured </admins/configuration>`
in the access list set in the ``server.http.status_access_list`` setting.

The URL of the metrics page is: ``/metrics/``.

Generic metrics
---------------
The generic metrics exposed are:

* `irrd_info`: exposes the version of IRRd as a label

  .. code-block::

    # HELP irrd_info Info from IRRD, value is always 1
    # TYPE irrd_info gauge
    irrd_info{version="4.5-dev"} 1

* `irrd_uptime_seconds`: the up-time of IRRd in seconds

  .. code-block::

    # HELP irrd_uptime_seconds Uptime of IRRD in seconds
    # TYPE irrd_uptime_seconds gauge
    irrd_uptime_seconds 1063

* `irrd_startup_timestamp`: the timestamp when IRRd was started

  .. code-block::

    # HELP irrd_startup_timestamp Startup time of IRRD in seconds since UNIX epoch
    # TYPE irrd_startup_timestamp gauge
    irrd_startup_timestamp 1699966491

Object storage for each source
------------------------------
The next part has further details on the objects stored for each source.

* `irrd_object_class_total`: a metric with labels for source and object class,
  showing the number of object in storage

  .. code-block::

    # HELP irrd_object_class_total Number of objects per class per source
    # TYPE irrd_object_class_total gauge
    irrd_object_class_total{source="SOURCE1", object_class="aut-num"} 2410
    irrd_object_class_total{source="SOURCE1", object_class="route"} 109678
    irrd_object_class_total{source="SOURCE1", object_class="route6"} 2000
    …etc…
    irrd_object_class_total{source="SOURCE2", object_class="aut-num"} 1738
    irrd_object_class_total{source="SOURCE2", object_class="mntner"} 1803
    irrd_object_class_total{source="SOURCE2", object_class="route"} 24203
    irrd_object_class_total{source="SOURCE2", object_class="route-set"} 106
    irrd_object_class_total{source="SOURCE2", object_class="route6"} 6149
    …etc…
    irrd_object_class_total{source="RPKI", object_class="route"} 391323
    irrd_object_class_total{source="RPKI", object_class="route6"} 89702
    …etc…

Source updates and errors
-------------------------
The next part exposes information on when the source was last updated and
when the last error occurred.

The ``irrd_last_update_*`` and ``irrd_last_rpsl_data_update_*`` fields
sounds similar, but have significant differences: the former updates when
anything is changed in the internal state of the source. That includes RPSL
data changes, but also recording an error, making an export, etc.
The ``irrd_last_rpsl_data_update_*`` fields only update after a modification
to the RPSL data. This includes changes in visibility due to object
suppression status.

* `irrd_last_update_seconds`: seconds since the last update to RPSL data

    .. code-block::

        # HELP irrd_last_rpsl_data_update_seconds Seconds since the last update to RPSL data
        # TYPE irrd_last_rpsl_data_update_seconds gauge
        irrd_last_rpsl_data_update_seconds{source="SOURCE1"} 2289
        irrd_last_rpsl_data_update_seconds{source="SOURCE2"} 4301
        irrd_last_rpsl_data_update_seconds{source="RPKI"} 10

* `irrd_last_update_timestamp`: UNIX timestamp of the last update to RPSL data

    .. code-block::

        # HELP irrd_last_rpsl_data_update_timestamp Timestamp of the last update to RPSL data in seconds since UNIX epoch
        # TYPE irrd_last_rpsl_data_update_timestamp gauge
        irrd_last_rpsl_data_update_timestamp{source="SOURCE1"} 1699965265
        irrd_last_rpsl_data_update_timestamp{source="SOURCE2"} 1699963253
        irrd_last_rpsl_data_update_timestamp{source="RPKI"} 1699967543

* `irrd_last_update_seconds`: seconds since the last internal status change

    .. code-block::

        # HELP irrd_last_update_seconds Seconds since the last internal status change
        # TYPE irrd_last_update_seconds gauge
        irrd_last_update_seconds{source="SOURCE1"} 2289
        irrd_last_update_seconds{source="SOURCE2"} 4301
        irrd_last_update_seconds{source="RPKI"} 10

* `irrd_last_update_timestamp`: UNIX timestamp of the last internal status change

    .. code-block::

        # HELP irrd_last_update_timestamp Timestamp of the last internal status change in seconds since UNIX epoch
        # TYPE irrd_last_update_timestamp gauge
        irrd_last_update_timestamp{source="SOURCE1"} 1699965265
        irrd_last_update_timestamp{source="SOURCE2"} 1699963253
        irrd_last_update_timestamp{source="RPKI"} 1699967543

* `irrd_last_error_seconds`: seconds since the last mirroring error

    .. code-block::

        # HELP irrd_last_error_seconds Seconds since the last mirroring error
        # TYPE irrd_last_error_seconds gauge
        irrd_last_error_seconds{source="SOURCE1"} 84438

* `irrd_last_error_timestamp`: UNIX timestamp of the last mirroring error

    .. code-block::

        # HELP irrd_last_error_timestamp Timestamp of the last mirroring error in seconds since UNIX epoch
        # TYPE irrd_last_error_timestamp gauge
        irrd_last_error_timestamp{source="SOURCE1"} 1699883115

Source serials
--------------
The final part exposes information on the latest serials imported/exported.

* `irrd_nrtm4_client_version`: the most recent NRTMv3 serial we mirrored from a remote source

    .. code-block::

        # HELP irrd_mirrored_serial Newest NRTMv4 version mirrored from upstream
        # TYPE irrd_nrtm4_client_version gauge
        irrd_nrtm4_client_version{source="SOURCE1"} 42

* `irrd_mirrored_serial`: the most recent NRTMv3 serial we mirrored from a remote source

    .. code-block::

        # HELP irrd_mirrored_serial Newest NRTMv3 serial number mirrored from upstream
        # TYPE irrd_mirrored_serial gauge
        irrd_mirrored_serial{source="SOURCE1"} 1352386
        irrd_mirrored_serial{source="SOURCE2"} 112741

* `irrd_last_export_serial`: the serial number of the most recent full export

    .. code-block::

        # HELP irrd_last_export_serial Last serial number for full export
        # TYPE irrd_last_export_serial gauge
        irrd_mirrored_serial{source="SOURCE1"} 1352000
        irrd_mirrored_serial{source="SOURCE2"} 112000

* `irrd_oldest_journal_serial`: the oldest serial number in the journal

    .. code-block::

        # HELP irrd_oldest_journal_serial Oldest serial in the journal
        # TYPE irrd_oldest_journal_serial gauge
        irrd_mirrored_serial{source="SOURCE1"} 1300000
        irrd_mirrored_serial{source="SOURCE2"} 110000

* `irrd_newest_journal_serial`: the newest serial number in the journal

    .. code-block::

        # HELP irrd_newest_journal_serial Newest serial in the journal
        # TYPE irrd_newest_journal_serial gauge
        irrd_mirrored_serial{source="SOURCE1"} 1360000
        irrd_mirrored_serial{source="SOURCE2"} 113000
