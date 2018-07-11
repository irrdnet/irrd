import uuid
from unittest.mock import Mock

import pytest
from IPy import IP
from pytest import raises

from ..query_parser import WhoisQueryParser, WhoisQueryResponseMode, WhoisQueryResponseType, WhoisQueryResponse

# Note that these mock objects are not entirely valid RPSL objects,
# as they are meant to test all the scenarios in the query parser.
MOCK_ROUTE1 = """route:          192.0.2.0/25
descr:          description
origin:         AS23456
mnt-by:         MNT-TEST
source:         TEST1
members:        AS1,AS2
"""

MOCK_ROUTE2 = """route:          192.0.2.0/25
descr:          description
origin:         AS65534
mnt-by:         MNT-TEST
source:         TEST2
"""

MOCK_ROUTE3 = """route:          192.0.2.128/25
descr:          description
origin:         AS65535
mnt-by:         MNT-TEST
source:         TEST2
"""

MOCK_ROUTE_COMBINED = MOCK_ROUTE1 + "\n" + MOCK_ROUTE2 + "\n" + MOCK_ROUTE3.strip()


MOCK_ROUTE_COMBINED_KEY_FIELDS = """route: 192.0.2.0/25
origin: AS23456
members: AS1, AS2

route: 192.0.2.0/25
origin: AS65534

route: 192.0.2.128/25
origin: AS65535"""


@pytest.fixture()
def prepare_parser(monkeypatch):
    mock_database_handler = Mock()
    monkeypatch.setattr("irrd.server.whois.query_parser.DatabaseHandler", lambda: mock_database_handler)
    mock_database_query = Mock()
    monkeypatch.setattr("irrd.server.whois.query_parser.RPSLDatabaseQuery", lambda: mock_database_query)
    parser = WhoisQueryParser('[127.0.0.1]:99999')

    mock_query_result = [
        {
            'pk': uuid.uuid4(),
            'rpsl_pk': '192.0.2.0/25,AS23456',
            'object_class': 'route',
            'parsed_data': {
                'route': '192.0.2.0/25', 'origin': 'AS23456', 'mnt-by': 'MNT-TEST', 'source': 'TEST1',
                'members': ['AS1, AS2']
            },
            'object_text': MOCK_ROUTE1,
            'source': 'TEST1',
        },
        {
            'pk': uuid.uuid4(),
            'rpsl_pk': '192.0.2.0/25,AS65534',
            'object_class': 'route',
            'parsed_data': {'route': '192.0.2.0/25', 'origin': 'AS65534', 'mnt-by': 'MNT-TEST', 'source': 'TEST2'},
            'object_text': MOCK_ROUTE2,
            'source': 'TEST2',
        },
        {
            'pk': uuid.uuid4(),
            'rpsl_pk': '192.0.2.128/25,AS65535',
            'object_class': 'route',
            'parsed_data': {'route': '192.0.2.128/25', 'origin': 'AS65535', 'mnt-by': 'MNT-TEST', 'source': 'TEST2'},
            'object_text': MOCK_ROUTE3,
            'source': 'TEST2',
        },
    ]
    mock_database_handler.execute_query = lambda query: mock_query_result

    yield (mock_database_query, mock_database_handler, parser)


