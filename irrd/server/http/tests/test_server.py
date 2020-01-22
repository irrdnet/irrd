import pytest
from http import HTTPStatus
from unittest.mock import Mock

from ..server import IRRdHTTPRequestProcessor


@pytest.fixture()
def prepare_mocks(monkeypatch, config_override):
    config_override({
        'server': {
            'http': {
                'access_list': 'test_access_list',
            }
        },
        'access_lists': {
            'test_access_list': {
                '192.0.2.0/25',
            }
        },
    })

    mock_database_status_generator = Mock()
    monkeypatch.setattr('irrd.server.http.server.StatusGenerator',
                        lambda: mock_database_status_generator)
    mock_database_status_generator.generate_status = lambda: 'status'


class TestIRRdHTTPRequestProcessor:
    def test_database_status_get_permitted_client_in_access_list(self, prepare_mocks):
        processor = IRRdHTTPRequestProcessor('192.0.2.1', 99999)
        status, content = processor.handle_get('/v1/status/')
        assert status == HTTPStatus.OK
        assert content == 'status'

    def test_database_status_get_denied_client_not_in_access_list(self, prepare_mocks, config_override):
        processor = IRRdHTTPRequestProcessor('192.0.2.200', 99999)
        status, content = processor.handle_get('/v1/status')
        assert status == HTTPStatus.FORBIDDEN
        assert content == 'Access denied'

    def test_database_status_get_denied_no_access_list(self, prepare_mocks, config_override):
        config_override({
            'server': {
                'http': {
                    'access_list': None,
                }
            },
        })

        processor = IRRdHTTPRequestProcessor('192.0.2.1', 99999)
        status, content = processor.handle_get('/v1/status/')
        assert status == HTTPStatus.FORBIDDEN
        assert content == 'Access denied'

    def test_database_status_get_unknown_url(self, prepare_mocks):
        processor = IRRdHTTPRequestProcessor('192.0.2.1', 99999)
        status, content = processor.handle_get('/v1')
        assert status == HTTPStatus.NOT_FOUND
        assert content == 'Not found'
