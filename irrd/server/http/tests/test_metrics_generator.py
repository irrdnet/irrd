import textwrap
from datetime import datetime
from unittest.mock import Mock

import freezegun
from pytz import UTC

from irrd import ENV_MAIN_STARTUP_TIME, __version__

from ..metrics_generator import MetricsGenerator


class TestMetricsGenerator:
    @freezegun.freeze_time(datetime.fromtimestamp(50, UTC))
    def test_request(self, monkeypatch):
        mock_database_handler = Mock()
        monkeypatch.setattr(
            "irrd.server.http.metrics_generator.DatabaseHandler", lambda: mock_database_handler
        )
        mock_status_query = Mock()
        monkeypatch.setattr(
            "irrd.server.http.metrics_generator.DatabaseStatusQuery", lambda: mock_status_query
        )
        mock_statistics_query = Mock()
        monkeypatch.setattr(
            "irrd.server.http.metrics_generator.RPSLDatabaseObjectStatisticsQuery",
            lambda: mock_statistics_query,
        )
        monkeypatch.setenv(ENV_MAIN_STARTUP_TIME, "5")

        nrtm4_client_session_id = "7c94d3eb-1d7f-4197-9fff-9e6101cdec80"
        mock_query_result = iter(
            [
                [
                    {"source": "TEST1", "object_class": "route", "count": 10},
                    {"source": "TEST1", "object_class": "aut-num", "count": 10},
                    {"source": "TEST1", "object_class": "other", "count": 5},
                    {"source": "TEST2", "object_class": "route", "count": 42},
                ],
                [
                    {
                        "source": "TEST1",
                        "serial_oldest_seen": 10,
                        "serial_newest_seen": 21,
                        "serial_oldest_journal": 15,
                        "serial_newest_journal": 20,
                        "serial_last_export": 16,
                        "serial_newest_mirror": 25,
                        "nrtm4_client_session_id": None,
                        "nrtm4_client_version": None,
                        "last_error_timestamp": datetime.fromtimestamp(10, UTC),
                        "rpsl_data_updated": datetime.fromtimestamp(17, UTC),
                        "updated": datetime.fromtimestamp(18, UTC),
                    },
                    {
                        "source": "TEST2",
                        "serial_oldest_seen": 210,
                        "serial_newest_seen": 221,
                        "serial_oldest_journal": None,
                        "serial_newest_journal": None,
                        "serial_last_export": None,
                        "serial_newest_mirror": None,
                        "nrtm4_client_session_id": nrtm4_client_session_id,
                        "nrtm4_client_version": 14,
                        "last_error_timestamp": None,
                        "rpsl_data_updated": datetime.fromtimestamp(14, UTC),
                        "updated": datetime.fromtimestamp(15, UTC),
                    },
                ],
            ]
        )
        mock_database_handler.execute_query = lambda query, flush_rpsl_buffer=True: next(mock_query_result)

        status_metrics = MetricsGenerator().generate()
        expected_metrics = textwrap.dedent(
            """
            # HELP irrd_info Info from IRRd, value is always 1
            # TYPE irrd_info gauge
            irrd_info{version=\""""
            + __version__
            + """\"} 1
            
            # HELP irrd_uptime_seconds Uptime of IRRd in seconds
            # TYPE irrd_uptime_seconds gauge
            irrd_uptime_seconds 45
            
            # HELP irrd_startup_timestamp Startup time of IRRd in seconds since UNIX epoch
            # TYPE irrd_startup_timestamp gauge
            irrd_startup_timestamp 5
            
            # HELP irrd_object_class_total Number of objects per class per source
            # TYPE irrd_object_class_total gauge
            irrd_object_class_total{source="TEST1", object_class="aut-num"} 10
            irrd_object_class_total{source="TEST1", object_class="other"} 5
            irrd_object_class_total{source="TEST1", object_class="route"} 10
            irrd_object_class_total{source="TEST2", object_class="route"} 42
            
            # HELP irrd_last_rpsl_data_update_seconds Seconds since the last update to RPSL data
            # TYPE irrd_last_rpsl_data_update_seconds gauge
            irrd_last_rpsl_data_update_seconds{source="TEST1"} 33
            irrd_last_rpsl_data_update_seconds{source="TEST2"} 36
            
            # HELP irrd_last_rpsl_data_update_timestamp Timestamp of the last update to RPSL data in seconds since UNIX epoch
            # TYPE irrd_last_rpsl_data_update_timestamp gauge
            irrd_last_rpsl_data_update_timestamp{source="TEST1"} 17
            irrd_last_rpsl_data_update_timestamp{source="TEST2"} 14
            
            # HELP irrd_last_update_seconds Seconds since the last internal status change
            # TYPE irrd_last_update_seconds gauge
            irrd_last_update_seconds{source="TEST1"} 32
            irrd_last_update_seconds{source="TEST2"} 35
            
            # HELP irrd_last_update_timestamp Timestamp of the last internal status change in seconds since UNIX epoch
            # TYPE irrd_last_update_timestamp gauge
            irrd_last_update_timestamp{source="TEST1"} 18
            irrd_last_update_timestamp{source="TEST2"} 15
            
            # HELP irrd_last_error_seconds Seconds since the last mirroring error
            # TYPE irrd_last_error_seconds gauge
            irrd_last_error_seconds{source="TEST1"} 40
            
            # HELP irrd_last_error_timestamp Timestamp of the last mirroring error in seconds since UNIX epoch
            # TYPE irrd_last_error_timestamp gauge
            irrd_last_error_timestamp{source="TEST1"} 10
            
            # HELP irrd_nrtm4_client_version Newest NRTMv4 version mirrored from upstream
            # TYPE irrd_nrtm4_client_version gauge
            irrd_nrtm4_client_version{source="TEST2"} 14
            
            # HELP irrd_mirrored_serial Newest serial NRTMv3 number mirrored from upstream
            # TYPE irrd_mirrored_serial gauge
            irrd_mirrored_serial{source="TEST1"} 25
            
            # HELP irrd_last_export_serial Last serial number for full export
            # TYPE irrd_last_export_serial gauge
            irrd_last_export_serial{source="TEST1"} 16
            
            # HELP irrd_oldest_journal_serial Oldest serial in the journal
            # TYPE irrd_oldest_journal_serial gauge
            irrd_oldest_journal_serial{source="TEST1"} 15
            
            # HELP irrd_newest_journal_serial Newest serial in the journal
            # TYPE irrd_newest_journal_serial gauge
            irrd_newest_journal_serial{source="TEST1"} 20\n\n"""
        ).lstrip()
        print(status_metrics)

        assert expected_metrics == status_metrics
