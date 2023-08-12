import threading
import time
from unittest.mock import Mock

import pytest

from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.utils.test_utils import flatten_mock_calls

from ..database_handler import DatabaseHandler
from ..preload import (
    REDIS_KEY_PK_SOURCE_SEPARATOR,
    REDIS_PRELOAD_ALL_MESSAGE,
    Preloader,
    PreloadStoreManager,
    PreloadUpdater,
)
from ..queries import RPSLDatabaseQuery

# Use different stores in tests
TEST_REDIS_ORIGIN_ROUTE4_STORE_KEY = "TEST-irrd-preload-origin-route4"
TEST_REDIS_ORIGIN_ROUTE6_STORE_KEY = "TEST-irrd-preload-origin-route6"
TEST_REDIS_PRELOAD_RELOAD_CHANNEL = "TEST-irrd-preload-reload-channel"
TEST_REDIS_PRELOAD_COMPLETE_CHANNEL = "TEST-irrd-preload-complete-channel"


@pytest.fixture()
def mock_preload_updater(monkeypatch, config_override):
    mock_preload_updater = Mock(spec=PreloadUpdater)
    monkeypatch.setattr("irrd.storage.preload.PreloadUpdater", mock_preload_updater)
    yield mock_preload_updater


@pytest.fixture()
def mock_redis_keys(monkeypatch, config_override):
    monkeypatch.setattr(
        "irrd.storage.preload.REDIS_ORIGIN_ROUTE4_STORE_KEY", TEST_REDIS_ORIGIN_ROUTE4_STORE_KEY
    )
    monkeypatch.setattr(
        "irrd.storage.preload.REDIS_ORIGIN_ROUTE6_STORE_KEY", TEST_REDIS_ORIGIN_ROUTE6_STORE_KEY
    )
    monkeypatch.setattr(
        "irrd.storage.preload.REDIS_PRELOAD_RELOAD_CHANNEL", TEST_REDIS_PRELOAD_RELOAD_CHANNEL
    )
    monkeypatch.setattr(
        "irrd.storage.preload.REDIS_PRELOAD_COMPLETE_CHANNEL", TEST_REDIS_PRELOAD_COMPLETE_CHANNEL
    )


