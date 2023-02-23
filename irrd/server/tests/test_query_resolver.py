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
from irrd.storage.preload import Preloader
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

        resolver.set_query_sources(None)
        assert resolver.sources == resolver.all_valid_sources

        resolver.set_query_sources(["TEST1"])
        assert resolver.sources == ["TEST1"]

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
        assert list(resolver.sources_default) == ["TEST2", "TEST1"]

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
        assert resolver.sources == ["RPKI"]

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
            ["", ({"AS65547", "AS65548"}, resolver.all_valid_sources), {"ip_version": 4}],
        ]
        assert not result

        mock_preloader.routes_for_origins = Mock(return_value={"192.0.2.0/25", "192.0.2.128/25"})

        result = resolver.routes_for_as_set("AS65547")
        assert resolver._current_set_root_object_class == "as-set"
        assert result == {"192.0.2.0/25", "192.0.2.128/25"}
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            ["", ({"AS65547", "AS65548"}, resolver.all_valid_sources), {"ip_version": None}],
        ]

        assert not mock_dq.mock_calls

    def test_as_set_members(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_query_result1 = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "AS-FIRSTLEVEL",
                "parsed_data": {
                    "as-set": "AS-FIRSTLEVEL",
                    "members": ["AS65547", "AS-FIRSTLEVEL", "AS-SECONDLEVEL", "AS-2nd-UNKNOWN"],
                },
                "object_text": "text",
                "object_class": "as-set",
                "source": "TEST1",
            },
        ]
        mock_query_result2 = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "AS-SECONDLEVEL",
                "parsed_data": {"as-set": "AS-SECONDLEVEL", "members": ["AS-THIRDLEVEL", "AS65544"]},
                "object_text": "text",
                "object_class": "as-set",
                "source": "TEST1",
            },
            {  # Should be ignored - only the first result per PK is accepted.
                "pk": uuid.uuid4(),
                "rpsl_pk": "AS-SECONDLEVEL",
                "parsed_data": {"as-set": "AS-SECONDLEVEL", "members": ["AS-IGNOREME"]},
                "object_text": "text",
                "object_class": "as-set",
                "source": "TEST2",
            },
        ]
        mock_query_result3 = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "AS-THIRDLEVEL",
                # Refers back to the first as-set to test infinite recursion issues
                "parsed_data": {
                    "as-set": "AS-THIRDLEVEL",
                    "members": ["AS65545", "AS-FIRSTLEVEL", "AS-4th-UNKNOWN"],
                },
                "object_text": "text",
                "object_class": "as-set",
                "source": "TEST2",
            },
        ]
        mock_dh.execute_query = lambda query, refresh_on_error=False: iter(mock_query_result1)

        result = resolver.members_for_set("AS-FIRSTLEVEL", recursive=False)
        assert result == ["AS-2nd-UNKNOWN", "AS-SECONDLEVEL", "AS65547"]
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"AS-FIRSTLEVEL"},), {}],
        ]
        mock_dq.reset_mock()

        mock_query_iterator = iter(
            [mock_query_result1, mock_query_result2, mock_query_result3, [], mock_query_result1, []]
        )
        mock_dh.execute_query = lambda query, refresh_on_error=False: iter(next(mock_query_iterator))

        result = resolver.members_for_set("AS-FIRSTLEVEL", recursive=True)
        assert result == ["AS65544", "AS65545", "AS65547"]
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"AS-FIRSTLEVEL"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set"],), {}],
            ["rpsl_pks", ({"AS-2nd-UNKNOWN", "AS-SECONDLEVEL"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set"],), {}],
            ["rpsl_pks", ({"AS-THIRDLEVEL"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set"],), {}],
            ["rpsl_pks", ({"AS-4th-UNKNOWN"},), {}],
        ]
        mock_dq.reset_mock()

        result = resolver.members_for_set("AS-FIRSTLEVEL", depth=1, recursive=True)
        assert result == ["AS-2nd-UNKNOWN", "AS-SECONDLEVEL", "AS65547"]
        mock_dq.reset_mock()

        mock_dh.execute_query = lambda query, refresh_on_error=False: iter([])
        result = resolver.members_for_set("AS-NOTEXIST", recursive=True)
        assert not result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"AS-NOTEXIST"},), {}],
        ]
        mock_dq.reset_mock()

        mock_dh.execute_query = lambda query, refresh_on_error=False: iter([])
        result = resolver.members_for_set("AS-NOTEXIST", recursive=True, root_source="ROOT")
        assert not result
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"AS-NOTEXIST"},), {}],
            ["sources", (["ROOT"],), {}],
        ]

    def test_route_set_members(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_query_result1 = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "RS-FIRSTLEVEL",
                "parsed_data": {"as-set": "RS-FIRSTLEVEL", "members": ["RS-SECONDLEVEL", "RS-2nd-UNKNOWN"]},
                "object_text": "text",
                "object_class": "route-set",
                "source": "TEST1",
            },
        ]
        mock_query_result2 = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "RS-SECONDLEVEL",
                "parsed_data": {
                    "as-set": "RS-SECONDLEVEL",
                    "members": ["AS-REFERRED", "192.0.2.0/25", "192.0.2.0/26^32"],
                },
                "object_text": "text",
                "object_class": "route-set",
                "source": "TEST1",
            },
        ]
        mock_query_result3 = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "AS-REFERRED",
                "parsed_data": {"as-set": "AS-REFERRED", "members": ["AS65545"]},
                "object_text": "text",
                "object_class": "as-set",
                "source": "TEST2",
            },
        ]
        mock_query_iterator = iter([mock_query_result1, mock_query_result2, mock_query_result3, []])
        mock_dh.execute_query = lambda query, refresh_on_error=False: iter(next(mock_query_iterator))
        mock_preloader.routes_for_origins = Mock(return_value=["192.0.2.128/25"])

        result = resolver.members_for_set("RS-FIRSTLEVEL", recursive=True)
        assert set(result) == {"192.0.2.0/26^32", "192.0.2.0/25", "192.0.2.128/25"}
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"RS-FIRSTLEVEL"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"RS-SECONDLEVEL", "RS-2nd-UNKNOWN"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"AS-REFERRED"},), {}],
        ]

    def test_as_route_set_mbrs_by_ref(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_query_result1 = [
            {
                # This route-set is intentionally misnamed RRS, as invalid names occur in real life.
                "pk": uuid.uuid4(),
                "rpsl_pk": "RRS-TEST",
                "parsed_data": {
                    "route-set": "RRS-TEST",
                    "members": ["192.0.2.0/32"],
                    "mp-members": ["2001:db8::/32"],
                    "mbrs-by-ref": ["MNT-TEST"],
                },
                "object_text": "text",
                "object_class": "route-set",
                "source": "TEST1",
            },
        ]
        mock_query_result2 = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "192.0.2.0/24,AS65544",
                "parsed_data": {
                    "route": "192.0.2.0/24",
                    "member-of": "rrs-test",
                    "mnt-by": ["FOO", "MNT-TEST"],
                },
                "object_text": "text",
                "object_class": "route",
                "source": "TEST1",
            },
        ]
        mock_query_iterator = iter([mock_query_result1, mock_query_result2, [], [], []])
        mock_dh.execute_query = lambda query, refresh_on_error=False: iter(next(mock_query_iterator))

        result = resolver.members_for_set("RRS-TEST", recursive=True)
        assert result == ["192.0.2.0/24", "192.0.2.0/32", "2001:db8::/32"]
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"RRS-TEST"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["lookup_attrs_in", (["member-of"], ["RRS-TEST"]), {}],
            ["lookup_attrs_in", (["mnt-by"], ["MNT-TEST"]), {}],
        ]
        mock_dq.reset_mock()

        # Disable maintainer check
        mock_query_result1[0]["parsed_data"]["mbrs-by-ref"] = ["ANY"]
        mock_query_iterator = iter([mock_query_result1, mock_query_result2, [], [], []])
        result = resolver.members_for_set("RRS-TEST", recursive=True)
        assert result == ["192.0.2.0/24", "192.0.2.0/32", "2001:db8::/32"]
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"RRS-TEST"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["route", "route6"],), {}],
            ["lookup_attrs_in", (["member-of"], ["RRS-TEST"]), {}],
        ]

    def test_route_set_compatibility_ipv4_only_route_set_members(self, prepare_resolver, config_override):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_query_result = [
            {
                "pk": uuid.uuid4(),
                "rpsl_pk": "RS-TEST",
                "parsed_data": {
                    "route-set": "RS-TEST",
                    "members": ["192.0.2.0/32"],
                    "mp-members": ["192.0.2.1/32", "2001:db8::/32", "RS-OTHER"],
                },
                "object_text": "text",
                "object_class": "route-set",
                "source": "TEST1",
            },
        ]
        mock_dh.execute_query = lambda query, refresh_on_error=False: mock_query_result

        result = resolver.members_for_set("RS-TEST", recursive=False)
        assert result == ["192.0.2.0/32", "192.0.2.1/32", "2001:db8::/32", "RS-OTHER"]

        config_override(
            {
                "compatibility": {"ipv4_only_route_set_members": True},
            }
        )

        result = resolver.members_for_set("RS-TEST", recursive=False)
        assert result == ["192.0.2.0/32", "192.0.2.1/32", "RS-OTHER"]

    def test_members_for_set_per_source(self, prepare_resolver):
        mock_dq, mock_dh, mock_preloader, mock_query_result, resolver = prepare_resolver

        mock_query_result = iter(
            [
                [
                    {
                        "rpsl_pk": "AS-TEST",
                        "source": "TEST1",
                    },
                    {
                        "rpsl_pk": "AS-TEST",
                        "source": "TEST2",
                    },
                ],
                [
                    {
                        "pk": uuid.uuid4(),
                        "rpsl_pk": "AS-TEST",
                        "parsed_data": {"as-set": "AS-TEST", "members": ["AS65547", "AS-SECONDLEVEL"]},
                        "object_text": "text",
                        "object_class": "as-set",
                        "source": "TEST1",
                    },
                ],
                [
                    {
                        "pk": uuid.uuid4(),
                        "rpsl_pk": "AS-SECONDLEVEL",
                        "parsed_data": {"as-set": "AS-SECONDLEVEL", "members": ["AS65548"]},
                        "object_text": "text",
                        "object_class": "as-set",
                        "source": "TEST1",
                    },
                ],
                [
                    {
                        "pk": uuid.uuid4(),
                        "rpsl_pk": "AS-TEST",
                        "parsed_data": {"as-set": "AS-TEST", "members": ["AS65549"]},
                        "object_text": "text",
                        "object_class": "as-set",
                        "source": "TEST2",
                    },
                ],
                [],
            ]
        )

        mock_dh.execute_query = lambda query, refresh_on_error=False: next(mock_query_result)

        result = resolver.members_for_set_per_source("AS-TEST", recursive=True)
        assert result == {"TEST1": ["AS65547", "AS65548"], "TEST2": ["AS65549"]}
        assert flatten_mock_calls(mock_dq) == [
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pk", ("AS-TEST",), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"AS-TEST"},), {}],
            ["sources", (["TEST1"],), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set"],), {}],
            ["rpsl_pks", ({"AS-SECONDLEVEL"},), {}],
            ["sources", (["TEST1", "TEST2"],), {}],
            ["object_classes", (["as-set", "route-set"],), {}],
            ["rpsl_pks", ({"AS-TEST"},), {}],
            ["sources", (["TEST2"],), {}],
        ]
        mock_dq.reset_mock()

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
            ]
        )
        assert flatten_mock_calls(mock_dsq) == [["sources", (["TEST1", "TEST2"],), {}]]
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
