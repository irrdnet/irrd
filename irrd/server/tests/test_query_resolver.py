import datetime
import uuid
from collections import OrderedDict
from unittest.mock import Mock

import pytest
from IPy import IP
from pytz import timezone

from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.storage.preload import Preloader, SetMembers
from irrd.utils.test_utils import flatten_mock_calls

from ..query_resolver import InvalidQueryException, QueryResolver, RouteLookupType

# Note that these mock objects are not entirely valid RPSL objects,
# as they are meant to test all the scenarios in the query resolver.
MOCK_ROUTE1 = """route:          192.0.2.0/25
descr:          description
origin:         AS65547
mnt-by:         MNT-TEST
source:         TEST1
members:        AS1,AS2
"""

MOCK_ROUTE2 = """route:          192.0.2.0/25
descr:          description
origin:         AS65544
mnt-by:         MNT-TEST
source:         TEST2
"""

MOCK_ROUTE3 = """route:          192.0.2.128/25
descr:          description
origin:         AS65545
mnt-by:         MNT-TEST
source:         TEST2
"""

MOCK_ROUTE_COMBINED = MOCK_ROUTE1 + "\n" + MOCK_ROUTE2 + "\n" + MOCK_ROUTE3.strip()


@pytest.fixture()
def prepare_resolver(monkeypatch, config_override):
    config_override(
        {
            "rpki": {"roa_source": None},
            "sources": {"TEST1": {}, "TEST2": {}},
            "source_aliases": {"ALIAS": ["TEST1", "TEST2"]},
            "sources_default": [],
        }
    )

    mock_database_handler = Mock()
    mock_database_query = Mock()
    monkeypatch.setattr(
        "irrd.server.query_resolver.RPSLDatabaseQuery",
        lambda columns=None, ordered_by_sources=True: mock_database_query,
    )
    mock_preloader = Mock(spec=Preloader)

    resolver = QueryResolver(mock_preloader, mock_database_handler)
    resolver.out_scope_filter_enabled = False
    resolver.route_preference_filter_enabled = False

    mock_query_result = [
        {
            "pk": uuid.uuid4(),
            "rpsl_pk": "192.0.2.0/25,AS65547",
            "object_class": "route",
            "parsed_data": {
                "route": "192.0.2.0/25",
                "origin": "AS65547",
                "mnt-by": "MNT-TEST",
                "source": "TEST1",
                "members": ["AS1, AS2"],
            },
            "object_text": MOCK_ROUTE1,
            "rpki_status": RPKIStatus.not_found,
            "source": "TEST1",
        },
        {
            "pk": uuid.uuid4(),
            "rpsl_pk": "192.0.2.0/25,AS65544",
            "object_class": "route",
            "parsed_data": {
                "route": "192.0.2.0/25",
                "origin": "AS65544",
                "mnt-by": "MNT-TEST",
                "source": "TEST2",
            },
            "object_text": MOCK_ROUTE2,
            "rpki_status": RPKIStatus.valid,
            "source": "TEST2",
        },
        {
            "pk": uuid.uuid4(),
            "rpsl_pk": "192.0.2.128/25,AS65545",
            "object_class": "route",
            "parsed_data": {
                "route": "192.0.2.128/25",
                "origin": "AS65545",
                "mnt-by": "MNT-TEST",
                "source": "TEST2",
            },
            "object_text": MOCK_ROUTE3,
            "rpki_status": RPKIStatus.valid,
            "source": "TEST2",
        },
    ]
    mock_database_handler.execute_query = lambda query, refresh_on_error=False: mock_query_result

    yield mock_database_query, mock_database_handler, mock_preloader, mock_query_result, resolver


