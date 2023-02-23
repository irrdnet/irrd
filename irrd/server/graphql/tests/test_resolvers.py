from unittest.mock import Mock

import pytest
from graphql import GraphQLError
from IPy import IP
from starlette.requests import HTTPConnection

from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.server.query_resolver import QueryResolver
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import DatabaseOperation, JournalEntryOrigin
from irrd.storage.preload import Preloader
from irrd.storage.queries import RPSLDatabaseJournalQuery, RPSLDatabaseQuery
from irrd.utils.test_utils import flatten_mock_calls

from .. import resolvers

EXPECTED_RPSL_GRAPHQL_OUTPUT = [
    {
        "rpslPk": "192.0.2.0/25,AS65547",
        "objectClass": "route",
        "objectText": "object text\nauth: CRYPT-PW DummyValue  # Filtered for security",
        "operation": DatabaseOperation.add_or_update,
        "rpkiStatus": RPKIStatus.not_found,
        "scopefilterStatus": ScopeFilterStatus.out_scope_as,
        "routePreferenceStatus": RoutePreferenceStatus.suppressed,
        "source": "TEST1",
        "route": "192.0.2.0/25",
        "origin": "AS65547",
        "mntBy": "MNT-TEST",
        "asn": 65547,
        "asnFirst": 65547,
        "asnLast": 65547,
        "ipFirst": "192.0.2.0",
        "ipLast": "192.0.2.128",
        "prefix": "192.0.2.0/25",
        "prefixLength": 25,
    }
]

MOCK_RPSL_DB_RESULT = [
    {
        "rpsl_pk": "192.0.2.0/25,AS65547",
        "object_class": "route",
        "parsed_data": {
            "route": "192.0.2.0/25",
            "origin": ["AS65547"],
            "mnt-by": "MNT-TEST",
        },
        "ip_first": "192.0.2.0",
        "ip_last": "192.0.2.128",
        "prefix_length": 25,
        "asn_first": 65547,
        "asn_last": 65547,
        "object_text": "object text\nauth: CRYPT-PW LEuuhsBJNFV0Q",
        "rpki_status": RPKIStatus.not_found,
        "scopefilter_status": ScopeFilterStatus.out_scope_as,
        "route_preference_status": RoutePreferenceStatus.suppressed,
        "source": "TEST1",
        # only used in journal test
        "operation": DatabaseOperation.add_or_update,
        "origin": JournalEntryOrigin.auth_change,
    }
]


@pytest.fixture()
def prepare_resolver(monkeypatch):
    resolvers._collect_predicate_names = lambda info: ["asn", "prefix", "ipLast"]

    mock_database_query = Mock(spec=RPSLDatabaseQuery)
    monkeypatch.setattr(
        "irrd.server.graphql.resolvers.RPSLDatabaseQuery", lambda **kwargs: mock_database_query
    )
    mock_database_query.columns = RPSLDatabaseQuery.columns

    mock_query_resolver = Mock(spec=QueryResolver)
    monkeypatch.setattr(
        "irrd.server.graphql.resolvers.QueryResolver", lambda preloader, database_handler: mock_query_resolver
    )

    app = Mock(
        state=Mock(
            database_handler=Mock(spec=DatabaseHandler),
            preloader=Mock(spec=Preloader),
        )
    )
    app.state.database_handler.execute_query = lambda query, refresh_on_error: MOCK_RPSL_DB_RESULT

    info = Mock()
    info.context = {}
    info.field_nodes = [Mock(selection_set=Mock(selections=Mock()))]
    info.context["request"] = HTTPConnection(
        {
            "type": "http",
            "client": ("127.0.0.1", "8000"),
            "app": app,
        }
    )

    yield info, mock_database_query, mock_query_resolver


