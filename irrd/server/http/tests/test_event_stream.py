import asyncio
import csv
import json
import unittest
from collections import OrderedDict
from datetime import datetime
from typing import Tuple, Union
from unittest.mock import create_autospec

import pytest
from coredis.response.types import StreamEntry
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.storage.event_stream import OPERATION_JOURNAL_EXTENDED
from irrd.storage.queries import (
    RPSLDatabaseJournalQuery,
    RPSLDatabaseJournalStatisticsQuery,
    RPSLDatabaseQuery,
)
from irrd.utils.rpsl_samples import SAMPLE_MNTNER
from irrd.utils.test_utils import MockDatabaseHandler
from irrd.vendor import postgres_copy

from ..app import app
from ..event_stream import AsyncEventStreamFollower


def create_autospec_async_compat(spec):  # pragma: no cover
    if hasattr(unittest.mock, "AsyncMock"):
        return create_autospec(spec)
    else:
        # AsyncMock is not available in 3.7
        import asyncmock

        return asyncmock.AsyncMock(spec)


class TestEventStreamInitialDownloadEndpoint:
    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    async def test_endpoint_success(self, monkeypatch, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {"keep_journal": True},
                    "IGNORED": {},
                },
                "server": {"http": {"event_stream_access_list": "access_list"}},
                "access_lists": {"access_list": "testclient"},
            }
        )

        def mock_copy_to_side_effect(source, dest, engine_or_conn, format):
            writer = csv.writer(dest)
            rpsl_obj = rpsl_object_from_text(SAMPLE_MNTNER, strict_validation=False)
            writer.writerow(
                [
                    rpsl_obj.pk(),
                    rpsl_obj.rpsl_object_class,
                    rpsl_obj.render_rpsl_text(),
                    rpsl_obj.source(),
                    datetime.utcnow().isoformat(),
                    json.dumps(rpsl_obj.parsed_data),
                ]
            )

        mock_copy_to = create_autospec(postgres_copy.copy_to)
        mock_copy_to.side_effect = mock_copy_to_side_effect
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        monkeypatch.setattr("irrd.server.http.event_stream.DatabaseHandler", MockDatabaseHandler)
        monkeypatch.setattr("irrd.server.http.event_stream.postgres_copy.copy_to", mock_copy_to)

        client = TestClient(app)
        response = client.get(
            "/v1/event-stream/initial/", params={"sources": "TEST", "object_classes": "mntner"}
        )
        assert response.status_code == 200
        header, rpsl_obj = (json.loads(line) for line in response.text.splitlines())

        assert header["data_type"] == "irrd_event_stream_initial_download"
        assert header["sources_filter"] == ["TEST"]
        assert header["object_classes_filter"] == ["mntner"]
        assert header["max_serial_global"] == 42
        assert header["last_change_timestamp"] == "2022-03-14T12:34:56"
        assert header["generated_at"] == "2022-03-14T12:34:56"

        assert rpsl_obj["pk"] == "TEST-MNT"
        assert rpsl_obj["parsed_data"]["auth"] == [
            "PGPKey-80F238C6",
            "CRYPT-Pw DummyValue  # Filtered for security",
            "MD5-pw DummyValue  # Filtered for security",
            "bcrypt-pw DummyValue  # Filtered for security",
        ]
        assert "DummyValue" in rpsl_obj["object_text"]

        db_query = mock_copy_to.mock_calls[0][2]["source"]
        expected_statement = (
            RPSLDatabaseQuery(
                column_names=["rpsl_pk", "object_class", "object_text", "source", "updated", "parsed_data"]
            )
            .rpki_status([RPKIStatus.not_found.name, RPKIStatus.valid.name])
            .scopefilter_status([ScopeFilterStatus.in_scope.name])
            .route_preference_status([RoutePreferenceStatus.visible.name])
            .sources(["TEST"])
            .object_classes(["mntner"])
            .finalise_statement()
        )
        assert str(db_query) == str(expected_statement)
        assert db_query.compile().params == expected_statement.compile().params

        assert not mock_dh.readonly
        assert mock_dh.closed
        assert mock_dh.queries[0] == RPSLDatabaseJournalStatisticsQuery()

    async def test_endpoint_unknown_get(self, monkeypatch, config_override):
        config_override(
            {
                "server": {"http": {"event_stream_access_list": "access_list"}},
                "access_lists": {"access_list": "testclient"},
            }
        )
        client = TestClient(app)
        response = client.get("/v1/event-stream/initial/", params={"unknown param": 2})
        assert response.status_code == 400
        assert response.text == "Unknown GET parameters: unknown param"

    async def test_endpoint_access_denied(self, monkeypatch, config_override):
        client = TestClient(app)
        response = client.get("/v1/event-stream/initial/", params={"unknown param": 2})
        assert response.status_code == 403


