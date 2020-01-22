import pytest
import uuid
from IPy import IP
from twisted.internet.address import IPv4Address
from unittest.mock import Mock

from irrd.mirroring.nrtm_generator import NRTMGeneratorException
from irrd.storage.models import RPKIStatus
from irrd.storage.preload import Preloader
from irrd.utils.test_utils import flatten_mock_calls
from ..query_parser import WhoisQueryParser
from ..query_response import WhoisQueryResponseType, WhoisQueryResponseMode

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

MOCK_ROUTE_COMBINED = MOCK_ROUTE1 + '\n' + MOCK_ROUTE2 + '\n' + MOCK_ROUTE3.strip()


MOCK_ROUTE_COMBINED_KEY_FIELDS = """route: 192.0.2.0/25
origin: AS65547
members: AS1, AS2

route: 192.0.2.0/25
origin: AS65544

route: 192.0.2.128/25
origin: AS65545"""


@pytest.fixture()
def prepare_parser(monkeypatch, config_override):
    config_override({
        'sources': {'TEST1': {}, 'TEST2': {}},
        'sources_default': [],
    })

    mock_database_handler = Mock()
    monkeypatch.setattr('irrd.server.whois.query_parser.DatabaseHandler', lambda: mock_database_handler)
    mock_database_query = Mock()
    monkeypatch.setattr('irrd.server.whois.query_parser.RPSLDatabaseQuery', lambda columns=None, ordered_by_sources=True: mock_database_query)
    mock_preloader = Mock(spec=Preloader)
    monkeypatch.setattr('irrd.server.whois.query_parser.get_preloader', lambda: mock_preloader)

    parser = WhoisQueryParser(IPv4Address('TCP', '127.0.0.1', 99999), '[127.0.0.1]:99999')

    mock_query_result = [
        {
            'pk': uuid.uuid4(),
            'rpsl_pk': '192.0.2.0/25,AS65547',
            'object_class': 'route',
            'parsed_data': {
                'route': '192.0.2.0/25', 'origin': 'AS65547', 'mnt-by': 'MNT-TEST', 'source': 'TEST1',
                'members': ['AS1, AS2']
            },
            'object_text': MOCK_ROUTE1,
            'source': 'TEST1',
        },
        {
            'pk': uuid.uuid4(),
            'rpsl_pk': '192.0.2.0/25,AS65544',
            'object_class': 'route',
            'parsed_data': {'route': '192.0.2.0/25', 'origin': 'AS65544', 'mnt-by': 'MNT-TEST', 'source': 'TEST2'},
            'object_text': MOCK_ROUTE2,
            'source': 'TEST2',
        },
        {
            'pk': uuid.uuid4(),
            'rpsl_pk': '192.0.2.128/25,AS65545',
            'object_class': 'route',
            'parsed_data': {'route': '192.0.2.128/25', 'origin': 'AS65545', 'mnt-by': 'MNT-TEST', 'source': 'TEST2'},
            'object_text': MOCK_ROUTE3,
            'source': 'TEST2',
        },
    ]
    mock_database_handler.execute_query = lambda query: mock_query_result

    yield (mock_database_query, mock_database_handler, mock_preloader, parser)


