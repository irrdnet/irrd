import socket
import textwrap
from datetime import datetime, timezone
from unittest.mock import Mock

from irrd import __version__
from irrd.conf import get_setting

from ..status_generator import StatusGenerator


class TestStatusGenerator:
    def test_request(self, monkeypatch, config_override):
        mock_database_handler = Mock()
        monkeypatch.setattr(
            "irrd.server.http.status_generator.DatabaseHandler", lambda: mock_database_handler
        )
        mock_status_query = Mock()
        monkeypatch.setattr(
            "irrd.server.http.status_generator.DatabaseStatusQuery", lambda: mock_status_query
        )
        monkeypatch.setattr(
            "irrd.server.http.status_generator.is_serial_synchronised", lambda dh, source: False
        )
        mock_statistics_query = Mock()
        monkeypatch.setattr(
            "irrd.server.http.status_generator.RPSLDatabaseObjectStatisticsQuery",
            lambda: mock_statistics_query,
        )

        def mock_whois_query(nrtm_host, nrtm_port, source):
            assert source in ["TEST1", "TEST2", "TEST3"]
            if source == "TEST1":
                assert nrtm_host == "nrtm1.example.com"
                assert nrtm_port == 43
                return True, 142, 143, 144
            elif source == "TEST2":
                raise ValueError()
            elif source == "TEST3":
                raise socket.timeout()

        monkeypatch.setattr("irrd.server.http.status_generator.whois_query_source_status", mock_whois_query)

        config_override(
            {
                "sources": {
                    "rpki": {"roa_source": "roa source"},
                    "TEST1": {
                        "authoritative": False,
                        "keep_journal": True,
                        "nrtm_host": "nrtm1.example.com",
                        "nrtm_port": 43,
                        "object_class_filter": "object-class-filter",
                        "rpki_excluded": True,
                        "route_object_preference": 200,
                    },
                    "TEST2": {
                        "authoritative": True,
                        "keep_journal": False,
                        "nrtm_host": "nrtm2.example.com",
                        "nrtm_port": 44,
                    },
                    "TEST3": {
                        "authoritative": True,
                        "keep_journal": False,
                        "nrtm_host": "nrtm3.example.com",
                        "nrtm_port": 45,
                    },
                    "TEST4": {
                        "authoritative": False,
                        "keep_journal": False,
                        "nrtm4_client_notification_file_url": "url",
                    },
                    "TEST5": {
                        "authoritative": False,
                        "keep_journal": False,
                    },
                }
            }
        )

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
                        "nrtm4_client_session_id": "session_id",
                        "nrtm4_client_version": 10,
                        "nrtm4_server_session_id": "server_session_id",
                        "nrtm4_server_version": 22,
                        "nrtm4_server_last_update_notification_file_update": datetime(
                            2018, 1, 1, tzinfo=timezone.utc
                        ),
                        "nrtm4_server_last_snapshot_version": 21,
                        "nrtm4_server_previous_deltas": ["d1", "d2"],
                        "last_error_timestamp": datetime(2018, 1, 1, tzinfo=timezone.utc),
                        "rpsl_data_updated": datetime(2017, 6, 1, tzinfo=timezone.utc),
                        "updated": datetime(2018, 6, 1, tzinfo=timezone.utc),
                    },
                    {
                        "source": "TEST2",
                        "serial_oldest_seen": 210,
                        "serial_newest_seen": 221,
                        "serial_oldest_journal": None,
                        "serial_newest_journal": None,
                        "serial_last_export": None,
                        "serial_newest_mirror": None,
                        "nrtm4_client_session_id": None,
                        "nrtm4_client_version": None,
                        "nrtm4_server_session_id": None,
                        "nrtm4_server_version": None,
                        "nrtm4_server_last_update_notification_file_update": None,
                        "nrtm4_server_last_snapshot_version": None,
                        "nrtm4_server_previous_deltas": None,
                        "last_error_timestamp": datetime(2019, 1, 1, tzinfo=timezone.utc),
                        "rpsl_data_updated": datetime(2018, 6, 1, tzinfo=timezone.utc),
                        "updated": datetime(2019, 6, 1, tzinfo=timezone.utc),
                    },
                    {
                        "source": "TEST3",
                        "serial_oldest_seen": None,
                        "serial_newest_seen": None,
                        "serial_oldest_journal": None,
                        "serial_newest_journal": None,
                        "serial_last_export": None,
                        "serial_newest_mirror": None,
                        "nrtm4_client_session_id": None,
                        "nrtm4_client_version": None,
                        "nrtm4_server_session_id": None,
                        "nrtm4_server_version": None,
                        "nrtm4_server_last_update_notification_file_update": None,
                        "nrtm4_server_last_snapshot_version": None,
                        "nrtm4_server_previous_deltas": None,
                        "last_error_timestamp": None,
                        "rpsl_data_updated": None,
                        "updated": None,
                    },
                    {
                        "source": "TEST4",
                        "serial_oldest_seen": None,
                        "serial_newest_seen": None,
                        "serial_oldest_journal": None,
                        "serial_newest_journal": None,
                        "serial_last_export": None,
                        "serial_newest_mirror": None,
                        "nrtm4_client_session_id": None,
                        "nrtm4_client_version": None,
                        "nrtm4_server_session_id": None,
                        "nrtm4_server_version": None,
                        "nrtm4_server_last_update_notification_file_update": None,
                        "nrtm4_server_last_snapshot_version": None,
                        "nrtm4_server_previous_deltas": None,
                        "last_error_timestamp": None,
                        "rpsl_data_updated": None,
                        "updated": None,
                    },
                    {
                        "source": "TEST5",
                        "serial_oldest_seen": None,
                        "serial_newest_seen": None,
                        "serial_oldest_journal": None,
                        "serial_newest_journal": None,
                        "serial_last_export": None,
                        "serial_newest_mirror": None,
                        "nrtm4_client_session_id": None,
                        "nrtm4_client_version": None,
                        "nrtm4_server_session_id": None,
                        "nrtm4_server_version": None,
                        "nrtm4_server_last_update_notification_file_update": None,
                        "nrtm4_server_last_snapshot_version": None,
                        "nrtm4_server_previous_deltas": None,
                        "last_error_timestamp": None,
                        "rpsl_data_updated": None,
                        "updated": None,
                    },
                ],
            ]
        )
        mock_database_handler.execute_query = lambda query, flush_rpsl_buffer=True: next(mock_query_result)

        status_report = StatusGenerator().generate()
        expected_report = textwrap.dedent(f"""
            IRRD version {__version__}
            Listening on ::0 port {get_setting('server.whois.port')}
            
            
            -----------------------------------------------------------------------
             source    total obj    rt obj    aut-num obj    serial    last export 
            -----------------------------------------------------------------------
             TEST1            25        10             10        21             16 
             TEST2            42        42              0       221                
             TEST3             0         0              0      None                
             TEST4             0         0              0      None                
             TEST5             0         0              0      None                
             TOTAL            67        52             10                          
            
            
            Status for TEST1
            -------------------
            Local information:
                Authoritative: No
                Object class filter: object-class-filter
                Oldest serial seen: 10
                Newest serial seen: 21
                Oldest local journal serial number: 15
                Newest local journal serial number: 20
                Last export at serial number: 16
                Newest serial number mirrored: 25
                NRTMv4 client: current session: session_id
                NRTMv4 client: current version: 10
                NRTMv4 server: current session: server_session_id
                NRTMv4 server: current version: 22
                NRTMv4 server: last Update Notification File update: 2018-01-01 00:00:00+00:00
                NRTMv4 server: last snapshot version: 21
                NRTMv4 server: number of deltas: 2
                Synchronised NRTM serials: No
                Last change to RPSL data: 2017-06-01 00:00:00+00:00
                Last internal status update: 2018-06-01 00:00:00+00:00
                Local journal kept: Yes
                Last import error occurred at: 2018-01-01 00:00:00+00:00
                RPKI validation enabled: No
                Scope filter enabled: No
                Route object preference: 200
            
            Remote information:
                NRTM host: nrtm1.example.com port 43
                Mirrorable: Yes
                Oldest journal serial number: 142
                Newest journal serial number: 143
                Last export at serial number: 144
            
            
            Status for TEST2
            -------------------
            Local information:
                Authoritative: Yes
                Object class filter: None
                Oldest serial seen: 210
                Newest serial seen: 221
                Oldest local journal serial number: None
                Newest local journal serial number: None
                Last export at serial number: None
                Newest serial number mirrored: None
                NRTMv4 client: current session: None
                NRTMv4 client: current version: None
                NRTMv4 server: current session: None
                NRTMv4 server: current version: None
                NRTMv4 server: last Update Notification File update: None
                NRTMv4 server: last snapshot version: None
                NRTMv4 server: number of deltas: 0
                Synchronised NRTM serials: No
                Last change to RPSL data: 2018-06-01 00:00:00+00:00
                Last internal status update: 2019-06-01 00:00:00+00:00
                Local journal kept: No
                Last import error occurred at: 2019-01-01 00:00:00+00:00
                RPKI validation enabled: Yes
                Scope filter enabled: No
                Route object preference: None

            Remote information:
                NRTM host: nrtm2.example.com port 44
                Remote status query unsupported or query failed
            
            
            Status for TEST3
            -------------------
            Local information:
                Authoritative: Yes
                Object class filter: None
                Oldest serial seen: None
                Newest serial seen: None
                Oldest local journal serial number: None
                Newest local journal serial number: None
                Last export at serial number: None
                Newest serial number mirrored: None
                NRTMv4 client: current session: None
                NRTMv4 client: current version: None
                NRTMv4 server: current session: None
                NRTMv4 server: current version: None
                NRTMv4 server: last Update Notification File update: None
                NRTMv4 server: last snapshot version: None
                NRTMv4 server: number of deltas: 0
                Synchronised NRTM serials: No
                Last change to RPSL data: None
                Last internal status update: None
                Local journal kept: No
                Last import error occurred at: None
                RPKI validation enabled: Yes
                Scope filter enabled: No
                Route object preference: None
            
            Remote information:
                NRTM host: nrtm3.example.com port 45
                Unable to reach remote server for status query


            Status for TEST4
            -------------------
            Local information:
                Authoritative: No
                Object class filter: None
                Oldest serial seen: None
                Newest serial seen: None
                Oldest local journal serial number: None
                Newest local journal serial number: None
                Last export at serial number: None
                Newest serial number mirrored: None
                NRTMv4 client: current session: None
                NRTMv4 client: current version: None
                NRTMv4 server: current session: None
                NRTMv4 server: current version: None
                NRTMv4 server: last Update Notification File update: None
                NRTMv4 server: last snapshot version: None
                NRTMv4 server: number of deltas: 0
                Synchronised NRTM serials: No
                Last change to RPSL data: None
                Last internal status update: None
                Local journal kept: No
                Last import error occurred at: None
                RPKI validation enabled: Yes
                Scope filter enabled: No
                Route object preference: None
            
            Remote information:
                NRTMv4 client Update Notification File URL: url
            
            
            Status for TEST5
            -------------------
            Local information:
                Authoritative: No
                Object class filter: None
                Oldest serial seen: None
                Newest serial seen: None
                Oldest local journal serial number: None
                Newest local journal serial number: None
                Last export at serial number: None
                Newest serial number mirrored: None
                NRTMv4 client: current session: None
                NRTMv4 client: current version: None
                NRTMv4 server: current session: None
                NRTMv4 server: current version: None
                NRTMv4 server: last Update Notification File update: None
                NRTMv4 server: last snapshot version: None
                NRTMv4 server: number of deltas: 0
                Synchronised NRTM serials: No
                Last change to RPSL data: None
                Last internal status update: None
                Local journal kept: No
                Last import error occurred at: None
                RPKI validation enabled: Yes
                Scope filter enabled: No
                Route object preference: None
            
            Remote information:
                No NRTM configured.\n\n""").lstrip()

        assert expected_report == status_report