class TestPreloading:
    def test_load_reload_thread_management(self, mock_preload_updater, mock_redis_keys):
        preload_manager = PreloadStoreManager()

        preload_manager_thread = threading.Thread(target=preload_manager.main, daemon=True)
        preload_manager_thread.start()
        time.sleep(1)
        assert mock_preload_updater.mock_calls[0][0] == ""
        assert mock_preload_updater.mock_calls[0][1][0] == preload_manager
        assert mock_preload_updater.mock_calls[0][1][1] == preload_manager._reload_lock
        assert mock_preload_updater.mock_calls[1][0] == "().start"
        assert len(mock_preload_updater.mock_calls) == 2
        assert len(preload_manager._threads) == 1
        mock_preload_updater.reset_mock()

        preload_manager.perform_reload(REDIS_PRELOAD_ALL_MESSAGE)

        assert mock_preload_updater.mock_calls[0][0] == "().is_alive"
        assert mock_preload_updater.mock_calls[1][0] == ""
        assert mock_preload_updater.mock_calls[1][1][0] == preload_manager
        assert mock_preload_updater.mock_calls[2][0] == "().start"
        assert len(mock_preload_updater.mock_calls) == 3
        assert len(preload_manager._threads) == 2
        mock_preload_updater.reset_mock()

        # Two threads already running, do nothing
        preload_manager.perform_reload(REDIS_PRELOAD_ALL_MESSAGE)

        assert mock_preload_updater.mock_calls[0][0] == "().is_alive"
        assert mock_preload_updater.mock_calls[1][0] == "().is_alive"
        assert len(mock_preload_updater.mock_calls) == 2
        assert len(preload_manager._threads) == 2
        mock_preload_updater.reset_mock()

        # Assume all threads are dead
        for thread in preload_manager._threads:
            thread.is_alive = lambda: False

        # Reload through the redis channel. First call is ignored, inetnums are not relevant.
        Preloader().signal_reload({"inetnum"})
        Preloader().signal_reload()
        Preloader().signal_reload()
        time.sleep(0.5)

        # As all threads are considered dead, a new thread should be started
        assert mock_preload_updater.mock_calls[0][0] == ""
        assert mock_preload_updater.mock_calls[1][0] == "().start"

        # Listen() on redis is blocking, unblock it after setting terminate
        preload_manager.terminate = True
        Preloader().signal_reload()

    def test_routes_for_origins(self, mock_redis_keys):
        preloader = Preloader()
        preload_manager = PreloadStoreManager()

        # Wait for the preloader instance to start listening on pubsub
        time.sleep(1)

        preload_manager.update_route_store(
            {
                f"TEST2{REDIS_KEY_PK_SOURCE_SEPARATOR}AS65546": {"192.0.2.0/25"},
                f"TEST1{REDIS_KEY_PK_SOURCE_SEPARATOR}AS65547": {"192.0.2.128/25", "198.51.100.0/25"},
            },
            {
                f"TEST2{REDIS_KEY_PK_SOURCE_SEPARATOR}AS65547": {"2001:db8::/32"},
            },
        )
        preload_manager.signal_redis_store_updated()
        time.sleep(1)

        sources = ["TEST1", "TEST2"]
        assert preloader.routes_for_origins([], sources) == set()
        assert preloader.routes_for_origins(["AS65545"], sources) == set()
        assert preloader.routes_for_origins(["AS65546"], []) == set()
        assert preloader.routes_for_origins(["AS65546"], sources, 4) == {"192.0.2.0/25"}
        assert preloader.routes_for_origins(["AS65547"], sources, 4) == {"192.0.2.128/25", "198.51.100.0/25"}
        assert preloader.routes_for_origins(["AS65546"], sources, 6) == set()
        assert preloader.routes_for_origins(["AS65547"], sources, 6) == {"2001:db8::/32"}
        assert preloader.routes_for_origins(["AS65546"], sources) == {"192.0.2.0/25"}
        assert preloader.routes_for_origins(["AS65547"], sources) == {
            "192.0.2.128/25",
            "198.51.100.0/25",
            "2001:db8::/32",
        }
        assert preloader.routes_for_origins(["AS65547", "AS65546"], sources, 4) == {
            "192.0.2.0/25",
            "192.0.2.128/25",
            "198.51.100.0/25",
        }

        assert preloader.routes_for_origins(["AS65547", "AS65546"], ["TEST1"]) == {
            "192.0.2.128/25",
            "198.51.100.0/25",
        }
        assert preloader.routes_for_origins(["AS65547", "AS65546"], ["TEST2"]) == {
            "192.0.2.0/25",
            "2001:db8::/32",
        }

        with pytest.raises(ValueError) as ve:
            preloader.routes_for_origins(["AS65547"], [], 2)
        assert "Invalid IP version: 2" in str(ve.value)