class TestWhoisQueryResponse:
    def test_response(self):
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.IRRD,
                                      response_type=WhoisQueryResponseType.SUCCESS,
                                      result='test').generate_response()
        assert response == 'A5\ntest\nC\n'
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.IRRD,
                                      response_type=WhoisQueryResponseType.SUCCESS,
                                      result='').generate_response()
        assert response == 'C\n'
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.IRRD,
                                      response_type=WhoisQueryResponseType.KEY_NOT_FOUND,
                                      result='test').generate_response()
        assert response == 'D\n'
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.IRRD,
                                      response_type=WhoisQueryResponseType.ERROR,
                                      result='test').generate_response()
        assert response == 'F test\n'
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.RIPE,
                                      response_type=WhoisQueryResponseType.SUCCESS,
                                      result='test').generate_response()
        assert response == 'test\n\n'
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.RIPE,
                                      response_type=WhoisQueryResponseType.SUCCESS,
                                      result='').generate_response()
        assert response == '%  No entries found for the selected source(s).\n'
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.RIPE,
                                      response_type=WhoisQueryResponseType.KEY_NOT_FOUND,
                                      result='test').generate_response()
        assert response == '%  No entries found for the selected source(s).\n'
        response = WhoisQueryResponse(mode=WhoisQueryResponseMode.RIPE,
                                      response_type=WhoisQueryResponseType.ERROR,
                                      result='test').generate_response()
        assert response == '%% test\n'

        with raises(RuntimeError) as ve:
            # noinspection PyTypeChecker
            WhoisQueryResponse(response_type='bar', mode='foo', result='foo').generate_response()  # type:ignore
        assert 'foo' in str(ve)


