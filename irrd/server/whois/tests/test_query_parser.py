import uuid
from unittest.mock import Mock

import pytest
from IPy import IP

from irrd.mirroring.nrtm_generator import NRTMGeneratorException
from irrd.rpki.status import RPKIStatus
from irrd.server.query_resolver import (
    InvalidQueryException,
    QueryResolver,
    RouteLookupType,
)
from irrd.storage.database_handler import DatabaseHandler
from irrd.utils.test_utils import flatten_mock_calls

from ..query_parser import WhoisQueryParser
from ..query_response import WhoisQueryResponseMode, WhoisQueryResponseType

# Note that these mock objects are not entirely valid RPSL objects,
# as they are meant to test all the scenarios in the query parser.
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
MOCK_ROUTE_COMBINED_WITH_RPKI = (
    MOCK_ROUTE1
    + "rpki-ov-state:  not_found # No ROAs found, or RPKI validation not enabled for source\n\n"
    + MOCK_ROUTE2
    + "rpki-ov-state:  valid\n\n"
    + MOCK_ROUTE3
    + "rpki-ov-state:  valid"
)


MOCK_ROUTE_COMBINED_KEY_FIELDS = """route: 192.0.2.0/25
origin: AS65547
members: AS1, AS2

route: 192.0.2.0/25
origin: AS65544

route: 192.0.2.128/25
origin: AS65545"""