class TestWhoisQueryParserRIPE:
    """Test RIPE-style queries"""

    def test_invalid_flag(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-e foo')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Unrecognised flag/search: e'
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]

    def test_keepalive(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('-k')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert parser.multiple_command_mode

    def test_route_search_exact(self, prepare_parser):
        # This also tests the recursion disabled flag, which should have no effect,
        # and the reset of the key fields only flag.
        # It also tests the handling of extra spaces.
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

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
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('-l 192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific_one_level', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_less_specific(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('-L 192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_more_specific(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('-M 192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_more_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_invalid_parameter(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('-x not-a-prefix')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Invalid input for route search: not-a-prefix'
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]

    def test_inverse_attribute_search(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

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
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-s test1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        assert parser.sources == ['TEST1']

    def test_sources_all(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-a')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        assert parser.sources == parser.all_valid_sources

    def test_sources_default(self, prepare_parser, config_override):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()
        config_override({
            'sources': {'TEST1': {}, 'TEST2': {}},
            'sources_default': ['TEST2', 'TEST1'],
        })

        response = parser.handle_query(' -r  -x 192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['TEST2', 'TEST1'],), {}],
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}],
        ]

    def test_sources_invalid_unknown_source(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-s UNKNOWN')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'One or more selected sources are unavailable.'

    def test_restrict_object_class(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
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
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-t aut-num')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert 'aut-num:[mandatory][single][primary/look-upkey]' in response.result.replace(' ', '')
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        mock_dh.reset_mock()

        response = parser.handle_query('-t object-class-not-existing')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Unknown object class: object-class-not-existing'
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]

    def test_key_fields_only(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

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
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('-V user-agent')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not response.result
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]

    def test_nrtm_request(self, prepare_parser, monkeypatch, config_override):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        mock_nrg = Mock()
        monkeypatch.setattr('irrd.server.whois.query_parser.NRTMGenerator', lambda: mock_nrg)
        mock_nrg.generate = lambda source, version, serial_start, serial_end, dh: f'{source}/{version}/{serial_start}/{serial_end}'

        response = parser.handle_query('-g TEST1:3:1-5')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Access denied'

        config_override({
            'sources': {
                'TEST1': {'nrtm_access_list': 'nrtm_access'},
            },
            'access_lists': {
                'nrtm_access': ['0/0', '0::/0'],
            },
            'sources_default': [],
        })

        response = parser.handle_query('-g TEST1:3:1-5')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'TEST1/3/1/5'

        response = parser.handle_query('-g TEST1:3:1-LAST')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'TEST1/3/1/None'

        response = parser.handle_query('-g TEST1:9:1-LAST')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Invalid NRTM version: 9'

        response = parser.handle_query('-g TEST1:1:1-LAST:foo')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Invalid parameter: must contain three elements'

        response = parser.handle_query('-g UNKNOWN:1:1-LAST')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'Unknown source: UNKNOWN'

        for invalid_range in ['1', 'LAST-1', 'LAST', '1-last']:
            response = parser.handle_query(f'-g TEST1:3:{invalid_range}')
            assert response.response_type == WhoisQueryResponseType.ERROR
            assert response.mode == WhoisQueryResponseMode.RIPE
            assert response.result == f'Invalid serial range: {invalid_range}'

        mock_nrg.generate = Mock(side_effect=NRTMGeneratorException('expected-test-error'))
        response = parser.handle_query('-g TEST1:3:1-5')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'expected-test-error'

    def test_text_search(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('query')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['text_search', ('query',), {}],
        ]

    def test_missing_argument(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        missing_arg_queries = ['-i ', '-i mnt-by ', '-s', '-T', '-t', '-V', '-x   ']
        for query in missing_arg_queries:
            response = parser.handle_query(query)
            assert response.response_type == WhoisQueryResponseType.ERROR
            assert response.mode == WhoisQueryResponseMode.RIPE
            assert response.result == 'Missing argument for flag/search: ' + query[1]
            assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
            mock_dh.reset_mock()

    def test_exception_handling(self, prepare_parser, caplog):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()
        mock_dh.execute_query = Mock(side_effect=Exception('test-error'))

        response = parser.handle_query('foo')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert response.result == 'An internal error occurred while processing this query.'
        assert flatten_mock_calls(mock_dh)[1] == ['close', (), {}]

        assert 'An exception occurred while processing whois query' in caplog.text
        assert 'test-error' in caplog.text


class TestWhoisQueryParserIRRD:
    """Test IRRD-style queries"""

    def test_invalid_command(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Missing IRRD command'

        response = parser.handle_query('!e')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Unrecognised command: E'

        assert not mock_dq.mock_calls

    def test_parameter_required(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        queries_with_parameter = list('TG6IJMNORS')
        for query in queries_with_parameter:
            response = parser.handle_query(f'!{query}')
            assert response.response_type == WhoisQueryResponseType.ERROR
            assert response.mode == WhoisQueryResponseMode.IRRD
            assert response.result == f'Missing parameter for {query} query'

        assert not mock_dq.mock_calls

    def test_multiple_command_mode(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!!')
        assert response.response_type == WhoisQueryResponseType.NO_RESPONSE
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert not mock_dq.mock_calls
        assert parser.multiple_command_mode

    def test_update_timeout(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!t300')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert parser.timeout == 300

        for invalid_value in ['foo', '-5', '1001']:
            response = parser.handle_query(f'!t{invalid_value}')
            assert response.response_type == WhoisQueryResponseType.ERROR
            assert response.mode == WhoisQueryResponseMode.IRRD
            assert response.result == f'Invalid value for timeout: {invalid_value}'

        assert parser.timeout == 300
        assert not mock_dq.mock_calls

    def test_routes_for_origin_v4(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        mock_preloader.routes_for_origins = Mock(return_value=['192.0.2.0/25', '192.0.2.128/25'])

        response = parser.handle_query('!gas065547')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/25 192.0.2.128/25'
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            ['', (['AS65547'], ['TEST1', 'TEST2']), {'ip_version': 4}],
        ]

        mock_preloader.routes_for_origins = Mock(return_value=[])
        response = parser.handle_query('!gAS65547')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

        assert not mock_dq.mock_calls

    def test_routes_for_origin_v6(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        mock_preloader.routes_for_origins = Mock(return_value=['2001:db8::1/128', '2001:db8::/32'])

        parser.sources = ['TEST1']
        response = parser.handle_query('!6AS65547')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '2001:db8::1/128 2001:db8::/32'
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            ['', (['AS65547'], ['TEST1']), {'ip_version': 6}],
        ]

        mock_preloader.routes_for_origins = Mock(return_value=[])
        response = parser.handle_query('!6AS65547')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

        assert not mock_dq.mock_calls

    def test_routes_for_origin_invalid(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!gASfoobar')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Invalid AS number ASFOOBAR: number part is not numeric'

        assert not mock_dq.mock_calls

    def test_handle_irrd_routes_for_as_set(self, prepare_parser, monkeypatch):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        for parameter in ['', '4', '6']:
            response = parser.handle_query(f'!a{parameter}')
            assert response.response_type == WhoisQueryResponseType.ERROR
            assert response.mode == WhoisQueryResponseMode.IRRD
            assert response.result == 'Missing required set name for A query'

        monkeypatch.setattr(
            'irrd.server.whois.query_parser.WhoisQueryParser._recursive_set_resolve',
            lambda self, set_name: {'AS65547', 'AS65548'}
        )

        mock_preloader.routes_for_origins = Mock(return_value=[])
        response = parser.handle_query(f'!aas-nodata')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

        mock_preloader.routes_for_origins = Mock(return_value=['192.0.2.0/25', '192.0.2.128/25'])

        response = parser.handle_query('!aAS-FOO')
        assert parser._current_set_root_object_class == 'as-set'
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/25 192.0.2.128/25'
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            ['', ({'AS65547', 'AS65548'}, parser.all_valid_sources), {'ip_version': None}],
        ]
        mock_preloader.routes_for_origins.reset_mock()

        response = parser.handle_query('!a4AS-FOO')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/25 192.0.2.128/25'
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            ['', ({'AS65547', 'AS65548'}, parser.sources), {'ip_version': 4}],
        ]
        mock_preloader.routes_for_origins.reset_mock()

        response = parser.handle_query('!a6AS-FOO')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/25 192.0.2.128/25'
        assert flatten_mock_calls(mock_preloader.routes_for_origins) == [
            ['', ({'AS65547', 'AS65548'}, parser.sources), {'ip_version': 6}],
        ]
        mock_preloader.routes_for_origins.reset_mock()

        assert not mock_dq.mock_calls

    def test_as_set_members(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        mock_query_result1 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-FIRSTLEVEL',
                'parsed_data': {'as-set': 'AS-FIRSTLEVEL', 'members': ['AS65547', 'AS-SECONDLEVEL', 'AS-2nd-UNKNOWN']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST1',
            },
        ]
        mock_query_result2 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-SECONDLEVEL',
                'parsed_data': {'as-set': 'AS-SECONDLEVEL', 'members': ['AS-THIRDLEVEL', 'AS65544']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST1',
            },
            {   # Should be ignored - only the first result per PK is accepted.
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-SECONDLEVEL',
                'parsed_data': {'as-set': 'AS-SECONDLEVEL', 'members': ['AS-IGNOREME']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST2',
            },
        ]
        mock_query_result3 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-THIRDLEVEL',
                # Refers back to the first as-set to test infinite recursion issues
                'parsed_data': {'as-set': 'AS-THIRDLEVEL', 'members': ['AS65545', 'AS-FIRSTLEVEL', 'AS-4th-UNKNOWN']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST2',
            },
        ]
        mock_dh.execute_query = lambda query: iter(mock_query_result1)

        response = parser.handle_query('!iAS-FIRSTLEVEL')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'AS-2nd-UNKNOWN AS-SECONDLEVEL AS65547'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pks', ({'AS-FIRSTLEVEL'},), {}],
        ]
        mock_dq.reset_mock()

        mock_query_iterator = iter([mock_query_result1, mock_query_result2, mock_query_result3, [], mock_query_result1, []])
        mock_dh.execute_query = lambda query: iter(next(mock_query_iterator))

        response = parser.handle_query('!iAS-FIRSTLEVEL,1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'AS65544 AS65545 AS65547'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pks', ({'AS-FIRSTLEVEL'},), {}],
            ['object_classes', (['as-set'],), {}],
            ['rpsl_pks', ({'AS-2nd-UNKNOWN', 'AS-SECONDLEVEL'},), {}],
            ['object_classes', (['as-set'],), {}],
            ['rpsl_pks', ({'AS-THIRDLEVEL'},), {}],
            ['object_classes', (['as-set'],), {}],
            ['rpsl_pks', ({'AS-4th-UNKNOWN'},), {}],
        ]
        mock_dq.reset_mock()

        mock_dh.execute_query = lambda query: iter([])
        response = parser.handle_query('!iAS-NOTEXIST')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pks', ({'AS-NOTEXIST'},), {}]
        ]

    def test_route_set_members(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        mock_query_result1 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'RS-FIRSTLEVEL',
                'parsed_data': {'as-set': 'RS-FIRSTLEVEL',
                                'members': ['RS-SECONDLEVEL', 'RS-2nd-UNKNOWN']},
                'object_text': 'text',
                'object_class': 'route-set',
                'source': 'TEST1',
            },
        ]
        mock_query_result2 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'RS-SECONDLEVEL',
                'parsed_data': {'as-set': 'RS-SECONDLEVEL', 'members': ['AS-REFERRED', '192.0.2.0/25']},
                'object_text': 'text',
                'object_class': 'route-set',
                'source': 'TEST1',
            },
        ]
        mock_query_result3 = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'AS-REFERRED',
                'parsed_data': {'as-set': 'AS-REFERRED',
                                'members': ['AS65545']},
                'object_text': 'text',
                'object_class': 'as-set',
                'source': 'TEST2',
            },
        ]
        mock_query_iterator = iter([mock_query_result1, mock_query_result2, mock_query_result3, []])
        mock_dh.execute_query = lambda query: iter(next(mock_query_iterator))
        mock_preloader.routes_for_origins = Mock(return_value=['192.0.2.128/25'])

        response = parser.handle_query('!iRS-FIRSTLEVEL,1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/25 192.0.2.128/25'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['as-set', 'route-set'],), {}], ['rpsl_pks', ({'RS-FIRSTLEVEL'},), {}],
            ['object_classes', (['as-set', 'route-set'],), {}],
            ['rpsl_pks', ({'RS-SECONDLEVEL', 'RS-2nd-UNKNOWN'},), {}],
            ['object_classes', (['as-set', 'route-set'],), {}], ['rpsl_pks', ({'AS-REFERRED'},), {}],
        ]

    def test_as_route_set_mbrs_by_ref(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

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
                'rpsl_pk': '192.0.2.0/24,AS65544',
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
            ['rpsl_pks', ({'RRS-TEST'},), {}],
            ['object_classes', (['route', 'route6'],), {}],
            ['lookup_attrs_in', (['member-of'], ['RRS-TEST']), {}],
            ['lookup_attrs_in', (['mnt-by'], ['MNT-TEST']), {}],
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
            ['rpsl_pks', ({'RRS-TEST'},), {}],
            ['object_classes', (['route', 'route6'],), {}],
            ['lookup_attrs_in', (['member-of'], ['RRS-TEST']), {}],
        ]

    def test_route_set_compatibility_ipv4_only_route_set_members(self, prepare_parser, config_override):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        mock_query_result = [
            {
                'pk': uuid.uuid4(),
                'rpsl_pk': 'RS-TEST',
                'parsed_data': {
                    'route-set': 'RS-TEST',
                    'members': ['192.0.2.0/32'],
                    'mp-members': ['192.0.2.1/32', '2001:db8::/32', 'RS-OTHER']
                },
                'object_text': 'text',
                'object_class': 'route-set',
                'source': 'TEST1',
            },
        ]
        mock_dh.execute_query = lambda query: mock_query_result

        response = parser.handle_query('!iRS-TEST,1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/32 192.0.2.1/32 2001:db8::/32'

        config_override({
            'compatibility': {'ipv4_only_route_set_members': True},
        })

        response = parser.handle_query('!iRS-TEST')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == '192.0.2.0/32 192.0.2.1/32 RS-OTHER'

    def test_database_serial_range(self, monkeypatch, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dsq = Mock()
        monkeypatch.setattr('irrd.server.whois.query_parser.DatabaseStatusQuery', lambda: mock_dsq)

        mock_query_result = [
            {'source': 'TEST1', 'serial_oldest_seen': 10, 'serial_newest_seen': 20, 'serial_last_export': 10},
            {'source': 'TEST2', 'serial_oldest_seen': None, 'serial_newest_seen': None, 'serial_last_export': None},
        ]
        mock_dh.execute_query = lambda query: mock_query_result

        response = parser.handle_query('!j-*')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'TEST1:N:10-20:10\nTEST2:N:-'
        assert flatten_mock_calls(mock_dsq) == [
            ['sources', (['TEST1', 'TEST2'],), {}]
        ]
        mock_dsq.reset_mock()

        response = parser.handle_query('!jtest1,test-invalid')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'TEST1:N:10-20:10\nTEST2:N:-\nTEST-INVALID:X:Database unknown'
        assert flatten_mock_calls(mock_dsq) == [
            ['sources', (['TEST1', 'TEST-INVALID'],), {}]
        ]

    def test_exact_key(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

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
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        parser.handle_query('!stest1')
        response = parser.handle_query('!mroute,192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['sources', (['TEST1'],), {}],
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
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('!nuser-agent')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]

    def test_objects_maintained_by(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

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
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

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
        assert response.result == 'AS65547 AS65544 AS65545'
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}]
        ]

        mock_dh.execute_query = lambda query: []
        response = parser.handle_query('!r192.0.2.0/32,o')
        assert response.response_type == WhoisQueryResponseType.KEY_NOT_FOUND
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result

    def test_route_search_exact_rpki_aware(self, prepare_parser, config_override):
        mock_dq, mock_dh, mock_preloader, _ = prepare_parser
        config_override({
            'sources': {'TEST1': {}, 'TEST2': {}},
            'sources_default': [],
            'rpki': {'roa_source': 'https://example.com/roa.json'},
        })
        parser = WhoisQueryParser(IPv4Address('TCP', '127.0.0.1', 99999), '[127.0.0.1]:99999')

        response = parser.handle_query('!r192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['rpki_status', ([RPKIStatus.unknown, RPKIStatus.valid],), {}],
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}],
        ]
        mock_dq.reset_mock()

        response = parser.handle_query('!f')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert 'Filtering out RPKI invalids is disabled' in response.result

        response = parser.handle_query('!r192.0.2.0/25')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_exact', (IP('192.0.2.0/25'),), {}],
        ]

    def test_route_search_less_specific_one_level(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!r192.0.2.0/25,l')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific_one_level', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_less_specific(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!r192.0.2.0/25,L')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_less_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_more_specific(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!r192.0.2.0/25,M')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == MOCK_ROUTE_COMBINED
        assert flatten_mock_calls(mock_dq) == [
            ['object_classes', (['route', 'route6'],), {}],
            ['ip_more_specific', (IP('192.0.2.0/25'),), {}]
        ]

    def test_route_search_invalid(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser

        response = parser.handle_query('!rz')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Invalid input for route search: z'
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        mock_dh.reset_mock()

        response = parser.handle_query('!rz,o')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Invalid input for route search: z,o'
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        mock_dh.reset_mock()

        response = parser.handle_query('!r192.0.2.0/25,z')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'Invalid route search option: z'
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        mock_dh.reset_mock()

    def test_sources_list(self, prepare_parser, config_override):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('!stest1')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert not response.result
        assert flatten_mock_calls(mock_dh) == [['close', (), {}]]
        assert parser.sources == ['TEST1']

        response = parser.handle_query('!s-lc')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'TEST1'

        response = parser.handle_query('!sTEST3')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'One or more selected sources are unavailable.'

        config_override({
            'sources': {'TEST1': {}, 'TEST2': {}},
            'sources_default': [],
            'rpki': {'roa_source': 'https://example.com/roa.json'}
        })
        parser = WhoisQueryParser(IPv4Address('TCP', '127.0.0.1', 99999), '[127.0.0.1]:99999')
        response = parser.handle_query('!s-lc')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'TEST1,TEST2,RPKI'

    def test_irrd_version(self, prepare_parser):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('!v')
        assert response.response_type == WhoisQueryResponseType.SUCCESS
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result.startswith('IRRd')
        assert not mock_dq.mock_calls

    def test_exception_handling(self, prepare_parser, caplog):
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()
        mock_dh.execute_query = Mock(side_effect=Exception('test-error'))

        response = parser.handle_query('!i123')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.IRRD
        assert response.result == 'An internal error occurred while processing this query.'
        assert flatten_mock_calls(mock_dh)[1] == ['close', (), {}]

        assert 'An exception occurred while processing whois query' in caplog.text
        assert 'test-error' in caplog.text

    def test_issue_131(self, prepare_parser):
        """Queries like `- 103.67.241.255` could lead to unfiltered SQL queries."""
        mock_dq, mock_dh, mock_preloader, parser = prepare_parser
        mock_dh.reset_mock()

        response = parser.handle_query('- 103.67.241.255')
        assert response.response_type == WhoisQueryResponseType.ERROR
        assert response.mode == WhoisQueryResponseMode.RIPE
        assert not mock_dq.mock_calls