class TestWhoisQueryParserRIPE:
    """Test RIPE-style queries"""

    def test_invalid_flag(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-e foo')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Unrecognised flag/search: e'
        assert not mock_dh.mock_calls

    def test_keepalive(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('-k')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert parser.multiple_command_mode

    def test_route_search_exact(self, prepare_parser):
        # This also tests the recursion disabled flag, which should have no effect,
        # and the reset of the key fields only flag.
        # It also tests the handling of extra spaces.
        mock_dq, mock_dh, parser = prepare_parser

        parser.key_fields_only = True
        response = parser.handle_query('-r  -x   192.0.2.0/25')
        assert not parser.key_fields_only

        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}]
        ]
        mock_dq.reset_mock()

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('-x 192.0.2.0/32')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result

    def test_route_search_less_specific_one_level(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('-l 192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific_one_level', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_less_specific(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('-L 192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_more_specific(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('-M 192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_more_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_invalid_parameter(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('-x not-a-prefix')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Invalid input for route search: not-a-prefix'
        assert not mock_dh.mock_calls

    def test_inverse_attribute_search(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('-i mnt-by MNT-TEST')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['lookup_attr', ('mnt-by', 'MNT-TEST'), {}],
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('-i mnt-by MNT-NOT-EXISTING')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('-i invalid-attr INVALID-SEARCH')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result.startswith('Inverse attribute search not supported for invalid-attr')

    def test_sources_list(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-s ripe,nttcom')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert not mock_dh.mock_calls
        assert parser.sources == ['RIPE', 'NTTCOM']

    def test_sources_all(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-a')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert not mock_dh.mock_calls
        assert parser.sources == []

    def test_restrict_object_class(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-T route -i mnt-by MNT-TEST')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route'],), {}],
            ['lookup_attr', ('mnt-by', 'MNT-TEST'), {}],
        ]
        mock_dq.reset_mock()

        # -T should not persist
        response = parser.handle_query('-i mnt-by MNT-TEST')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['lookup_attr', ('mnt-by', 'MNT-TEST'), {}],
        ]

    def test_object_template(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-t aut-num')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert 'aut-num:[mandatory][single][primary/look-upkey]' in response.result.replace(' ', '')
        assert not mock_dh.mock_calls

        response = parser.handle_query('-t object-class-not-existing')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Unknown object class: object-class-not-existing'
        assert not mock_dh.mock_calls

    def test_key_fields_only(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('-K -x 192.0.2.0/25')
        assert parser.key_fields_only

        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED_KEY_FIELDS
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}]
        ]
        mock_dq.reset_mock()

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('-x 192.0.2.0/32')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result

    def test_user_agent(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-V user-agent')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert not mock_dh.mock_calls

    def test_text_search(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('query')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['text_search', ('query',), {}],
        ]

    def test_missing_argument(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        missing_arg_queries = ['-i ', '-i mnt-by ', '-s', '-T', '-t', '-V', '-x   ']
        for query in missing_arg_queries:
            response = parser.handle_query(query)
            assert response.response_type == WhoisQueryResponseType.ERROR
            assert response.mode == WhoisQueryResponseMode.RIPE
            assert response.result == 'Missing argument for flag/search: ' + query[1]
            assert not mock_dh.mock_calls


class TestWhoisQueryParserIRRD:
    """Test IRRD-style queries"""

    def test_invalid_command(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Missing IRRD command'

        response = parser.handle_query('!e')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Unrecognised command: E'

        assert not mock_dq.mock_calls

    def test_multiple_command_mode(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!!')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert not mock_dq.mock_calls
        assert parser.multiple_command_mode

    def test_routes_for_origin_v4(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!gAS23456')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/25 192.0.2.128/25'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route'],), {}],
            ['asn', (23456,), {}],
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('!gAS23456')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_routes_for_origin_v6(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        # For testing this query, it suffices to make sure there is a route6 attribute
        mock_query_result = mock_dh.execute_query(None)
        for mock_result_row in mock_query_result:
            mock_result_row['parsed_data']['route6'] = mock_result_row['parsed_data']['route']
        mock_dh.execute_query = lambda query: mock_query_result

        response = parser.handle_query('!6AS23456')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/25 192.0.2.128/25'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route6'],), {}],
            ['asn', (23456,), {}],
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('!6AS23456')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_routes_for_origin_invalid(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!gASfoobar')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Invalid AS number ASFOOBAR: number part is not numeric'

        assert not mock_dq.mock_calls

    def test_as_route_set_members(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        mock_query_result1 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-FIRSTLEVEL',
                'parsed_data': {'as-set': 'AS-FIRSTLEVEL', 'members': ['AS23456', 'AS-SECONDLEVEL']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST1',
            },
        ]
        mock_query_result2 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-SECONDLEVEL',
                'parsed_data': {'as-set': 'AS-SECONDLEVEL', 'members': ['AS-THIRDLEVEL', 'AS65534']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST1',
            },
        ]
        mock_query_result3 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-THIRDLEVEL',
                # Refers back to the first as-set to test infinite recursion issues
                'parsed_data': {'as-set': 'AS-THIRDLEVEL', 'members': ['AS65535', 'AS-FIRSTLEVEL', 'AS-UNKNOWN']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST1',
            },
        ]
        mock_dh.execute_query = lambda query: iter(mock_query_result1)

        response = parser.handle_query('!iAS-FIRSTLEVEL')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'AS-SECONDLEVEL AS23456'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('AS-FIRSTLEVEL',), {}],
            ['first_only', (), {}]
        ]
        mock_dq.reset_mock()

        mock_query_iterator = iter([mock_query_result1, mock_query_result2, mock_query_result3, [], mock_query_result1, []])
        mock_dh.execute_query = lambda query: iter(next(mock_query_iterator))

        response = parser.handle_query('!iAS-FIRSTLEVEL,1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'AS-UNKNOWN AS23456 AS65534 AS65535'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('AS-FIRSTLEVEL',), {}],
            ['first_only', (), {}],
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('AS-SECONDLEVEL',), {}],
            ['first_only', (), {}],
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('AS-THIRDLEVEL',), {}],
            ['first_only', (), {}],
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('AS-UNKNOWN',), {}],
            ['first_only', (), {}],
        ]
        mock_dq.reset_mock()

        mock_dh.execute_query = lambda query: iter([])
        response = parser.handle_query('!iAS-FIRSTLEVEL,1')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('AS-FIRSTLEVEL',), {}],
            ['first_only', (), {}],
        ]

    def test_as_route_set_mbrs_by_ref(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        mock_query_result1 = [
            {
                # This route-set is intentionally misnamed RRS, as invalid names occur in real life.
                'pk': uuid.uuid4(),
                'rpsl_pk': 'RRS-TEST',
                'parsed_data': {'route-set': 'RRS-TEST', 'members': ['192.0.2.0/32'],
                                'mp-members': ['2001:db8::/32'], 'mbrs-by-ref': ['MNT-TEST']},
                'object_text': 'text',
                'object_class': 'route-set',
                'source': 'TEST1',
            },
        ]
        mock_query_result2 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': '192.0.2.0/24,AS65534',
                'parsed_data': {'route': '192.0.2.0/24', 'member-of': 'rrs-test', 'mnt-by': ['FOO', 'MNT-TEST']},
                'object_text': 'text',
                'object_class': 'route',
                'source': 'TEST1',
            },
        ]
        mock_query_iterator = iter([mock_query_result1, mock_query_result2, [], [], []])
        mock_dh.execute_query = lambda query: iter(next(mock_query_iterator))

        response = parser.handle_query('!iRRS-TEST,1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/24 192.0.2.0/32 2001:db8::/32'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('RRS-TEST',), {}],
            ['first_only', (), {}],
            ['object_classes', (['route', 'route6'],), {}],
            ['lookup_attr', ('member-of', 'RRS-TEST'), {}],
            ['lookup_attr_in', ('mnt-by', ['MNT-TEST']), {}]
        ]
        mock_dq.reset_mock()

        # Disable maintainer check
        mock_query_result1[0]['parsed_data']['mbrs-by-ref'] = ['ANY']
        mock_query_iterator = iter([mock_query_result1, mock_query_result2, [], [], []])
        response = parser.handle_query('!iRRS-TEST,1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/24 192.0.2.0/32 2001:db8::/32'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pk', ('RRS-TEST',), {}],
            ['first_only', (), {}],
            ['object_classes', (['route', 'route6'],), {}],
            ['lookup_attr', ('member-of', 'RRS-TEST'), {}],
        ]

    def test_database_serial_range(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        with raises(NotImplementedError):
            parser.handle_query('!j-*')

    def test_exact_key(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!mroute,192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route'],), {}],
            ['rpsl_pk', ('192.0.2.0/25',), {}],
            ['first_only', (), {}],
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('!mroute,192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

        response = parser.handle_query('!mfoo')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Invalid argument for object lookup: foo'

    def test_exact_key_limit_sources(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        parser.handle_query('!snttcom,ripe')
        response = parser.handle_query('!mroute,192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['NTTCOM', 'RIPE'],), {}],
            ['object_classes', (['route'],), {}],
            ['rpsl_pk', ('192.0.2.0/25',), {}],
            ['first_only', (), {}],
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('!mroute,192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

        response = parser.handle_query('!mfoo')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Invalid argument for object lookup: foo'

    def test_user_agent(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('!nuser-agent')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert not mock_dh.mock_calls

    def test_objects_maintained_by(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!oMNT-TEST')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['lookup_attr', ('mnt-by', 'MNT-TEST'), {}],
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('!oMNT-NOT-EXISTING')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_route_search_exact(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!r192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}]
        ]
        mock_dq.reset_mock()

        response = parser.handle_query('!r192.0.2.0/25,o')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'AS23456 AS65534 AS65535'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}]
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('!r192.0.2.0/32,o')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_route_search_less_specific_one_level(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!r192.0.2.0/25,l')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific_one_level', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_less_specific(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!r192.0.2.0/25,L')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_more_specific(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!r192.0.2.0/25,M')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_more_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_invalid(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser

        response = parser.handle_query('!rz')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Invalid input for route search: z"

        response = parser.handle_query('!rz,o')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Invalid input for route search: z,o"

        response = parser.handle_query('!r192.0.2.0/25,z')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == "Invalid route search option: z"

        assert not mock_dh.mock_calls

    def test_sources_list(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('!sripe,nttcom')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert not mock_dh.mock_calls
        assert parser.sources == ['RIPE', 'NTTCOM']

        response = parser.handle_query('!s-lc')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'RIPE,NTTCOM'

        response = parser.handle_query('!s')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'One or more listed sources are unavailable.'

        # TODO: add test with invalid sources

    def test_irrd_version(self, prepare_parser):
        mock_dq, mock_dh, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('!v')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.startswith('IRRD4')
        assert not mock_dq.mock_calls


def flatten_mock_calls(mock):
    result = []
    for call in mock.mock_calls:
        call = list(call)
        call_name = call[0]
        if '.' in str(call_name):
            call_name = str(call_name).split('.')[-1]
        result.append([call_name] + call[1:])
    return result
