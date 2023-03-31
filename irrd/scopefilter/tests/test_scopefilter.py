from unittest.mock import Mock

import pytest
from IPy import IP

from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import RPSLDatabaseQuery
from irrd.utils.rpsl_samples import SAMPLE_AUT_NUM, SAMPLE_INETNUM, SAMPLE_ROUTE
from irrd.utils.test_utils import flatten_mock_calls

from ..status import ScopeFilterStatus
from ..validators import ScopeFilterValidator


class TestScopeFilterValidator:
    def test_validate(self, config_override):
        config_override(
            {
                "scopefilter": {
                    "asns": [
                        "23456",
                        "10-20",
                    ],
                    "prefixes": ["10/8", "192.168.0.0/24"],
                },
                "sources": {"TEST-EXCLUDED": {"scopefilter_excluded": True}},
            }
        )

        validator = ScopeFilterValidator()
        assert validator.validate("TEST", IP("192.0.2/24")) == ScopeFilterStatus.in_scope
        assert validator.validate("TEST", IP("192.168/24")) == ScopeFilterStatus.out_scope_prefix
        assert validator.validate("TEST", IP("10.2.1/24")) == ScopeFilterStatus.out_scope_prefix
        assert validator.validate("TEST", IP("192/8")) == ScopeFilterStatus.out_scope_prefix

        assert validator.validate("TEST", asn=9) == ScopeFilterStatus.in_scope
        assert validator.validate("TEST", asn=21) == ScopeFilterStatus.in_scope
        assert validator.validate("TEST", asn=20) == ScopeFilterStatus.out_scope_as
        assert validator.validate("TEST", asn=10) == ScopeFilterStatus.out_scope_as
        assert validator.validate("TEST", asn=15) == ScopeFilterStatus.out_scope_as
        assert validator.validate("TEST", asn=23456) == ScopeFilterStatus.out_scope_as

        assert validator.validate("TEST-EXCLUDED", IP("192/8")) == ScopeFilterStatus.in_scope
        assert validator.validate("TEST-EXCLUDED", asn=20) == ScopeFilterStatus.in_scope

        # Override to no filter
        config_override({})
        validator.load_filters()
        assert validator.validate("TEST", IP("192.168/24")) == ScopeFilterStatus.in_scope
        assert validator.validate("TEST", asn=20) == ScopeFilterStatus.in_scope

    def test_invalid_input(self):
        validator = ScopeFilterValidator()
        with pytest.raises(ValueError) as ve:
            validator.validate("TEST")
        assert "must be provided asn or prefix" in str(ve.value)

    def test_validate_rpsl_object(self, config_override):
        validator = ScopeFilterValidator()
        route_obj = rpsl_object_from_text(SAMPLE_ROUTE)
        assert validator.validate_rpsl_object(route_obj) == (ScopeFilterStatus.in_scope, "")
        autnum_obj = rpsl_object_from_text(SAMPLE_AUT_NUM)
        assert validator.validate_rpsl_object(autnum_obj) == (ScopeFilterStatus.in_scope, "")

        config_override(
            {
                "scopefilter": {
                    "asns": ["65537"],
                },
            }
        )
        validator.load_filters()
        result = validator.validate_rpsl_object(route_obj)
        assert result == (ScopeFilterStatus.out_scope_as, "ASN 65537 is out of scope")
        result = validator.validate_rpsl_object(autnum_obj)
        assert result == (ScopeFilterStatus.out_scope_as, "ASN 65537 is out of scope")

        config_override(
            {
                "scopefilter": {
                    "prefixes": ["192.0.2.0/32"],
                },
            }
        )
        validator.load_filters()
        result = validator.validate_rpsl_object(route_obj)
        assert result == (ScopeFilterStatus.out_scope_prefix, "prefix 192.0.2.0/24 is out of scope")

        config_override(
            {
                "scopefilter": {
                    "prefix": ["0/0"],
                },
            }
        )
        validator.load_filters()

        # Ignored object class
        result = validator.validate_rpsl_object(rpsl_object_from_text(SAMPLE_INETNUM))
        assert result == (ScopeFilterStatus.in_scope, "")

    def test_validate_all_rpsl_objects(self, config_override, monkeypatch):
        mock_dh = Mock(spec=DatabaseHandler)
        mock_dq = Mock(spec=RPSLDatabaseQuery)
        monkeypatch.setattr(
            "irrd.scopefilter.validators.RPSLDatabaseQuery",
            lambda column_names=None, enable_ordering=True: mock_dq,
        )

        config_override(
            {
                "scopefilter": {
                    "asns": [
                        "23456",
                    ],
                    "prefixes": [
                        "192.0.2.0/25",
                    ],
                },
            }
        )

        mock_query_result = iter(
            [
                [
                    {
                        # Should become in_scope
                        "pk": "192.0.2.128/25,AS65547",
                        "rpsl_pk": "192.0.2.128/25,AS65547",
                        "prefix": "192.0.2.128/25",
                        "asn_first": 65547,
                        "source": "TEST",
                        "object_class": "route",
                        "scopefilter_status": ScopeFilterStatus.out_scope_prefix,
                    },
                    {
                        # Should become out_scope_prefix
                        "pk": "192.0.2.0/25,AS65547",
                        "rpsl_pk": "192.0.2.0/25,AS65547",
                        "prefix": "192.0.2.0/25",
                        "asn_first": 65547,
                        "source": "TEST",
                        "object_class": "route",
                        "scopefilter_status": ScopeFilterStatus.in_scope,
                    },
                    {
                        # Should become out_scope_as
                        "pk": "192.0.2.128/25,AS65547",
                        "rpsl_pk": "192.0.2.128/25,AS65547",
                        "prefix": "192.0.2.128/25",
                        "asn_first": 23456,
                        "source": "TEST",
                        "object_class": "route",
                        "scopefilter_status": ScopeFilterStatus.out_scope_prefix,
                    },
                    {
                        # Should become out_scope_as
                        "pk": "AS65547",
                        "rpsl_pk": "AS65547",
                        "asn_first": 23456,
                        "source": "TEST",
                        "object_class": "aut-num",
                        "object_text": "text",
                        "scopefilter_status": ScopeFilterStatus.in_scope,
                    },
                    {
                        # Should not change
                        "pk": "192.0.2.128/25,AS65548",
                        "rpsl_pk": "192.0.2.128/25,AS65548",
                        "prefix": "192.0.2.128/25",
                        "asn_first": 65548,
                        "source": "TEST",
                        "object_class": "route",
                        "scopefilter_status": ScopeFilterStatus.in_scope,
                    },
                ],
                [
                    {
                        "pk": "192.0.2.128/25,AS65547",
                        "object_text": "text-192.0.2.128/25,AS65547",
                    },
                    {
                        "pk": "192.0.2.0/25,AS65547",
                        "object_text": "text-192.0.2.0/25,AS65547",
                    },
                    {
                        "pk": "192.0.2.128/25,AS65547",
                        "object_text": "text-192.0.2.128/25,AS65547",
                    },
                    {
                        "pk": "AS65547",
                        "object_text": "text-AS65547",
                    },
                ],
            ]
        )
        mock_dh.execute_query = lambda query: next(mock_query_result)

        validator = ScopeFilterValidator()
        result = validator.validate_all_rpsl_objects(mock_dh)
        now_in_scope, now_out_scope_as, now_out_scope_prefix = result

        assert len(now_in_scope) == 1
        assert len(now_out_scope_as) == 2
        assert len(now_out_scope_prefix) == 1

        assert now_in_scope[0]["rpsl_pk"] == "192.0.2.128/25,AS65547"
        assert now_in_scope[0]["old_status"] == ScopeFilterStatus.out_scope_prefix
        assert now_in_scope[0]["object_text"] == "text-192.0.2.128/25,AS65547"

        assert now_out_scope_as[0]["rpsl_pk"] == "192.0.2.128/25,AS65547"
        assert now_out_scope_as[0]["old_status"] == ScopeFilterStatus.out_scope_prefix
        assert now_out_scope_as[0]["object_text"] == "text-192.0.2.128/25,AS65547"
        assert now_out_scope_as[1]["rpsl_pk"] == "AS65547"
        assert now_out_scope_as[1]["old_status"] == ScopeFilterStatus.in_scope
        assert now_out_scope_as[1]["object_text"] == "text-AS65547"

        assert now_out_scope_prefix[0]["rpsl_pk"] == "192.0.2.0/25,AS65547"
        assert now_out_scope_prefix[0]["old_status"] == ScopeFilterStatus.in_scope
        assert now_out_scope_prefix[0]["object_text"] == "text-192.0.2.0/25,AS65547"

        assert flatten_mock_calls(mock_dq) == [
            ["object_classes", (["route", "route6", "aut-num"],), {}],
            [
                "pks",
                (["192.0.2.128/25,AS65547", "192.0.2.0/25,AS65547", "192.0.2.128/25,AS65547", "AS65547"],),
                {},
            ],
        ]
