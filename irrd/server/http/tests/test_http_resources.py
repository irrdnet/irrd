from unittest.mock import Mock

from irrd.utils.test_utils import flatten_mock_calls
from ..http_resources import DatabaseStatusResource, http_site


class TestDatabaseStatusResource:
    def test_path_configured(self):
        assert http_site.resource.children[b'v1'].children[b'status'].__class__ == DatabaseStatusResource

    def test_database_status_get(self, monkeypatch):
        mock_database_status_request = Mock()
        monkeypatch.setattr("irrd.server.http.http_resources.DatabaseStatusRequest",
                            lambda: mock_database_status_request)
        mock_http_request = Mock()

        resource = DatabaseStatusResource()
        assert resource.isLeaf

        mock_database_status_request.generate_status = lambda: 'test 🦄'
        response = resource.render_GET(mock_http_request)

        assert flatten_mock_calls(mock_http_request) == [
            ['setHeader', ('Content-Type', 'text/plain; charset=utf-8'), {}]
        ]

        assert response == b'test \xf0\x9f\xa6\x84'
