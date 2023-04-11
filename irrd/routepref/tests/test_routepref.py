import itertools

from IPy import IP

from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.test_utils import MockDatabaseHandler

from ..routepref import RoutePreferenceValidator, update_route_preference_status
from ..status import RoutePreferenceStatus


def test_route_preference_validator(config_override):
    config_override(
        {
            "sources": {
                "SRC-HIGH-A": {"route_object_preference": 900},
                "SRC-HIGH-B": {"route_object_preference": 900},
                "SRC-LOWEST": {"route_object_preference": 100},
                "SRC-LOW": {"route_object_preference": 200},
            }
        }
    )
    route_objects = [
        {
            "source": "SRC-HIGH-A",
            "prefix": "192.0.0.0/23",
            "pk": "route-A",
            "route_preference_status": RoutePreferenceStatus.suppressed,
        },
        {
            "source": "SRC-HIGH-B",
            "prefix": "192.0.0.0/24",
            "pk": "route-B",
            "route_preference_status": RoutePreferenceStatus.suppressed,
        },
        {
            "source": "SRC-LOWEST",
            "prefix": "192.0.0.0/23",
            "pk": "route-C",
            "route_preference_status": RoutePreferenceStatus.visible,
        },
        {
            "source": "SRC-LOW",
            "prefix": "192.0.0.0/22",
            "pk": "route-D",
            "route_preference_status": RoutePreferenceStatus.visible,
        },
        {
            "source": "SRC-LOW",
            "prefix": "192.0.1.0/24",
            "pk": "route-E",
            "route_preference_status": RoutePreferenceStatus.visible,
        },
        {
            "source": "SRC-LOWEST",
            "prefix": "192.0.3.0/24",
            "pk": "route-F",
            "route_preference_status": RoutePreferenceStatus.visible,
        },
        {
            "source": "SRC-NOPREF",
            "prefix": "192.0.0.0/24",
            "pk": "route-G",
            "route_preference_status": RoutePreferenceStatus.suppressed,
        },
        {
            "source": "SRC-NOPREF",
            "prefix": "192.0.0.0/32",
            "pk": "route-H",
            "route_preference_status": RoutePreferenceStatus.visible,
        },
        {
            # No overlaps
            "source": "SRC-LOWEST",
            "prefix": "198.51.100.0/24",
            "pk": "route-I",
            "route_preference_status": RoutePreferenceStatus.suppressed,
        },
    ]

    validator = RoutePreferenceValidator(route_objects)
    to_be_visible, to_be_suppressed = validator.validate_known_routes()
    assert validator.excluded_currently_suppressed == ["route-G"]
    assert to_be_visible == ["route-A", "route-B", "route-I"]
    assert to_be_suppressed == ["route-D", "route-C", "route-E", "route-F"]

    config_override(
        {
            "sources": {
                "SRC-HIGH-A": {},
                "SRC-HIGH-B": {},
                "SRC-LOWEST": {},
                "SRC-LOW": {},
            }
        }
    )

    validator = RoutePreferenceValidator(route_objects)
    to_be_visible, to_be_suppressed = validator.validate_known_routes()
    assert validator.excluded_currently_suppressed == ["route-A", "route-B", "route-G", "route-I"]
    assert to_be_suppressed == []


def test_update_route_preference_status(config_override, monkeypatch):
    config_override(
        {
            "sources": {
                "SRC-HIGH": {"route_object_preference": 900},
                "SRC-LOW": {"route_object_preference": 200},
            }
        }
    )
    route_objects = [
        {
            "source": "SRC-HIGH",
            "prefix": "192.0.0.0/23",
            "pk": "route-A",
            "route_preference_status": RoutePreferenceStatus.suppressed,
        },
        {
            "source": "SRC-LOW",
            "prefix": "192.0.0.0/22",
            "pk": "route-D",
            "route_preference_status": RoutePreferenceStatus.visible,
        },
    ]

    object_classes = ["route", "route6"]
    expected_columns = ["prefix", "source", "pk", "route_preference_status"]
    enrich_columns = [
        "pk",
        "object_text",
        "rpsl_pk",
        "source",
        "prefix",
        "origin",
        "object_class",
        "object_text",
        "scopefilter_status",
        "rpki_status",
    ]

    # First, test without a filter for specific prefixes.
    mock_dh = MockDatabaseHandler()
    mock_dh.reset_mock()
    mock_dh.query_responses[RPSLDatabaseQuery] = iter(route_objects)
    update_route_preference_status(mock_dh)
    assert mock_dh.queries == [
        RPSLDatabaseQuery(column_names=expected_columns, ordered_by_sources=False).object_classes(
            object_classes
        ),
        RPSLDatabaseQuery(
            enrich_columns,
            enable_ordering=False,
        ).pks(["route-A"]),
        RPSLDatabaseQuery(
            enrich_columns,
            enable_ordering=False,
        ).pks(["route-D"]),
    ]
    assert mock_dh.other_calls == [
        (
            "update_route_preference_status",
            {"rpsl_objs_now_visible": [], "rpsl_objs_now_suppressed": []},
        )
    ]

    # Second, test with a filter for specific prefixes
    mock_dh.reset_mock()
    mock_dh.query_responses[RPSLDatabaseQuery] = iter(route_objects)
    update_route_preference_status(mock_dh, [IP("192.0.0.0/23"), IP("198.51.100.0/24")])
    assert mock_dh.queries == [
        RPSLDatabaseQuery(column_names=expected_columns, ordered_by_sources=False)
        .object_classes(object_classes)
        .ip_any(IP("192.0.0.0/23")),
        RPSLDatabaseQuery(column_names=expected_columns, ordered_by_sources=False)
        .object_classes(object_classes)
        .ip_any(IP("198.51.100.0/24")),
        RPSLDatabaseQuery(
            enrich_columns,
            enable_ordering=False,
        ).pks(["route-A"]),
        RPSLDatabaseQuery(
            enrich_columns,
            enable_ordering=False,
        ).pks(["route-D"]),
    ]
    assert mock_dh.other_calls == [
        (
            "update_route_preference_status",
            {"rpsl_objs_now_visible": [], "rpsl_objs_now_suppressed": []},
        )
    ]

    # Finally, test with a "large" set of prefixes
    monkeypatch.setattr("irrd.routepref.routepref.MAX_FILTER_PREFIX_LEN", 5)
    mock_dh.reset_mock()
    mock_dh.query_responses[RPSLDatabaseQuery] = iter(route_objects)
    ip = IP("192.0.0.0/23")
    filter_prefixes = list(itertools.chain.from_iterable(itertools.repeat(ip, 10)))
    update_route_preference_status(mock_dh, filter_prefixes)
    assert mock_dh.queries == [
        RPSLDatabaseQuery(column_names=expected_columns, ordered_by_sources=False).object_classes(
            object_classes
        ),
        RPSLDatabaseQuery(
            enrich_columns,
            enable_ordering=False,
        ).pks(["route-A"]),
        RPSLDatabaseQuery(
            enrich_columns,
            enable_ordering=False,
        ).pks(["route-D"]),
    ]
    assert mock_dh.other_calls == [
        (
            "update_route_preference_status",
            {"rpsl_objs_now_visible": [], "rpsl_objs_now_suppressed": []},
        )
    ]
