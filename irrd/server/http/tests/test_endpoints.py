from unittest.mock import Mock

import ujson
from starlette.requests import HTTPConnection
from starlette.testclient import TestClient

from irrd import META_KEY_HTTP_CLIENT_IP
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import AuthoritativeChangeOrigin
from irrd.storage.preload import Preloader
from irrd.updates.handler import ChangeSubmissionHandler
from irrd.utils.validators import RPSLChangeSubmission, RPSLSuspensionSubmission

from ...whois.query_parser import WhoisQueryParser
from ...whois.query_response import (
    WhoisQueryResponse,
    WhoisQueryResponseMode,
    WhoisQueryResponseType,
)
from ..app import app
from ..endpoints_api import MetricsEndpoint, StatusEndpoint, WhoisQueryEndpoint
from ..metrics_generator import MetricsGenerator
from ..status_generator import StatusGenerator


class StatusAccessListEndpointBase:
    def setup_method(self):
        self.mock_request = HTTPConnection(
            {
                "type": "http",
                "client": ("127.0.0.1", "8000"),
            }
        )
        self.endpoint = self.endpoint_class(scope=self.mock_request, receive=None, send=None)

    def test_status_no_access_list(self):
        response = self.endpoint.get(self.mock_request)
        assert response.status_code == 403
        assert response.body == b"Access denied"

    def test_status_access_list_permitted(self, config_override, monkeypatch):
        config_override(
            {
                "server": {
                    "http": {
                        "status_access_list": "test_access_list",
                    }
                },
                "access_lists": {
                    "test_access_list": {
                        "127.0.0.0/25",
                    }
                },
            }
        )

        mock_generator = Mock(spec=self.generator_class)
        monkeypatch.setattr(
            f"irrd.server.http.endpoints_api.{self.generator_class.__name__}", lambda: mock_generator
        )
        mock_generator.generate = lambda: "status"

        response = self.endpoint.get(self.mock_request)
        assert response.status_code == 200
        assert response.body == b"status"

    def test_status_access_list_denied(self, config_override):
        config_override(
            {
                "server": {
                    "http": {
                        "status_access_list": "test_access_list",
                    }
                },
                "access_lists": {
                    "test_access_list": {
                        "192.0.2.0/25",
                    }
                },
            }
        )
        response = self.endpoint.get(self.mock_request)
        assert response.status_code == 403
        assert response.body == b"Access denied"


class TestStatusEndpoint(StatusAccessListEndpointBase):
    endpoint_class = StatusEndpoint
    generator_class = StatusGenerator


class TestMetricsEndpoint(StatusAccessListEndpointBase):
    endpoint_class = MetricsEndpoint
    generator_class = MetricsGenerator


class TestWhoisQueryEndpoint:
    def test_query_endpoint(self, monkeypatch):
        mock_query_parser = Mock(spec=WhoisQueryParser)
        monkeypatch.setattr(
            "irrd.server.http.endpoints_api.WhoisQueryParser",
            lambda client_ip, client_str, preloader, database_handler: mock_query_parser,
        )
        app = Mock(
            state=Mock(
                database_handler=Mock(spec=DatabaseHandler),
                preloader=Mock(spec=Preloader),
            )
        )
        mock_request = HTTPConnection(
            {
                "type": "http",
                "client": ("127.0.0.1", "8000"),
                "app": app,
                "query_string": "",
            }
        )
        endpoint = WhoisQueryEndpoint(scope=mock_request, receive=None, send=None)

        result = endpoint.get(mock_request)
        assert result.status_code == 400
        assert result.body.startswith(b"Missing required query")

        mock_request = HTTPConnection(
            {
                "type": "http",
                "client": ("127.0.0.1", "8000"),
                "app": app,
                "query_string": "q=query",
            }
        )

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.SUCCESS,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result=f"result {query} 🦄",
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 200
        assert result.body.decode("utf-8") == "result query 🦄"

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.KEY_NOT_FOUND,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result="",
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 204
        assert not result.body

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.ERROR_USER,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result=f"result {query} 🦄",
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 400
        assert result.body.decode("utf-8") == "result query 🦄"

        mock_query_parser.handle_query = lambda query: WhoisQueryResponse(
            response_type=WhoisQueryResponseType.ERROR_INTERNAL,
            mode=WhoisQueryResponseMode.IRRD,  # irrelevant
            result=f"result {query} 🦄",
        )
        result = endpoint.get(mock_request)
        assert result.status_code == 500
        assert result.body.decode("utf-8") == "result query 🦄"


