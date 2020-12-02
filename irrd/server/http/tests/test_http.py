from unittest.mock import Mock

from starlette.requests import HTTPConnection

from ..endpoints import StatusEndpoint
from ..status_generator import StatusGenerator


class TestStatusEndpoint:
    def setup_method(self):
        self.mock_request = HTTPConnection({
            'type': 'http',
            'client': ('127.0.0.1', '8000'),
        })
        self.app = StatusEndpoint(scope=self.mock_request, receive=None, send=None)

    def test_status_no_access_list(self):
        response = self.app.get(self.mock_request)
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

        response = self.app.get(self.mock_request)
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
        response = self.app.get(self.mock_request)
        assert response.status_code == 403
        assert response.body == b'Access denied'
