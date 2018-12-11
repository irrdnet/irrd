from unittest.mock import Mock

import pytest
from twisted.internet.address import IPv4Address, UNIXAddress

from irrd.utils.test_utils import flatten_mock_calls
from ..http_resources import DatabaseStatusResource, http_site


@pytest.fixture()
def prepare_resource_mocks(monkeypatch, config_override):
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

    mock_database_status_request = Mock()
    monkeypatch.setattr("irrd.server.http.http_resources.DatabaseStatusRequest",
                        lambda: mock_database_status_request)
    mock_http_request = Mock()
    mock_http_request.getClientAddress = lambda: IPv4Address('TCP', '192.0.2.0', 99999)
    yield mock_database_status_request, mock_http_request


class TestDatabaseStatusResource:
    def test_path_configured(self):
        assert http_site.resource.children[b'v1'].children[b'status'].__class__ == DatabaseStatusResource

    def test_database_status_get_permitted_client_in_access_list(self, prepare_resource_mocks):
        mock_database_status_request, mock_http_request = prepare_resource_mocks

        resource = DatabaseStatusResource()
        assert resource.isLeaf

        mock_database_status_request.generate_status = lambda: 'test 🦄'
        response = resource.render_GET(mock_http_request)

        assert response == b'test \xf0\x9f\xa6\x84'
        assert flatten_mock_calls(mock_http_request) == [
            ['setHeader', (b'Content-Type', b'text/plain; charset=utf-8'), {}]
        ]

    def test_database_status_get_denied_client_not_in_access_list(self, prepare_resource_mocks, config_override):
        mock_database_status_request, mock_http_request = prepare_resource_mocks
        config_override({
            'server': {
                'http': {
                    'access_list': 'test_access_list',
                }
            },
            'access_lists': {
                'test_access_list': {
                    '192.0.2.128/25',
                }
            },
        })

        resource = DatabaseStatusResource()
        mock_database_status_request.generate_status = lambda: 'test 🦄'
        response = resource.render_GET(mock_http_request)

        assert response == b'Access denied'
        assert flatten_mock_calls(mock_http_request) == [
            ['setResponseCode', (403,), {}]
        ]

    def test_database_status_get_denied_no_access_list(self, prepare_resource_mocks, config_override):
        mock_database_status_request, mock_http_request = prepare_resource_mocks
        config_override({
            'server': {
                'http': {
                    'access_list': None,
                }
            },
        })

        resource = DatabaseStatusResource()
        mock_database_status_request.generate_status = lambda: 'test 🦄'
        response = resource.render_GET(mock_http_request)

        assert response == b'Access denied'
        assert flatten_mock_calls(mock_http_request) == [
            ['setResponseCode', (403,), {}]
        ]

    def test_database_status_get_denied_unknown_client_address(self, prepare_resource_mocks):
        mock_database_status_request, mock_http_request = prepare_resource_mocks
        mock_http_request.getClientAddress = lambda: UNIXAddress('not-supported')

        resource = DatabaseStatusResource()
        mock_database_status_request.generate_status = lambda: 'test 🦄'
        response = resource.render_GET(mock_http_request)

        assert response == b'Access denied'
        assert flatten_mock_calls(mock_http_request) == [
            ['setResponseCode', (403,), {}]
        ]