MOCK_DATABASE_RESPONSE = [
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


@pytest.fixture()
def prepare_parser(monkeypatch, config_override):
    mock_query_resolver = Mock(spec=QueryResolver)
    mock_query_resolver.rpki_aware = False
    monkeypatch.setattr(
        "irrd.server.whois.query_parser.QueryResolver",
        lambda preloader, database_handler: mock_query_resolver,
    )

    mock_dh = Mock(spec=DatabaseHandler)
    parser = WhoisQueryParser("127.0.0.1", "127.0.0.1:99999", None, mock_dh)
    yield mock_query_resolver, mock_dh, parser


class TestWhoisQueryParserRIPE:
    """Test RIPE-style queries"""

    def test_invalid_flag(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("-e foo")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "Unrecognised flag/search: e"

    def test_null_bytes(self, prepare_parser):  # #581
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("\x00 foo")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Queries may not contain null bytes"

    def test_keepalive(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("-k")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert parser.multiple_command_mode

    def test_route_search_exact(self, prepare_parser):
        # This also tests the recursion disabled flag, which should have no effect,
        # and the reset of the key fields only flag.
        # It also tests the handling of extra spaces.
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        parser.key_fields_only = True
        response = parser.handle_query("-r  -x   192.0.2.0/25")
        assert not parser.key_fields_only

        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.EXACT,
        )
        mock_query_resolver.reset_mock()

        mock_query_resolver.route_search = Mock(return_value=[])
        response = parser.handle_query("-x 192.0.2.0/32")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert response.remove_auth_hashes

    def test_route_search_less_specific_one_level(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("-l 192.0.2.0/25")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.LESS_SPECIFIC_ONE_LEVEL,
        )

    def test_route_search_less_specific(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("-L 192.0.2.0/25")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.LESS_SPECIFIC_WITH_EXACT,
        )

    def test_route_search_more_specific(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("-M 192.0.2.0/25")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.MORE_SPECIFIC_WITHOUT_EXACT,
        )

    def test_route_search_invalid_parameter(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("-x not-a-prefix")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "Invalid input for route search: not-a-prefix"

    def test_inverse_attribute_search(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.rpsl_attribute_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("-i mnt-by MNT-TEST")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.rpsl_attribute_search.assert_called_once_with("mnt-by", "MNT-TEST")

        mock_query_resolver.rpsl_attribute_search = Mock(return_value=[])
        response = parser.handle_query("-i mnt-by MNT-NOT-EXISTING")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result

    def test_sources_list(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.set_query_sources = Mock()

        response = parser.handle_query("-s test1")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        mock_query_resolver.rpsl_attribute_search.set_query_sources(["TEST1"])

    def test_sources_all(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.set_query_sources = Mock()

        response = parser.handle_query("-a")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        mock_query_resolver.rpsl_attribute_search.set_query_sources(None)

    def test_restrict_object_class(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.set_object_class_filter_next_query = Mock()
        mock_query_resolver.rpsl_attribute_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("-T route -i mnt-by MNT-TEST")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert response.remove_auth_hashes
        mock_query_resolver.rpsl_attribute_search.set_object_class_filter_next_query(["route"])
        mock_query_resolver.rpsl_attribute_search.rpsl_attribute_search("mnt-by", "MNT-TEST")

    def test_object_template(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.rpsl_object_template = Mock(return_value="<template>")

        response = parser.handle_query("-t aut-num")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "<template>"
        mock_query_resolver.rpsl_attribute_search.rpsl_object_template("aut-num")

    def test_key_fields_only(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("-K -x 192.0.2.0/25")
        assert parser.key_fields_only

        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED_KEY_FIELDS
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.EXACT,
        )

        mock_query_resolver.route_search = Mock(return_value=[])
        response = parser.handle_query("-x 192.0.2.0/32")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result

    def test_user_agent(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("-V user-agent")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result

    def test_nrtm_request(self, prepare_parser, monkeypatch, config_override):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.all_valid_sources = ["TEST1"]

        mock_nrg = Mock()
        monkeypatch.setattr("irrd.server.whois.query_parser.NRTMGenerator", lambda: mock_nrg)
        mock_nrg.generate = (
            lambda source, version, serial_start, serial_end, dh, remove_auth_hashes: (
                f"{source}/{version}/{serial_start}/{serial_end}/{remove_auth_hashes}"
            )
        )

        response = parser.handle_query("-g TEST1:3:1-5")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "Access denied"

        config_override(
            {
                "sources": {
                    "TEST1": {"nrtm_access_list": "nrtm_access"},
                },
                "access_lists": {
                    "nrtm_access": ["0/0", "0::/0"],
                },
                "sources_default": [],
            }
        )

        response = parser.handle_query("-g TEST1:3:1-5")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "TEST1/3/1/5/True"
        assert not response.remove_auth_hashes

        response = parser.handle_query("-g TEST1:3:1-LAST")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "TEST1/3/1/None/True"
        assert not response.remove_auth_hashes

        config_override(
            {
                "sources": {
                    "TEST1": {"nrtm_access_list_unfiltered": "nrtm_access"},
                },
                "access_lists": {
                    "nrtm_access": ["0/0", "0::/0"],
                },
                "sources_default": [],
            }
        )
        response = parser.handle_query("-g TEST1:3:1-LAST")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "TEST1/3/1/None/False"
        assert not response.remove_auth_hashes

        config_override(
            {
                "sources": {
                    "TEST1": {
                        "nrtm_access_list": "nrtm_access",
                        "nrtm_access_list_unfiltered": "nrtm_access",
                    },
                },
                "access_lists": {
                    "nrtm_access": ["0/0", "0::/0"],
                },
                "sources_default": [],
            }
        )
        response = parser.handle_query("-g TEST1:3:1-LAST")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "TEST1/3/1/None/False"
        assert not response.remove_auth_hashes

        response = parser.handle_query("-g TEST1:9:1-LAST")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "Invalid NRTM version: 9"

        response = parser.handle_query("-g TEST1:1:1-LAST:foo")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "Invalid parameter: must contain three elements"

        response = parser.handle_query("-g UNKNOWN:1:1-LAST")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "Unknown source: UNKNOWN"

        for invalid_range in ["1", "LAST-1", "LAST", "1-last"]:
            response = parser.handle_query(f"-g TEST1:3:{invalid_range}")
            assert response.response_type == WhoisQueryResponseType.ERROR_USER
            assert response.mode == WhoisQueryResponseMode.RIPE
            assert response.result == f"Invalid serial range: {invalid_range}"

        mock_nrg.generate = Mock(side_effect=NRTMGeneratorException("expected-test-error"))
        response = parser.handle_query("-g TEST1:3:1-5")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "expected-test-error"

    def test_text_search(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.rpsl_text_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("query")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert response.remove_auth_hashes
        mock_query_resolver.rpsl_text_search.assert_called_once_with("query")

    def test_missing_argument(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        missing_arg_queries = ["-i ", "-i mnt-by ", "-s", "-T", "-t", "-V", "-x   "]
        for query in missing_arg_queries:
            response = parser.handle_query(query)
            assert response.response_type == WhoisQueryResponseType.ERROR_USER
            assert response.mode == WhoisQueryResponseMode.RIPE
            assert response.result == "Missing argument for flag/search: " + query[1]

    def test_exception_handling(self, prepare_parser, caplog):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.rpsl_text_search = Mock(side_effect=Exception("test-error"))

        response = parser.handle_query("foo")
        assert response.response_type == WhoisQueryResponseType.ERROR_INTERNAL
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "An internal error occurred while processing this query."

        assert "An exception occurred while processing whois query" in caplog.text
        assert "test-error" in caplog.text

        mock_query_resolver.rpsl_text_search = Mock(side_effect=InvalidQueryException("user error"))

        response = parser.handle_query("foo")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == "user error"


class TestWhoisQueryParserIRRD:
    """Test IRRD-style queries"""

    def test_invalid_command(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("!")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Missing IRRD command"

        response = parser.handle_query("!e")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Unrecognised command: e"

    def test_parameter_required(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        queries_with_parameter = list("tg6ijmnors")
        for query in queries_with_parameter:
            response = parser.handle_query(f"!{query}")
            assert response.response_type == WhoisQueryResponseType.ERROR_USER
            assert response.mode == WhoisQueryResponseMode.IRRD
            assert response.result == f"Missing parameter for {query} query"

    def test_multiple_command_mode(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("!!")
        assert response.response_type == WhoisQueryResponseType.NO_RESPONSE
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert parser.multiple_command_mode

    def test_update_timeout(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("!t300")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert parser.timeout == 300

        for invalid_value in ["foo", "-5", "1001"]:
            response = parser.handle_query(f"!t{invalid_value}")
            assert response.response_type == WhoisQueryResponseType.ERROR_USER
            assert response.mode == WhoisQueryResponseMode.IRRD
            assert response.result == f"Invalid value for timeout: {invalid_value}"

        assert parser.timeout == 300

    def test_routes_for_origin(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.routes_for_origin = Mock(return_value=["192.0.2.0/25", "192.0.2.128/25"])

        response = parser.handle_query("!gas065547")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "192.0.2.0/25 192.0.2.128/25"
        mock_query_resolver.routes_for_origin.assert_called_once_with("AS65547", 4)

        mock_query_resolver.routes_for_origin = Mock(return_value=["2001:db8::/32"])
        response = parser.handle_query("!6as065547")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "2001:db8::/32"
        mock_query_resolver.routes_for_origin.assert_called_once_with("AS65547", 6)

        mock_query_resolver.routes_for_origin = Mock(return_value=[])
        response = parser.handle_query("!gAS65547")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

        response = parser.handle_query("!6AS65547")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_routes_for_origin_invalid(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("!gASfoobar")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Invalid AS number ASFOOBAR: number part is not numeric"

    def test_handle_irrd_routes_for_as_set(self, prepare_parser, monkeypatch):
        mock_query_resolver, mock_dh, parser = prepare_parser

        for parameter in ["", "4", "6"]:
            response = parser.handle_query(f"!a{parameter}")
            assert response.response_type == WhoisQueryResponseType.ERROR_USER
            assert response.mode == WhoisQueryResponseMode.IRRD
            assert response.result == "Missing required set name for A query"

        mock_query_resolver.routes_for_as_set = Mock(return_value=["192.0.2.0/25", "192.0.2.128/25"])

        response = parser.handle_query("!aAS-FOO")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "192.0.2.0/25 192.0.2.128/25"
        mock_query_resolver.routes_for_as_set.assert_called_once_with("AS-FOO", None)
        mock_query_resolver.routes_for_as_set.reset_mock()

        response = parser.handle_query("!a4AS-FOO")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "192.0.2.0/25 192.0.2.128/25"
        mock_query_resolver.routes_for_as_set.assert_called_once_with("AS-FOO", 4)
        mock_query_resolver.routes_for_as_set.reset_mock()

        response = parser.handle_query("!a6AS-FOO")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "192.0.2.0/25 192.0.2.128/25"
        mock_query_resolver.routes_for_as_set.assert_called_once_with("AS-FOO", 6)
        mock_query_resolver.routes_for_as_set.reset_mock()

        mock_query_resolver.routes_for_as_set = Mock(return_value=[])
        response = parser.handle_query("!a6AS-FOO")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_set_members(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.members_for_set = Mock(return_value=["MEMBER1", "MEMBER2"])

        response = parser.handle_query("!iAS-FOO")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "MEMBER1 MEMBER2"
        mock_query_resolver.members_for_set.assert_called_once_with("AS-FOO", recursive=False)
        mock_query_resolver.members_for_set.reset_mock()

        response = parser.handle_query("!iAS-FOO,1")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "MEMBER1 MEMBER2"
        mock_query_resolver.members_for_set.assert_called_once_with("AS-FOO", recursive=True)

        mock_query_resolver.members_for_set = Mock(return_value=[])
        response = parser.handle_query("!iAS-FOO")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_database_serial_range(self, monkeypatch, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.sources_default = ["TEST1", "TEST2"]
        mock_query_resolver.all_valid_sources = ["TEST1", "TEST2"]

        mock_dsq = Mock()
        monkeypatch.setattr("irrd.server.whois.query_parser.DatabaseStatusQuery", lambda: mock_dsq)

        mock_query_result = [
            {
                "source": "TEST1",
                "serial_oldest_seen": 10,
                "serial_newest_mirror": 20,
                "serial_last_export": 10,
            },
            {
                "source": "TEST2",
                "serial_oldest_seen": None,
                "serial_newest_mirror": None,
                "serial_last_export": None,
            },
        ]
        mock_dh.execute_query = lambda query, refresh_on_error=False: mock_query_result

        response = parser.handle_query("!j-*")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "TEST1:N:0-20:10\nTEST2:N:-"
        assert flatten_mock_calls(mock_dsq) == [["sources", (["TEST1", "TEST2"],), {}]]
        mock_dsq.reset_mock()

        response = parser.handle_query("!jtest1,test-invalid")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "TEST1:N:0-20:10\nTEST2:N:-\nTEST-INVALID:X:Database unknown"
        assert flatten_mock_calls(mock_dsq) == [["sources", (["TEST1", "TEST-INVALID"],), {}]]

    def test_database_status(self, monkeypatch, prepare_parser, config_override):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.database_status = Mock(return_value={"dict": True})

        response = parser.handle_query("!J-*")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.replace(" ", "") == '{\n"dict":true\n}'
        mock_query_resolver.database_status.assert_called_once_with(None)
        mock_query_resolver.database_status.reset_mock()

        response = parser.handle_query("!Jtest1,test-invalid")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.replace(" ", "") == '{\n"dict":true\n}'
        mock_query_resolver.database_status.assert_called_once_with(["TEST1", "TEST-INVALID"])

    def test_exact_key(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.key_lookup = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("!mroute,192.0.2.0/25")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert response.remove_auth_hashes
        mock_query_resolver.key_lookup.assert_called_once_with("route", "192.0.2.0/25")
        mock_query_resolver.key_lookup.reset_mock()

        response = parser.handle_query("!mroute,192.0.2.0/25AS65530")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert response.remove_auth_hashes
        mock_query_resolver.key_lookup.assert_called_once_with("route", "192.0.2.0/25AS65530")
        mock_query_resolver.key_lookup.reset_mock()

        # https://github.com/irrdnet/irrd/issues/551
        response = parser.handle_query("!mroute,192.0.2.0/25 AS65530")
        mock_query_resolver.key_lookup.assert_called_once_with("route", "192.0.2.0/25AS65530")
        mock_query_resolver.key_lookup.reset_mock()
        response = parser.handle_query("!mroute,192.0.2.0/25-As65530")
        mock_query_resolver.key_lookup.assert_called_once_with("route", "192.0.2.0/25AS65530")
        mock_query_resolver.key_lookup.reset_mock()
        response = parser.handle_query("!mas-set,AS-FOO")
        mock_query_resolver.key_lookup.assert_called_once_with("as-set", "AS-FOO")
        mock_query_resolver.key_lookup.reset_mock()

        mock_query_resolver.key_lookup = Mock(return_value=[])
        response = parser.handle_query("!mroute,192.0.2.0/25")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.remove_auth_hashes
        assert not response.result

        response = parser.handle_query("!mfoo")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.remove_auth_hashes
        assert response.result == "Invalid argument for object lookup: foo"

    def test_user_agent(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("!nuser-agent")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_objects_maintained_by(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.rpsl_attribute_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("!oMNT-TEST")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert response.remove_auth_hashes
        mock_query_resolver.rpsl_attribute_search.assert_called_once_with("mnt-by", "MNT-TEST")

        mock_query_resolver.rpsl_attribute_search = Mock(return_value=[])
        response = parser.handle_query("!oMNT-NOT-EXISTING")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_route_search_exact(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("!r192.0.2.0/25")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.EXACT,
        )
        mock_query_resolver.route_search.reset_mock()

        response = parser.handle_query("!r192.0.2.0/25,o")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "AS65547 AS65544 AS65545"
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.EXACT,
        )

        mock_query_resolver.route_search = Mock(return_value=[])
        response = parser.handle_query("!r192.0.2.0/32,o")
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_route_search_exact_rpki_aware(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)
        mock_query_resolver.rpki_aware = True

        response = parser.handle_query("!r192.0.2.0/25")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED_WITH_RPKI
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.EXACT,
        )
        mock_query_resolver.route_search.reset_mock()

    def test_route_search_less_specific_one_level(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("!r192.0.2.0/25,l")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.LESS_SPECIFIC_ONE_LEVEL,
        )

    def test_route_search_less_specific(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("!r192.0.2.0/25,L")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.LESS_SPECIFIC_WITH_EXACT,
        )

    def test_route_search_more_specific(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.route_search = Mock(return_value=MOCK_DATABASE_RESPONSE)

        response = parser.handle_query("!r192.0.2.0/25,M")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        mock_query_resolver.route_search.assert_called_once_with(
            IP("192.0.2.0/25"),
            RouteLookupType.MORE_SPECIFIC_WITHOUT_EXACT,
        )

    def test_route_search_invalid(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("!rz")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Invalid input for route search: z"

        response = parser.handle_query("!rz,o")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Invalid input for route search: z,o"

        response = parser.handle_query("!r192.0.2.0/25,z")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Invalid route search option: z"

    def test_sources_list(self, prepare_parser, config_override):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.sources = ["TEST1"]
        mock_query_resolver.set_query_sources = Mock()

        response = parser.handle_query("!stest1")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        mock_query_resolver.set_query_sources.assert_called_once_with(["TEST1"])

        response = parser.handle_query("!s-lc")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "TEST1"

    def test_irrd_version(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        response = parser.handle_query("!v")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.startswith("IRRd")

    def test_disable_filters(self, prepare_parser):
        mock_query_resolver, mock_dh, parser = prepare_parser

        mock_query_resolver.disable_rpki_filter = Mock()
        response = parser.handle_query("!fno-rpki-filter")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.startswith("Filtering out RPKI invalids")
        mock_query_resolver.disable_rpki_filter.assert_called_once_with()

        mock_query_resolver.disable_out_of_scope_filter = Mock()
        response = parser.handle_query("!fno-scope-filter")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.startswith("Filtering out out-of-scope")
        mock_query_resolver.disable_out_of_scope_filter.assert_called_once_with()

        mock_query_resolver.disable_route_preference_filter = Mock()
        response = parser.handle_query("!fno-route-preference-filter")
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.startswith("Filtering out objects suppressed due to route")
        mock_query_resolver.disable_route_preference_filter.assert_called_once_with()

    def test_exception_handling(self, prepare_parser, caplog):
        mock_query_resolver, mock_dh, parser = prepare_parser
        mock_query_resolver.members_for_set = Mock(side_effect=Exception("test-error"))

        response = parser.handle_query("!i123")
        assert response.response_type == WhoisQueryResponseType.ERROR_INTERNAL
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "An internal error occurred while processing this query."

        assert "An exception occurred while processing whois query" in caplog.text
        assert "test-error" in caplog.text

        mock_query_resolver.members_for_set = Mock(side_effect=InvalidQueryException("user error"))

        response = parser.handle_query("!i123")
        assert response.response_type == WhoisQueryResponseType.ERROR_USER
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "user error"
