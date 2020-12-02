from unittest.mock import Mock

from starlette.requests import HTTPConnection

from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.preload import Preloader
from ..endpoints import StatusEndpoint, WhoisQueryEndpoint
from ..status_generator import StatusGenerator
from ...whois.query_parser import WhoisQueryParser
from ...whois.query_response import WhoisQueryResponse, WhoisQueryResponseType, \
    WhoisQueryResponseMode


class TestStatusEndpoint:
    def setup_method(self):
        self.mock_request = HTTPConnection({
            'type': 'http',
            'client': ('127.0.0.1', '8000'),
        })
        self.endpoint = StatusEndpoint(scope=self.mock_request, receive=None, send=None)

    def test_status_no_access_list(self):
        response = self.endpoint.get(self.mock_request)
        assert response.status_code == 403
        assert response.body == b'Access denied'

    def test_status_access_list_permitted(self, config_override, monkeypatch):
        config_override({
            'server': {
                'http': {
                    'status_access_list': 'test_access_list',
                }
            },
            'access_lists': {
                'test_access_list': {
                    '127.0.0.0/25',
                }
            },
        })

        mock_database_status_generator = Mock(spec=StatusGenerator)
        monkeypatch.setattr('irrd.server.http.endpoints.StatusGenerator',
                            lambda: mock_database_status_generator)
        mock_database_status_generator.generate_status = lambda: 'status'

        response = self.endpoint.get(self.mock_request)
        assert response.status_code == 200
        assert response.body == b'status'

    def test_status_access_list_denied(self, config_override):
        config_override({
            'server': {
                'http': {
                    'status_access_list': 'test_access_list',
                }
            },
            'access_lists': {
                'test_access_list': {
                    '192.0.2.0/25',
                }
            },
        })
        response = self.endpoint.get(self.mock_request)
        assert response.status_code == 403
        assert response.body == b'Access denied'


class TestWhoisQueryEndpoint:
    def test_query_endpoint(self, monkeypatch):
        mock_query_parser = Mock(spec=WhoisQueryParser)
        monkeypatch.setattr('irrd.server.http.endpoints.WhoisQueryParser',
                            lambda client_ip, client_str, preloader, database_handler: mock_query_parser)
        app = Mock(state=Mock(
            database_handler=Mock(spec=DatabaseHandler),
            preloader=Mock(spec=Preloader),
        ))
        mock_request = HTTPConnection({
            'type': 'http',
            'client': ('127.0.0.1', '8000'),
            'app': app,
            'query_string': '',
        })
        endpoint = WhoisQueryEndpoint(scope=mock_request, receive=None, send=None)

        result = endpoint.get(mock_request)
        assert result.status_code == 400
        assert result.body.startswith(b'Missing required query')

        mock_request = HTTPConnection({
            'type': 'http',
            'client': ('127.0.0.1', '8000'),
            'app': app,
            'query_string': 'q=query',
        })

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.SUCCESS,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result=f'result {query} 🦄'
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 200
        assert result.body.decode('utf-8') == 'result query 🦄'

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.KEY_NOT_FOUND,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result='',
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 204
        assert not result.body

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.ERROR_USER,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result=f'result {query} 🦄'
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 400
        assert result.body.decode('utf-8') == 'result query 🦄'

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.ERROR_INTERNAL,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result=f'result {query} 🦄'
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 500
        assert result.body.decode('utf-8') == 'result query 🦄'