class TestObjectSubmissionEndpoint:
    def test_endpoint(self, monkeypatch):
        mock_handler = Mock(spec=ChangeSubmissionHandler)
        monkeypatch.setattr("irrd.server.http.endpoints_api.ChangeSubmissionHandler", lambda: mock_handler)
        mock_handler.submitter_report_json = lambda: {"response": True}

        client = TestClient(app)
        data = {
            "objects": [
                {
                    "attributes": [
                        {"name": "person", "value": "Placeholder Person Object"},
                        {"name": "nic-hdl", "value": "PERSON-TEST"},
                        {"name": "changed", "value": "changed@example.com 20190701 # comment"},
                        {"name": "source", "value": "TEST"},
                    ]
                },
            ],
            "passwords": ["invalid1", "invalid2"],
        }
        expected_data = RPSLChangeSubmission.model_validate(data)

        response_post = client.post(
            "/v1/submit/", content=ujson.dumps(data), headers={"X-irrd-metadata": '{"meta": 2}'}
        )
        assert response_post.status_code == 200
        assert response_post.text == '{"response":true}'
        mock_handler.load_change_submission.assert_called_once_with(
            data=expected_data,
            origin=AuthoritativeChangeOrigin.webapi,
            delete=False,
            request_meta={META_KEY_HTTP_CLIENT_IP: "testclient", "HTTP-User-Agent": "testclient", "meta": 2},
            remote_ip=None,
        )
        mock_handler.send_notification_target_reports.assert_called_once()
        mock_handler.reset_mock()

        response_delete = client.request("DELETE", "/v1/submit/", content=ujson.dumps(data))
        assert response_delete.status_code == 200
        assert response_delete.text == '{"response":true}'
        mock_handler.load_change_submission.assert_called_once_with(
            data=expected_data,
            origin=AuthoritativeChangeOrigin.webapi,
            delete=True,
            request_meta={META_KEY_HTTP_CLIENT_IP: "testclient", "HTTP-User-Agent": "testclient"},
            remote_ip=None,
        )
        mock_handler.send_notification_target_reports.assert_called_once()
        mock_handler.reset_mock()

        response_invalid_format = client.post("/v1/submit/", content='{"invalid": true}')
        assert response_invalid_format.status_code == 400
        assert "Field required" in response_invalid_format.text
        mock_handler.load_change_submission.assert_not_called()
        mock_handler.send_notification_target_reports.assert_not_called()

        response_invalid_json = client.post("/v1/submit/", content="invalid")
        assert response_invalid_json.status_code == 400
        assert "expect" in response_invalid_json.text.lower()
        mock_handler.load_change_submission.assert_not_called()
        mock_handler.send_notification_target_reports.assert_not_called()


class TestSuspensionSubmissionEndpoint:
    def test_endpoint(self, monkeypatch):
        mock_handler = Mock(spec=ChangeSubmissionHandler)
        monkeypatch.setattr("irrd.server.http.endpoints_api.ChangeSubmissionHandler", lambda: mock_handler)
        mock_handler.submitter_report_json = lambda: {"response": True}

        client = TestClient(app)
        data = {
            "objects": [{"mntner": "DASHCARE-MNT", "source": "DASHCARE", "request_type": "reactivate"}],
            "override": "<>",
        }
        expected_data = RPSLSuspensionSubmission.model_validate(data)

        response_post = client.post("/v1/suspension/", content=ujson.dumps(data))
        assert response_post.status_code == 200
        assert response_post.text == '{"response":true}'
        mock_handler.load_suspension_submission.assert_called_once_with(
            data=expected_data,
            request_meta={META_KEY_HTTP_CLIENT_IP: "testclient", "HTTP-User-Agent": "testclient"},
        )
        mock_handler.reset_mock()

        response_invalid_format = client.post("/v1/suspension/", content='{"invalid": true}')
        assert response_invalid_format.status_code == 400
        assert "Field required" in response_invalid_format.text

        response_invalid_json = client.post("/v1/suspension/", content="invalid")
        assert response_invalid_json.status_code == 400
        assert "expect" in response_invalid_json.text.lower()
