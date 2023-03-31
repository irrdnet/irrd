from unittest.mock import Mock

import pytest

from irrd.rpki.status import RPKIStatus
from irrd.rpki.validators import SingleRouteROAValidator
from irrd.rpsl.rpsl_objects import RPSLMntner
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery, RPSLDatabaseSuspendedQuery
from irrd.utils.rpsl_samples import (
    SAMPLE_MNTNER,
    SAMPLE_PERSON,
    SAMPLE_ROLE,
    SAMPLE_ROUTE,
)
from irrd.utils.test_utils import flatten_mock_calls

from ..suspension import reactivate_for_mntner, suspend_for_mntner


class TestSuspension:
    def test_suspend_for_mntner(self, monkeypatch, config_override):
        mock_database_handler = Mock(spec=DatabaseHandler)
        mock_database_query = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr("irrd.updates.suspension.RPSLDatabaseQuery", mock_database_query)

        mntner = RPSLMntner(SAMPLE_MNTNER)
        query_results = iter(
            [
                # First query for suspendable objects
                # the mntner has another active mntner, but should
                # be suspended anyways. Other objects are skipped if
                # they have OTHER-MNT.
                [
                    {
                        "pk": "pk_suspend",
                        "rpsl_pk": "rpsl_pk_suspend",
                        "parsed_data": {"mnt-by": [mntner.pk(), "INACTIVE-MNT"]},
                        "object_class": "mntner",
                    },
                    {
                        "pk": "pk_skip",
                        "rpsl_pk": "rpsl_pk_skip",
                        "parsed_data": {"mnt-by": [mntner.pk(), "OTHER-MNT"]},
                        "object_class": "mntner",
                    },
                    {
                        "pk": "pk_skip2",
                        "rpsl_pk": "rpsl_pk_skip2",
                        "parsed_data": {"mnt-by": [mntner.pk(), "OTHER-MNT", "INACTIVE-MNT"]},
                        "object_class": "mntner",
                    },
                    # Verify that repeated objects are only included once
                    {
                        "pk": "pk_suspend",
                        "rpsl_pk": "rpsl_pk_suspend",
                        "parsed_data": {"mnt-by": [mntner.pk(), "INACTIVE-MNT"]},
                        "object_class": "mntner",
                    },
                ],
                # Second query for suspendable objects
                [
                    {
                        "pk": "pk_suspend2",
                        "rpsl_pk": mntner.pk(),
                        "parsed_data": {"mnt-by": ["INACTIVE-MNT"]},
                        "object_class": "mntner",
                    },
                ],
                # query for INACTIVE-MNT
                [],
                # query for OTHER-MNT:
                [{"pk": "OTHER-MNT"}],
            ]
        )
        mock_database_handler.execute_query = lambda q: next(query_results)

        with pytest.raises(ValueError) as ve:
            list(suspend_for_mntner(mock_database_handler, mntner))
        assert "authoritative" in str(ve)

        config_override({"sources": {"TEST": {"authoritative": True}}})
        results = list(suspend_for_mntner(mock_database_handler, mntner))
        assert len(results) == 2
        assert {r["pk"] for r in results} == {"pk_suspend", "pk_suspend2"}

        dh_calls = flatten_mock_calls(mock_database_handler)
        assert len(dh_calls) == 2
        assert ["suspend_rpsl_object", ("pk_suspend",), {}] in dh_calls
        assert ["suspend_rpsl_object", ("pk_suspend2",), {}] in dh_calls

        assert flatten_mock_calls(mock_database_query) == [
            ["", (), {"column_names": ["pk", "rpsl_pk", "object_class", "source", "parsed_data"]}],
            ["sources", (["TEST"],), {}],
            ["lookup_attr", ("mnt-by", "TEST-MNT"), {}],
            ["", (), {"column_names": ["pk", "rpsl_pk", "object_class", "source", "parsed_data"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["object_classes", (["mntner"],), {}],
            ["", (), {"column_names": ["pk"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("INACTIVE-MNT",), {}],
            ["object_classes", (["mntner"],), {}],
            ["first_only", (), {}],
            ["", (), {"column_names": ["pk"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("OTHER-MNT",), {}],
            ["object_classes", (["mntner"],), {}],
            ["first_only", (), {}],
        ]

        mock_database_handler.execute_query = lambda q: []
        with pytest.raises(ValueError) as ve:
            list(suspend_for_mntner(mock_database_handler, mntner))
        assert "does not exist" in str(ve)

    def test_reactivate_for_mntner(self, monkeypatch, config_override):
        mock_database_handler = Mock(spec=DatabaseHandler)
        mock_database_query = Mock(spec=RPSLDatabaseQuery)
        mock_database_suspended_query = Mock(spec=RPSLDatabaseSuspendedQuery)
        mock_scopefilter = Mock(spec=ScopeFilterValidator)
        mock_roa_valiator = Mock(spec=SingleRouteROAValidator)
        monkeypatch.setattr("irrd.updates.suspension.RPSLDatabaseQuery", mock_database_query)
        monkeypatch.setattr(
            "irrd.updates.suspension.RPSLDatabaseSuspendedQuery", mock_database_suspended_query
        )
        monkeypatch.setattr("irrd.updates.suspension.ScopeFilterValidator", lambda: mock_scopefilter)
        monkeypatch.setattr("irrd.updates.suspension.SingleRouteROAValidator", lambda dh: mock_roa_valiator)

        mntner = RPSLMntner(SAMPLE_MNTNER)
        query_results = iter(
            [
                # Check for PK conflict with live object
                [],
                # Retrieve suspended mntner
                [
                    {
                        "pk": "pk_regular_mntner",
                        "object_text": SAMPLE_MNTNER,
                        "original_created": "2021-01-01",
                    },
                ],
                # The currently suspended objects
                [
                    {
                        "pk": "pk_regular_mntner",
                        "object_text": SAMPLE_MNTNER,
                        "original_created": "2021-01-01",
                    },
                    {
                        "pk": "pk_regular_restore_route",
                        "object_text": SAMPLE_ROUTE,
                        "original_created": "2021-01-01",
                    },
                    {
                        "pk": "pk_regular_restore_person",
                        "object_text": SAMPLE_PERSON,
                        "original_created": "2021-01-01",
                    },
                    {
                        "pk": "pk_key_exists_role",
                        "object_text": SAMPLE_ROLE,
                        "original_created": "2021-01-01",
                    },
                ],
                # Check for PK conflict with live object on mntner (again, yes)
                [],
                # Check for PK conflict with live object on route
                [],
                # Check for PK conflict with live object on person
                [],
                # Check for PK conflict with live object on role
                [{"pk": "pk_regular_restore_person"}],
            ]
        )
        mock_database_handler.execute_query = lambda q: next(query_results)
        mock_scopefilter.validate_rpsl_object = lambda rpsl_obj: (ScopeFilterStatus.out_scope_as, "")
        mock_roa_valiator.validate_route = lambda prefix, asn, source: RPKIStatus.invalid

        with pytest.raises(ValueError) as ve:
            list(reactivate_for_mntner(mock_database_handler, mntner))
        assert "authoritative" in str(ve)

        config_override({"sources": {"TEST": {"authoritative": True}}})
        reactivated_objects, info_messages = list(reactivate_for_mntner(mock_database_handler, mntner))
        assert len(reactivated_objects) == 3
        assert reactivated_objects[0].pk() == mntner.pk()
        assert reactivated_objects[1].pk() == "192.0.2.0/24AS65537"
        assert reactivated_objects[2].pk() == "PERSON-TEST"
        assert info_messages == [
            "Skipping restore of object role/ROLE-TEST/TEST - an object already exists with the same key"
        ]

        assert flatten_mock_calls(mock_database_handler, flatten_objects=True) == [
            [
                "upsert_rpsl_object",
                ("mntner/TEST-MNT/TEST", "JournalEntryOrigin.suspension"),
                {"forced_created_value": "2021-01-01"},
            ],
            [
                "upsert_rpsl_object",
                ("route/192.0.2.0/24AS65537/TEST", "JournalEntryOrigin.suspension"),
                {"forced_created_value": "2021-01-01"},
            ],
            [
                "upsert_rpsl_object",
                ("person/PERSON-TEST/TEST", "JournalEntryOrigin.suspension"),
                {"forced_created_value": "2021-01-01"},
            ],
            [
                "delete_suspended_rpsl_objects",
                ({"pk_regular_mntner", "pk_regular_restore_route", "pk_regular_restore_person"},),
                {},
            ],
        ]
        assert flatten_mock_calls(mock_database_query) == [
            ["", (), {"column_names": ["pk"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["object_classes", (["mntner"],), {}],
            ["", (), {"column_names": ["pk"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("TEST-MNT",), {}],
            ["object_classes", (["mntner"],), {}],
            ["", (), {"column_names": ["pk"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("192.0.2.0/24AS65537",), {}],
            ["object_classes", (["route"],), {}],
            ["", (), {"column_names": ["pk"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("PERSON-TEST",), {}],
            ["object_classes", (["person"],), {}],
            ["", (), {"column_names": ["pk"]}],
            ["sources", (["TEST"],), {}],
            ["rpsl_pk", ("ROLE-TEST",), {}],
            ["object_classes", (["role"],), {}],
        ]

        mock_database_handler.execute_query = lambda q: []
        with pytest.raises(ValueError) as ve:
            list(reactivate_for_mntner(mock_database_handler, mntner))
        assert "not found in suspended store" in str(ve)

        mock_database_handler.execute_query = lambda q: [{"rpsl_pk": "conflicting existing mntner"}]
        with pytest.raises(ValueError) as ve:
            list(reactivate_for_mntner(mock_database_handler, mntner))
        assert "has a currently active mntner " in str(ve)