class TestPreloadUpdater:
    def test_preload_updater(self, monkeypatch):
        mock_database_handler = Mock(spec=DatabaseHandler)
        mock_database_query = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr(
            "irrd.storage.preload.RPSLDatabaseQuery",
            lambda column_names, enable_ordering: mock_database_query,
        )
        mock_reload_lock = Mock()
        mock_preload_obj = Mock()

        mock_query_result = iter(
            [
                [
                    {
                        "ip_version": 4,
                        "ip_first": "192.0.2.0",
                        "prefix_length": 25,
                        "asn_first": 65546,
                        "source": "TEST1",
                    },
                    {
                        "ip_version": 4,
                        "ip_first": "192.0.2.128",
                        "prefix_length": 25,
                        "asn_first": 65547,
                        "source": "TEST1",
                    },
                    {
                        "ip_version": 4,
                        "ip_first": "198.51.100.0",
                        "prefix_length": 25,
                        "asn_first": 65547,
                        "source": "TEST1",
                    },
                    {
                        "ip_version": 6,
                        "ip_first": "2001:db8::",
                        "prefix_length": 32,
                        "asn_first": 65547,
                        "source": "TEST2",
                    },
                ],
                [
                    {
                        "rpsl_pk": "AS-SET1",
                        "parsed_data": {"members": ["AS65530"], "mbrs-by-ref": ["TEST-MNT"]},
                        "source": "TEST1",
                    },
                    {
                        "rpsl_pk": "AS-SET-ANY",
                        "parsed_data": {"members": ["AS65530"], "mbrs-by-ref": ["ANY"]},
                        "source": "TEST1",
                    },
                ],
                [
                    {
                        "object_class": "aut-num",
                        "parsed_data": {
                            "aut-num": "AS65531",
                            "member-of": ["AS-SET1", "AS-SET-NOT-EXIST"],
                            "mnt-by": ["TEST-MNT"],
                        },
                        "source": "TEST1",
                    },
                    {
                        "object_class": "aut-num",
                        "parsed_data": {
                            "aut-num": "AS65532",
                            "member-of": ["AS-SET-ANY"],
                            "mnt-by": ["OTHER-MNT"],
                        },
                        "source": "TEST1",
                    },
                    {
                        "object_class": "aut-num",
                        "parsed_data": {
                            "aut-num": "AS65533",
                            "member-of": ["AS-SET1"],
                            "mnt-by": ["OTHER-MNT"],
                        },
                        "source": "TEST1",
                    },
                    {
                        "object_class": "aut-num",
                        "parsed_data": {
                            "aut-num": "AS65534",
                            "member-of": "AS-SET1",
                            "mnt-by": "TEST-MNT",
                        },
                        "source": "OTHER-SOURCE",
                    },
                ],
                [
                    {
                        "rpsl_pk": "RS-SET1",
                        "parsed_data": {"members": ["192.0.2.0/25"], "mp-members": ["2001:db8:1::/48"], "mbrs-by-ref": ["TEST-MNT"],},
                        "source": "TEST1",
                    },
                ],
                [
                    {
                        "object_class": "route",
                        "parsed_data": {
                            "route": "192.0.2.128/25",
                            "member-of": ["RS-SET1"],
                            "mnt-by": ["TEST-MNT"],
                        },
                        "source": "TEST1",
                    },
                    {
                        "object_class": "route6",
                        "parsed_data": {
                            "route6": "2001:db8:2::/48",
                            "member-of": ["RS-SET1"],
                            "mnt-by": ["TEST-MNT"],
                        },
                        "source": "TEST1",
                    },
                ],
            ]
        )
        mock_database_handler.execute_query = lambda query: next(mock_query_result)
        PreloadUpdater(mock_preload_obj, mock_reload_lock).run(mock_database_handler)

        assert flatten_mock_calls(mock_reload_lock) == [["acquire", (), {}], ["release", (), {}]]
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["route", "route6"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
            ["object_classes", (["as-set"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
            ["lookup_attrs_in", (["member-of"], ["AS-SET1", "AS-SET-ANY"]), {}],
            ["object_classes", (["aut-num"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
            ["object_classes", (["route-set"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
            ["lookup_attrs_in", (["member-of"], ["RS-SET1"]), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
        ]

        assert flatten_mock_calls(mock_preload_obj) == [
            [
                "update_route_store",
                (
                    {
                        f"TEST1{REDIS_KEY_PK_SOURCE_SEPARATOR}AS65546": {"192.0.2.0/25"},
                        f"TEST1{REDIS_KEY_PK_SOURCE_SEPARATOR}AS65547": {
                            "192.0.2.128/25",
                            "198.51.100.0/25",
                        },
                    },
                    {f"TEST2{REDIS_KEY_PK_SOURCE_SEPARATOR}AS65547": {"2001:db8::/32"}},
                ),
                {},
            ],
            [
                "update_as_set_store",
                (
                    {
                        "TEST1_AS-SET-ANY": {"AS65530", "AS65532"},
                        "TEST1_AS-SET1": {"AS65530", "AS65531"},
                    },
                ),
                {},
            ],
            [
                "update_route_set_store",
                (
                    {
                        "TEST1_RS-SET1": {"192.0.2.0/25", "192.0.2.128/25", "2001:db8:1::/48", "2001:db8:2::/48"},
                    },
                ),
                {},
            ],
            ["signal_redis_store_updated", (), {}],
        ]

    def test_preload_updater_failure(self, caplog):
        mock_database_handler = Mock()
        mock_reload_lock = Mock()
        mock_preload_obj = Mock()
        PreloadUpdater(mock_preload_obj, mock_reload_lock).run(mock_database_handler)

        assert "Updating preload store failed" in caplog.text
        assert flatten_mock_calls(mock_reload_lock) == [["acquire", (), {}], ["release", (), {}]]