class TestGraphQLResolvers:
    def test_resolve_rpsl_objects(self, prepare_resolver, config_override):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        with pytest.raises(ValueError):
            resolvers.resolve_rpsl_objects(None, info)
        with pytest.raises(ValueError):
            resolvers.resolve_rpsl_objects(None, info, object_class="route", sql_trace=True)
        with pytest.raises(ValueError):
            resolvers.resolve_rpsl_objects(
                None, info, object_class="route", rpki_status=[RPKIStatus.not_found], sql_trace=True
            )

        # Should not raise ValueError
        resolvers.resolve_rpsl_objects(
            None, info, object_class="route", rpki_status=[RPKIStatus.invalid], sql_trace=True
        )
        mock_database_query.reset_mock()

        result = list(
            resolvers.resolve_rpsl_objects(
                None,
                info,
                sql_trace=True,
                rpsl_pk="pk",
                object_class="route",
                asn=[65550],
                text_search="text",
                rpki_status=[RPKIStatus.invalid],
                scope_filter_status=[ScopeFilterStatus.out_scope_as],
                route_preference_status=[RoutePreferenceStatus.suppressed],
                ip_exact="192.0.2.1",
                sources=["TEST1"],
                mntBy="mnt-by",
                unknownKwarg="ignored",
                record_limit=2,
            )
        )

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["limit", (2,), {}],
            ["rpsl_pks", ("pk",), {}],
            ["object_classes", ("route",), {}],
            ["asns_first", ([65550],), {}],
            ["text_search", ("text",), {}],
            ["rpki_status", ([RPKIStatus.invalid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.out_scope_as],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.suppressed],), {}],
            ["sources", (["TEST1"],), {}],
            ["lookup_attrs_in", (["mnt-by"], "mnt-by"), {}],
            ["ip_exact", (IP("192.0.2.1"),), {}],
        ]
        assert info.context["sql_trace"]

        mock_database_query.reset_mock()
        config_override({"sources_default": ["TEST1"]})
        result = list(
            resolvers.resolve_rpsl_objects(
                None,
                info,
                sql_trace=True,
                rpsl_pk="pk",
            )
        )
        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["rpsl_pks", ("pk",), {}],
            ["rpki_status", ([RPKIStatus.not_found, RPKIStatus.valid],), {}],
            ["scopefilter_status", ([ScopeFilterStatus.in_scope],), {}],
            ["route_preference_status", ([RoutePreferenceStatus.visible],), {}],
            ["sources", (["TEST1"],), {}],
        ]

    def test_strips_auth_attribute_hashes(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        rpsl_db_mntner_result = [
            {
                "object_class": "mntner",
                "parsed_data": {
                    "auth": ["CRYPT-Pw LEuuhsBJNFV0Q"],
                },
            }
        ]

        info.context["request"].app.state.database_handler.execute_query = (
            lambda query, refresh_on_error: rpsl_db_mntner_result
        )
        result = list(
            resolvers.resolve_rpsl_objects(
                None,
                info,
                sql_trace=True,
                rpsl_pk="pk",
            )
        )
        assert result == [
            {
                "objectClass": "mntner",
                "auth": ["CRYPT-Pw DummyValue  # Filtered for security"],
            }
        ]

    def test_resolve_rpsl_object_mnt_by_objs(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        mock_rpsl_object = {
            "objectClass": "route",
            "mntBy": "mntBy",
            "source": "source",
        }
        result = list(resolvers.resolve_rpsl_object_mnt_by_objs(mock_rpsl_object, info))

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", (["mntBy"],), {}],
            ["sources", (["source"],), {}],
        ]

        # Missing PK
        mock_rpsl_object = {
            "objectClass": "route",
            "source": "source",
        }
        assert not list(resolvers.resolve_rpsl_object_mnt_by_objs(mock_rpsl_object, info))

    def test_resolve_rpsl_object_adminc_objs(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        mock_rpsl_object = {
            "objectClass": "route",
            "adminC": "adminC",
            "source": "source",
        }
        result = list(resolvers.resolve_rpsl_object_adminc_objs(mock_rpsl_object, info))

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pks", (["adminC"],), {}],
            ["sources", (["source"],), {}],
        ]

    def test_resolve_rpsl_object_techc_objs(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        mock_rpsl_object = {
            "objectClass": "route",
            "techC": "techC",
            "source": "source",
        }
        result = list(resolvers.resolve_rpsl_object_techc_objs(mock_rpsl_object, info))

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["role", "person"],), {}],
            ["rpsl_pks", (["techC"],), {}],
            ["sources", (["source"],), {}],
        ]

    def test_resolve_rpsl_object_members_by_ref_objs(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        mock_rpsl_object = {
            "objectClass": "route",
            "mbrsByRef": "mbrsByRef",
            "source": "source",
        }
        result = list(resolvers.resolve_rpsl_object_members_by_ref_objs(mock_rpsl_object, info))

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["mntner"],), {}],
            ["rpsl_pks", (["mbrsByRef"],), {}],
            ["sources", (["source"],), {}],
        ]

    def test_resolve_rpsl_object_member_of_objs(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        mock_rpsl_object = {
            "objectClass": "route",
            "memberOf": "memberOf",
            "source": "source",
        }
        result = list(resolvers.resolve_rpsl_object_member_of_objs(mock_rpsl_object, info))

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["route-set"],), {}],
            ["rpsl_pks", (["memberOf"],), {}],
            ["sources", (["source"],), {}],
        ]

    def test_resolve_rpsl_object_members_objs(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        mock_rpsl_object = {
            "objectClass": "as-set",
            "members": "members",
            "source": "source",
        }
        result = list(resolvers.resolve_rpsl_object_members_objs(mock_rpsl_object, info))

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["as-set"],), {}],
            ["rpsl_pks", (["members"],), {}],
        ]
        mock_database_query.reset_mock()

        mock_rpsl_object = {
            "objectClass": "rtr-set",
            "members": "members",
            "source": "source",
        }
        result = list(resolvers.resolve_rpsl_object_members_objs(mock_rpsl_object, info))

        assert result == EXPECTED_RPSL_GRAPHQL_OUTPUT
        assert flatten_mock_calls(mock_database_query) == [
            ["object_classes", (["rtr-set"],), {}],
            ["rpsl_pks", (["members"],), {}],
        ]

    def test_resolve_rpsl_object_journal(self, prepare_resolver, monkeypatch, config_override):
        info, mock_database_query, mock_query_resolver = prepare_resolver

        mock_journal_query = Mock(spec=RPSLDatabaseJournalQuery)
        monkeypatch.setattr(
            "irrd.server.graphql.resolvers.RPSLDatabaseJournalQuery", lambda **kwargs: mock_journal_query
        )

        mock_rpsl_object = {
            "rpslPk": "pk",
            "source": "source",
        }
        with pytest.raises(GraphQLError):
            next(resolvers.resolve_rpsl_object_journal(mock_rpsl_object, info))

        config_override(
            {
                "access_lists": {"localhost": ["127.0.0.1"]},
                "sources": {"source": {"nrtm_access_list": "localhost"}},
            }
        )
        result = list(resolvers.resolve_rpsl_object_journal(mock_rpsl_object, info))
        assert len(result) == 1
        assert result[0]["origin"] == "auth_change"
        assert "CRYPT-PW DummyValue  # Filtered for security" in result[0]["objectText"]
        assert flatten_mock_calls(mock_journal_query) == [
            ["sources", (["source"],), {}],
            ["rpsl_pk", ("pk",), {}],
        ]

    def test_resolve_database_status(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver
        mock_status = {
            "SOURCE1": {"status_field": 1},
            "SOURCE2": {"status_field": 2},
        }
        mock_query_resolver.database_status = lambda sources: mock_status

        result = list(resolvers.resolve_database_status(None, info))
        assert result[0]["source"] == "SOURCE1"
        assert result[0]["statusField"] == 1
        assert result[1]["source"] == "SOURCE2"
        assert result[1]["statusField"] == 2

    def test_resolve_asn_prefixes(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver
        mock_query_resolver.routes_for_origin = lambda asn, ip_version: [f"prefix-{asn}"]

        result = list(
            resolvers.resolve_asn_prefixes(
                None,
                info,
                asns=[65550, 65551],
                ip_version=4,
            )
        )
        assert result == [
            {"asn": 65550, "prefixes": ["prefix-AS65550"]},
            {"asn": 65551, "prefixes": ["prefix-AS65551"]},
        ]
        mock_query_resolver.set_query_sources.assert_called_once()

    def test_resolve_as_set_prefixes(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver
        mock_query_resolver.routes_for_as_set = lambda set_name, ip_version, exclude_sets: [
            f"prefix-{set_name}"
        ]

        result = list(
            resolvers.resolve_as_set_prefixes(
                None,
                info,
                set_names=["as-A", "AS-B"],
                ip_version=4,
                sql_trace=True,
            )
        )
        assert sorted(result, key=str) == sorted(
            [
                {"rpslPk": "AS-A", "prefixes": ["prefix-AS-A"]},
                {"rpslPk": "AS-B", "prefixes": ["prefix-AS-B"]},
            ],
            key=str,
        )
        mock_query_resolver.set_query_sources.assert_called_once()

    def test_resolve_recursive_set_members(self, prepare_resolver):
        info, mock_database_query, mock_query_resolver = prepare_resolver
        mock_query_resolver.members_for_set_per_source = lambda set_name, exclude_sets, depth, recursive: {
            "TEST1": [f"member1-{set_name}"],
            "TEST2": [f"member2-{set_name}"],
        }

        result = list(
            resolvers.resolve_recursive_set_members(
                None,
                info,
                set_names=["as-A", "AS-B"],
                depth=4,
                sql_trace=True,
            )
        )
        assert sorted(result, key=str) == sorted(
            [
                {"rpslPk": "AS-A", "rootSource": "TEST1", "members": ["member1-AS-A"]},
                {"rpslPk": "AS-A", "rootSource": "TEST2", "members": ["member2-AS-A"]},
                {"rpslPk": "AS-B", "rootSource": "TEST1", "members": ["member1-AS-B"]},
                {"rpslPk": "AS-B", "rootSource": "TEST2", "members": ["member2-AS-B"]},
            ],
            key=str,
        )
        mock_query_resolver.set_query_sources.assert_called_once()