class TestQueryResolver:
    def test_set_sources(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        assert resolver.source_manager.all_valid_real_sources == ["TEST1", "TEST2"]
        assert resolver.source_manager.all_valid_sources == ["TEST1", "TEST2", "ALIAS"]

        resolver.set_query_sources(None)
        assert resolver.source_manager.sources_resolved == resolver.source_manager.all_valid_real_sources

        resolver.set_query_sources(["TEST1"])
        assert resolver.source_manager.sources_resolved == ["TEST1"]
        resolver.set_query_sources(["TEST1", "ALIAS"])
        assert resolver.source_manager.sources_resolved == ["TEST1", "TEST2"]

        # With RPKI-aware mode disabled, RPKI is not a valid source
        with pytest.raises(InvalidQueryException):
            resolver.set_query_sources(["RPKI"])

    def test_default_sources(self, prepare_resolver, config_override):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        mock_dh.reset_mock()
        config_override(
            {
                "sources": {"TEST1": {}, "TEST2": {}},
                "sources_default": ["TEST2", "TEST1"],
            }
        )
        resolver = QueryResolver(mock_preloader, mock_dh)
        assert list(resolver.source_manager.sources_default) == ["TEST2", "TEST1"]

    def test_restrict_object_class(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        mock_dh.reset_mock()

        resolver.set_object_class_filter_next_query(["route"])
        result = resolver.rpsl_attribute_search("mnt-by", "MNT-TEST")
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route"],), {}],
            ["lookup_attr", ("mnt-by", "MNT-TEST"), {}],
        ]
        mock_dq.reset_mock()

        # filter should not persist
        result = resolver.rpsl_attribute_search("mnt-by", "MNT-TEST")
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["lookup_attr", ("mnt-by", "MNT-TEST"), {}],
        ]

    def test_key_lookup(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        result = resolver.key_lookup("route", "192.0.2.0/25")
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/25",), {}],
            ["first_only", (), {}],
        ]

    def test_key_lookup_with_sql_trace(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        resolver.enable_sql_trace()

        result = resolver.key_lookup("route", "192.0.2.0/25")
        assert list(result) == mock_query_result
        assert len(resolver.retrieve_sql_trace()) == 1
        assert len(resolver.retrieve_sql_trace()) == 0

    def test_limit_sources_key_lookup(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        resolver.set_query_sources(["TEST1"])
        result = resolver.key_lookup("route", "192.0.2.0/25")
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1"],), {}],
            ["object_classes", (["route"],), {}],
            ["rpsl_pk", ("192.0.2.0/25",), {}],
            ["first_only", (), {}],
        ]

    def test_text_search(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        mock_dh.reset_mock()

        result = resolver.rpsl_text_search("query")
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["text_search", ("query",), {}],
        ]

    def test_route_search_exact(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_exact", (IP("192.0.2.0/25"),), {}],
        ]
        mock_dq.reset_mock()

    def test_route_search_less_specific_one_level(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.LESS_SPECIFIC_ONE_LEVEL)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_less_specific_one_level", (IP("192.0.2.0/25"),), {}],
        ]

    def test_route_search_less_specific(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.LESS_SPECIFIC_WITH_EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_less_specific", (IP("192.0.2.0/25"),), {}],
        ]

    def test_route_search_more_specific(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.MORE_SPECIFIC_WITHOUT_EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_more_specific", (IP("192.0.2.0/25"),), {}],
        ]

    def test_route_search_exact_rpki_aware(self, prepare_resolver, config_override):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        config_override(
            {
                "sources": {"TEST1": {}, "TEST2": {}},
                "sources_default": [],
                "rpki": {"roa_source": "https://example.com/roa.json"},
            }
        )
        resolver = QueryResolver(mock_preloader, mock_dh)
        resolver.out_scope_filter_enabled = False
        resolver.route_preference_filter_enabled = False

        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2", "RPKI"],), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_exact", (IP("192.0.2.0/25"),), {}],
        ]
        mock_dq.reset_mock()

        resolver.disable_rpki_filter()
        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2", "RPKI"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_exact", (IP("192.0.2.0/25"),), {}],
        ]
        mock_dq.reset_mock()

        resolver.set_query_sources(["RPKI"])
        assert resolver.source_manager.sources_resolved == ["RPKI"]

    def test_route_search_exact_with_scopefilter(self, prepare_resolver, config_override):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        resolver.out_scope_filter_enabled = True

        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_exact", (IP("192.0.2.0/25"),), {}],
        ]
        mock_dq.reset_mock()

        resolver.disable_out_of_scope_filter()
        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_exact", (IP("192.0.2.0/25"),), {}],
        ]
        mock_dq.reset_mock()

    def test_route_search_exact_with_route_preference_filter(self, prepare_resolver, config_override):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        resolver.route_preference_filter_enabled = True

        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_exact", (IP("192.0.2.0/25"),), {}],
        ]
        mock_dq.reset_mock()

        resolver.disable_route_preference_filter()
        result = resolver.route_search(IP("192.0.2.0/25"), RouteLookupType.EXACT)
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["ip_exact", (IP("192.0.2.0/25"),), {}],
        ]
        mock_dq.reset_mock()

    def test_rpsl_attribute_search(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        result = resolver.rpsl_attribute_search("mnt-by", "MNT-TEST")
        assert list(result) == mock_query_result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["lookup_attr", ("mnt-by", "MNT-TEST"), {}],
        ]

        mock_dh.execute_query = lambda query, refresh_on_error=False: []
        with pytest.raises(InvalidQueryException):
            resolver.rpsl_attribute_search("invalid-attr", "MNT-TEST")

    def test_routes_for_origin(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_preloader.routes_for_origins = Mock(return_value={"192.0.2.0/25", "192.0.2.128/25"})

        result = resolver.routes_for_origin("AS65547", 4)
        assert result == {"192.0.2.0/25", "192.0.2.128/25"}
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            ["", (["AS65547"], ["TEST1", "TEST2"]), {"ip_version": 4}],
        ]

        mock_preloader.routes_for_origins = Mock(return_value={})
        result = resolver.routes_for_origin("AS65547", 4)
        assert result == {}
        assert not mock_dq.mock_calls

    def test_routes_for_as_set(self, prepare_resolver, monkeypatch):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        monkeypatch.setattr(
            "irrd.server.query_resolver.QueryResolver._recursive_set_resolve",
            lambda self, set_name: {"AS65547", "AS65548"},
        )

        mock_preloader.routes_for_origins = Mock(return_value=[])
        result = resolver.routes_for_as_set("AS65547", 4)
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            [
                "",
                ({"AS65547", "AS65548"}, resolver.source_manager.all_valid_real_sources),
                {"ip_version": 4},
            ],
        ]
        assert not result

        mock_preloader.routes_for_origins = Mock(return_value={"192.0.2.0/25", "192.0.2.128/25"})

        result = resolver.routes_for_as_set("AS65547")
        assert resolver._current_set_root_object_class == "as-set"
        assert result == {"192.0.2.0/25", "192.0.2.128/25"}
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            [
                "",
                ({"AS65547", "AS65548"}, resolver.source_manager.all_valid_real_sources),
                {"ip_version": None},
            ],
        ]

        assert not mock_dq.mock_calls

    def test_as_set_members(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_set_members = {
            "AS-FIRSTLEVEL": ["AS65547", "AS-FIRSTLEVEL", "AS-SECONDLEVEL", "AS-2nd-UNKNOWN"],
            "AS-SECONDLEVEL": ["AS-THIRDLEVEL", "AS65544"],
            "AS-THIRDLEVEL": ["AS65545", "AS-FIRSTLEVEL", "AS-4th-UNKNOWN"],
        }
        mock_preloader.set_members = Mock(
            side_effect=lambda set_pk, sources, object_classes: (
                SetMembers(mock_set_members.get(set_pk), "as-set") if set_pk in mock_set_members else None
            )
        )

        result = resolver.members_for_set("AS-FIRSTLEVEL", recursive=False)
        assert result == ["AS-2nd-UNKNOWN", "AS-SECONDLEVEL", "AS65547"]
        assert flatten_mock_calls(mock_preloader) == [
            ["set_members", ("AS-FIRSTLEVEL", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
        ]
        mock_preloader.reset_mock()

        result = resolver.members_for_set("AS-FIRSTLEVEL", recursive=True)
        assert result == ["AS65544", "AS65545", "AS65547"]
        assert sorted(flatten_mock_calls(mock_preloader)) == sorted(
            [
                ["set_members", ("AS-FIRSTLEVEL", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
                ["set_members", ("AS-SECONDLEVEL", ["TEST1", "TEST2"], ['as-set']), {}],
                ["set_members", ("AS-2nd-UNKNOWN", ["TEST1", "TEST2"], ['as-set']), {}],
                ["set_members", ("AS-THIRDLEVEL", ["TEST1", "TEST2"], ['as-set']), {}],
                ["set_members", ("AS-4th-UNKNOWN", ["TEST1", "TEST2"], ['as-set']), {}],
            ]
        )
        mock_preloader.reset_mock()

        result = resolver.members_for_set("AS-FIRSTLEVEL", depth=1, recursive=True)
        assert result == ["AS-2nd-UNKNOWN", "AS-SECONDLEVEL", "AS65547"]
        assert flatten_mock_calls(mock_preloader) == [
            ["set_members", ("AS-FIRSTLEVEL", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
        ]
        mock_preloader.reset_mock()

        result = resolver.members_for_set("AS-NOTEXIST", recursive=True)
        assert not result
        assert flatten_mock_calls(mock_preloader) == [
            ["set_members", ("AS-NOTEXIST", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
        ]
        mock_preloader.reset_mock()

        result = resolver.members_for_set("AS-NOTEXIST", recursive=True, root_source="ROOT")
        assert not result
        assert flatten_mock_calls(mock_preloader) == [
            ["set_members", ("AS-NOTEXIST", ["ROOT"], ['route-set', 'as-set']), {}],
        ]

    def test_route_set_members(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        mock_set_members = {
            "RS-FIRSTLEVEL": ["RS-SECONDLEVEL", "RS-2nd-UNKNOWN"],
            "RS-SECONDLEVEL": ["AS-REFERRED", "192.0.2.0/25", "192.0.2.0/26^32"],
            "AS-REFERRED": ["AS65545"],
        }
        mock_preloader.set_members = Mock(
            side_effect=lambda set_pk, sources, object_classes: (
                SetMembers(mock_set_members.get(set_pk), "route-set") if set_pk in mock_set_members else None
            )
        )
        mock_preloader.routes_for_origins = Mock(return_value=["192.0.2.128/25"])

        result = resolver.members_for_set("RS-FIRSTLEVEL", recursive=True)
        assert set(result) == {"192.0.2.0/26^32", "192.0.2.0/25", "192.0.2.128/25"}
        assert sorted(flatten_mock_calls(mock_preloader)) == sorted(
            [
                ["set_members", ("RS-FIRSTLEVEL", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
                ["set_members", ("RS-SECONDLEVEL", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
                ["set_members", ("RS-2nd-UNKNOWN", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
                ["set_members", ("AS-REFERRED", ["TEST1", "TEST2"], ['route-set', 'as-set']), {}],
                ["routes_for_origins", (["AS65545"], ["TEST1", "TEST2"]), {}],
            ]
        )

    def test_route_set_compatibility_ipv4_only_route_set_members(self, prepare_resolver, config_override):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_set_members = ["192.0.2.0/32", "2001:db8::/32", "RS-OTHER"]
        mock_preloader.set_members = Mock(
            side_effect=lambda set_pk, sources, object_classes: SetMembers(mock_set_members, "route-set")
        )

        result = resolver.members_for_set("RS-TEST", recursive=False)
        assert result == ["192.0.2.0/32", "2001:db8::/32", "RS-OTHER"]

        config_override(
            {
                "compatibility": {"ipv4_only_route_set_members": True},
            }
        )

        result = resolver.members_for_set("RS-TEST", recursive=False)
        assert result == ["192.0.2.0/32", "RS-OTHER"]

    def test_members_for_set_per_source(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_query_result = [
            {
                "rpsl_pk": "AS-TEST",
                "source": "TEST1",
            },
            {
                "rpsl_pk": "AS-TEST",
                "source": "TEST2",
            },
        ]

        mock_dh.execute_query = lambda query, refresh_on_error=False: mock_query_result

        mock_set_members_source = {
            "TEST1": ["AS65547", "AS65548"],
            "TEST2": ["AS65549"],
        }
        mock_preloader.set_members = Mock(
            side_effect=lambda set_pk, sources, object_classes: (
                SetMembers(mock_set_members_source.get(sources[0]), "as-set")
            )
        )

        result = resolver.members_for_set_per_source("AS-TEST", recursive=True)
        assert result == {"TEST1": ["AS65547", "AS65548"], "TEST2": ["AS65549"]}
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pk", ("AS-TEST",), {}],
        ]
        assert flatten_mock_calls(mock_preloader) == [
            ["set_members", ("AS-TEST", ["TEST1"], ['route-set', 'as-set']), {}],
            ["set_members", ("AS-TEST", ["TEST2"], ['route-set', 'as-set']), {}],
        ]

    def test_database_status(self, monkeypatch, prepare_resolver, config_override):
        config_override(
            {
                "rpki": {"roa_source": "http://example.com/"},
                "scopefilter": {"prefixes": ["192.0.2.0/24"]},
                "sources": {
                    "TEST1": {
                        "authoritative": True,
                        "object_class_filter": ["route"],
                        "scopefilter_excluded": True,
                        "route_preference": 200,
                    },
                    "TEST2": {"rpki_excluded": True, "keep_journal": True},
                },
                "sources_default": [],
                "source_aliases": ["TEST1"],
            }
        )
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        mock_dsq = Mock()
        monkeypatch.setattr("irrd.server.query_resolver.DatabaseStatusQuery", lambda: mock_dsq)
        monkeypatch.setattr("irrd.server.query_resolver.is_serial_synchronised", lambda dh, s: False)

        mock_query_result = [
            {
                "source": "TEST1",
                "serial_oldest_journal": 10,
                "serial_newest_journal": 10,
                "serial_last_export": 10,
                "serial_newest_mirror": 500,
                "updated": datetime.datetime(2020, 1, 1, tzinfo=timezone("UTC")),
            },
            {
                "source": "TEST2",
                "serial_oldest_journal": None,
                "serial_newest_journal": None,
                "serial_last_export": None,
                "serial_newest_mirror": 20,
                "updated": datetime.datetime(2020, 1, 1, tzinfo=timezone("UTC")),
            },
        ]
        mock_dh.execute_query = lambda query, refresh_on_error=False: mock_query_result

        result = resolver.database_status()
        expected_test1_result = (
            "TEST1",
            OrderedDict(
                [
                    ("source_type", "regular"),
                    ("authoritative", True),
                    ("object_class_filter", ["route"]),
                    ("rpki_rov_filter", True),
                    ("scopefilter_enabled", False),
                    ("route_preference", None),
                    ("local_journal_kept", False),
                    ("serial_oldest_journal", 10),
                    ("serial_newest_journal", 10),
                    ("serial_last_export", 10),
                    ("serial_newest_mirror", 500),
                    ("last_update", "2020-01-01T00:00:00+00:00"),
                    ("synchronised_serials", False),
                ]
            ),
        )
        assert result == OrderedDict(
            [
                expected_test1_result,
                (
                    "TEST2",
                    OrderedDict(
                        [
                            ("source_type", "regular"),
                            ("authoritative", False),
                            ("object_class_filter", None),
                            ("rpki_rov_filter", False),
                            ("scopefilter_enabled", True),
                            ("route_preference", None),
                            ("local_journal_kept", True),
                            ("serial_oldest_journal", None),
                            ("serial_newest_journal", None),
                            ("serial_last_export", None),
                            ("serial_newest_mirror", 20),
                            ("last_update", "2020-01-01T00:00:00+00:00"),
                            ("synchronised_serials", False),
                        ]
                    ),
                ),
                ("ALIAS", OrderedDict(source_type="alias", aliased_sources=["TEST1", "TEST2"])),
            ]
        )
        assert flatten_mock_calls(mock_dsq) == [["sources", (["TEST1", "TEST2", "ALIAS"],), {}]]
        mock_dsq.reset_mock()

        mock_query_result = mock_query_result[:1]
        result = resolver.database_status(["TEST1", "TEST-INVALID"])
        assert result == OrderedDict(
            [
                expected_test1_result,
                ("TEST-INVALID", OrderedDict([("error", "Unknown source")])),
            ]
        )
        assert flatten_mock_calls(mock_dsq) == [["sources", (["TEST1", "TEST-INVALID"],), {}]]

    def test_object_template(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver
        mock_dh.reset_mock()

        result = resolver.rpsl_object_template("aut-num")
        assert "aut-num:[mandatory][single][primary/look-upkey]" in result.replace(" ", "")
        mock_dh.reset_mock()

        with pytest.raises(InvalidQueryException):
            resolver.rpsl_object_template("does-not-exist")