class TestEventStreamEndpoint:
    @pytest.mark.freeze_time("2022-03-14 12:34:56")
    async def test_endpoint(self, monkeypatch, config_override):
        config_override(
            {
                "sources": {
                    "TEST": {"keep_journal": True},
                    "IGNORED": {},
                },
                "server": {"http": {"event_stream_access_list": "access_list"}},
                "access_lists": {"access_list": "testclient"},
            }
        )

        mock_event_stream_follower = create_autospec_async_compat(AsyncEventStreamFollower)
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        monkeypatch.setattr("irrd.server.http.event_stream.DatabaseHandler", MockDatabaseHandler)
        monkeypatch.setattr(
            "irrd.server.http.event_stream.AsyncEventStreamFollower", mock_event_stream_follower
        )

        client = TestClient(app)
        with client.websocket_connect("/v1/event-stream/") as websocket:
            header = websocket.receive_json()
            assert header == {
                "message_type": "stream_status",
                "streamed_sources": ["TEST"],
                "last_reload_times": {"TEST": "2022-03-14T12:34:56"},
            }
            websocket.send_json({"message_type": "subscribe"})
            websocket.send_json({"message_type": "subscribe"})
            error = websocket.receive_json()
            assert error == {
                "message_type": "invalid_request",
                "errors": [{"msg": "The stream is already running, request ignored."}],
            }
            websocket.close()

        with client.websocket_connect("/v1/event-stream/") as websocket:
            websocket.receive_json()  # discard header
            websocket.send_json({"message_type": "invalid"})
            error = websocket.receive_json()
            # insert_assert(error)
            assert error["message_type"] == "invalid_request"

    async def test_endpoint_access_denied(self, monkeypatch, config_override):
        client = TestClient(app)
        with client.websocket_connect("/v1/event-stream/") as websocket:
            with pytest.raises(WebSocketDisconnect):
                websocket.receive_text()


class MockAsyncEventStreamRedisClient:
    @classmethod
    async def create(cls):
        return cls()

    def __init__(self):
        self.closed = False
        self.has_returned_entries = False

    async def get_entries(self, after_event_id: str) -> Tuple[StreamEntry, ...]:
        if self.has_returned_entries:
            await asyncio.sleep(10)
        self.has_returned_entries = True
        field_values: OrderedDict[Union[str, bytes], Union[str, bytes]] = OrderedDict(
            {"source": "TEST", "operation": OPERATION_JOURNAL_EXTENDED}
        )
        return (StreamEntry(identifier=after_event_id, field_values=field_values),)

    async def close(self):
        self.closed = True


class TestAsyncEventStreamFollower:
    @pytest.mark.parametrize("after_global_serial,expected_serial_starts", [(None, [43, 43]), (0, [1, 5])])
    async def test_follower_success(self, monkeypatch, after_global_serial, expected_serial_starts):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        monkeypatch.setattr("irrd.server.http.event_stream.DatabaseHandler", MockDatabaseHandler)
        monkeypatch.setattr(
            "irrd.server.http.event_stream.AsyncEventStreamRedisClient",
            MockAsyncEventStreamRedisClient,
        )

        messages = []

        async def message_callback(message):
            messages.append(message)

        follower = await AsyncEventStreamFollower.create("127.0.0.1", after_global_serial, message_callback)
        await asyncio.sleep(1)
        await follower.close()
        assert follower.stream_client.closed

        assert mock_dh.readonly
        assert mock_dh.closed
        assert mock_dh.queries[0] == RPSLDatabaseJournalStatisticsQuery()
        assert mock_dh.queries[1] == RPSLDatabaseJournalQuery().serial_global_range(
            expected_serial_starts.pop(0)
        )
        assert mock_dh.queries[2] == RPSLDatabaseJournalQuery().serial_global_range(
            expected_serial_starts.pop(0)
        )

        msg_journal1, event_journal_extended = messages

        assert msg_journal1["message_type"] == "rpsl_journal"
        assert msg_journal1["event_data"]["pk"] == "TEST-MNT"
        assert msg_journal1["event_data"]["serial_global"] == 4
        assert msg_journal1["event_data"]["parsed_data"]["auth"] == [
            "PGPKey-80F238C6",
            "CRYPT-Pw DummyValue",
            "MD5-pw DummyValue",
            "bcrypt-pw DummyValue",
        ]
        assert "DummyValue" in msg_journal1["event_data"]["object_text"]

        assert event_journal_extended == {
            "message_type": "event",
            "event_id": "$",
            "event_data": {"source": "TEST", "operation": "journal_extended"},
        }

    async def test_follower_invalid_serial(self, monkeypatch, event_loop):
        mock_dh = MockDatabaseHandler()
        mock_dh.reset_mock()
        monkeypatch.setattr("irrd.server.http.event_stream.DatabaseHandler", MockDatabaseHandler)

        messages = []

        async def message_callback(message):
            messages.append(message)

        follower = await AsyncEventStreamFollower.create("127.0.0.1", 10000, message_callback)
        await asyncio.sleep(1)
        assert not follower

        assert messages == [
            {
                "message_type": "invalid_request",
                "errors": [{"msg": "The maximum known serial is 42"}],
            }
        ]
