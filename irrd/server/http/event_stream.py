import asyncio
import csv
import datetime
import logging
import socket
import sys
import tempfile
from typing import Any, Callable, List, Optional

import pydantic
import ujson
from starlette.endpoints import HTTPEndpoint, WebSocketEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response, StreamingResponse
from starlette.status import WS_1003_UNSUPPORTED_DATA, WS_1008_POLICY_VIOLATION
from starlette.websockets import WebSocket
from typing_extensions import Literal

from irrd.conf import get_setting
from irrd.routepref.status import RoutePreferenceStatus
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.server.access_check import is_client_permitted
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.event_stream import (
    REDIS_STREAM_END_IDENTIFIER,
    AsyncEventStreamRedisClient,
)
from irrd.storage.queries import (
    DatabaseStatusQuery,
    RPSLDatabaseJournalQuery,
    RPSLDatabaseJournalStatisticsQuery,
    RPSLDatabaseQuery,
)
from irrd.utils.text import remove_auth_hashes
from irrd.vendor import postgres_copy

logger = logging.getLogger(__name__)


class EventStreamInitialDownloadEndpoint(HTTPEndpoint):
    async def get(self, request: Request) -> Response:
        assert request.client
        if not is_client_permitted(request.client.host, "server.http.event_stream_access_list"):
            return PlainTextResponse("Access denied", status_code=403)

        sources = request.query_params.get("sources")
        object_classes = request.query_params.get("object_classes")
        unknown_get_parameters = set(request.query_params.keys()) - {"sources", "object_classes"}
        if unknown_get_parameters:
            return PlainTextResponse(
                status_code=400, content=f"Unknown GET parameters: {', '.join(unknown_get_parameters)}"
            )
        return StreamingResponse(
            EventStreamInitialDownloadGenerator(
                request.client.host,
                sources.split(",") if sources else [],
                object_classes.split(",") if object_classes else [],
            ).stream_response(),
            media_type="application/jsonl+json",
        )


class EventStreamInitialDownloadGenerator:
    def __init__(self, host: str, sources: List[str], object_classes: List[str]):
        self.host = host
        self.sources = sources
        self.object_classes = object_classes
        self.dh = None

    async def stream_response(self):
        # This database handler is intentionally not read-only,
        # to make sure our queries run in a single transaction.
        self.dh = await DatabaseHandler.create_async()

        yield ujson.encode(await self.generate_header()) + "\n"
        async for row in self.generate_rows():
            yield ujson.encode(row) + "\n"
        self.dh.close()

    async def generate_rows(self):
        query = await self.generate_sql_query()

        with tempfile.TemporaryFile(mode="w+") as temp_csv:
            logger.debug(
                f"event stream {self.host}: received request for initial download, "
                f"copying data to temporary file {temp_csv.name}"
            )
            postgres_copy.copy_to(
                source=query.finalise_statement(),
                dest=temp_csv,
                engine_or_conn=self.dh._connection,
                format="csv",
            )

            temp_csv.seek(0)
            csv.field_size_limit(sys.maxsize)
            for row in csv.reader(temp_csv):
                pk, object_class, object_text, source, updated, parsed_data_text = row
                parsed_data = ujson.decode(parsed_data_text)
                if "auth" in parsed_data:
                    parsed_data["auth"] = [remove_auth_hashes(p) for p in parsed_data["auth"]]
                yield {
                    "pk": pk,
                    "object_class": object_class,
                    "object_text": remove_auth_hashes(object_text),
                    "source": source,
                    "updated": updated,
                    "parsed_data": parsed_data,
                }

    async def generate_sql_query(self):
        query = (
            RPSLDatabaseQuery(
                column_names=["rpsl_pk", "object_class", "object_text", "source", "updated", "parsed_data"]
            )
            .rpki_status([RPKIStatus.not_found.name, RPKIStatus.valid.name])
            .scopefilter_status([ScopeFilterStatus.in_scope.name])
            .route_preference_status([RoutePreferenceStatus.visible.name])
        )
        if self.sources:
            query = query.sources(self.sources)
        if self.object_classes:
            query = query.object_classes(self.object_classes)
        return query

    async def generate_header(self):
        journal_stats = next(await self.dh.execute_query_async(RPSLDatabaseJournalStatisticsQuery()))
        timestamp = journal_stats["max_timestamp"]
        return {
            "data_type": "irrd_event_stream_initial_download",
            "sources_filter": self.sources,
            "object_classes_filter": self.object_classes,
            "max_serial_global": journal_stats["max_serial_global"],
            "last_change_timestamp": timestamp.isoformat() if timestamp else None,
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "generated_on": socket.gethostname(),
        }


class EventStreamEndpoint(WebSocketEndpoint):
    encoding = "text"
    stream_follower = None
    websocket = None

    async def on_connect(self, websocket: WebSocket) -> None:
        assert websocket.client
        await websocket.accept()
        if not is_client_permitted(websocket.client.host, "server.http.event_stream_access_list"):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return

        self.websocket = websocket
        await self.send_header()

    async def send_header(self) -> None:
        journaled_sources = [
            name for name, settings in get_setting("sources").items() if settings.get("keep_journal")
        ]
        dh = DatabaseHandler(readonly=True)
        query = DatabaseStatusQuery().sources(journaled_sources)
        sources_created = {row["source"]: row["created"].isoformat() for row in dh.execute_query(query)}
        dh.close()

        await self.message_callback(
            {
                "message_type": "stream_status",
                "streamed_sources": journaled_sources,
                "last_reload_times": sources_created,
            }
        )

    async def message_callback(self, message: Any) -> None:
        assert self.websocket
        await self.websocket.send_text(ujson.encode(message))

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        assert websocket.client
        logger.debug(f"event stream {websocket.client.host}: received {data}")
        try:
            request = EventStreamSubscriptionRequest.parse_raw(data)
        except pydantic.ValidationError as exc:
            await websocket.send_json(
                {
                    "message_type": "invalid_request",
                    "errors": exc.errors(),
                }
            )
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            return

        if self.stream_follower:
            await websocket.send_json(
                {
                    "message_type": "invalid_request",
                    "errors": [{"msg": "The stream is already running, request ignored."}],
                }
            )
            return

        self.stream_follower = await AsyncEventStreamFollower.create(
            websocket.client.host, request.after_global_serial, self.message_callback
        )

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        if self.stream_follower:
            await self.stream_follower.close()
            self.stream_follower = None


class EventStreamSubscriptionRequest(pydantic.main.BaseModel):
    message_type: Literal["subscribe"]
    after_global_serial: Optional[int]


class AsyncEventStreamFollower:
    @classmethod
    async def create(
        cls, host: str, after_global_serial: Optional[int], callback: Callable
    ) -> Optional["AsyncEventStreamFollower"]:
        database_handler = await DatabaseHandler.create_async(readonly=True)
        stream_client = await AsyncEventStreamRedisClient.create()
        self = cls(host, database_handler, stream_client, callback)

        journal_stats = next(self.database_handler.execute_query(RPSLDatabaseJournalStatisticsQuery()))
        max_serial_global = journal_stats["max_serial_global"]

        if after_global_serial is not None:
            self.after_global_serial = after_global_serial
            if after_global_serial > max_serial_global:
                await self.callback(
                    {
                        "message_type": "invalid_request",
                        "errors": [{"msg": f"The maximum known serial is {max_serial_global}"}],
                    }
                )
                self.database_handler.close()
                return None
        else:
            self.after_global_serial = max_serial_global

        self.streaming_task = asyncio.create_task(self._run_monitor())
        return self

    def __init__(
        self,
        host: str,
        database_handler: DatabaseHandler,
        stream_client: AsyncEventStreamRedisClient,
        callback: Callable,
    ):
        self.streaming_task: Optional[asyncio.Task] = None
        self.host = host
        self.database_handler = database_handler
        self.stream_client = stream_client
        self.callback = callback

    async def _run_monitor(self) -> None:
        after_redis_event_id = REDIS_STREAM_END_IDENTIFIER
        logger.info(
            f"event stream {self.host}: sending entries from global serial {self.after_global_serial}"
        )
        await self._send_new_journal_entries()
        logger.debug(f"event stream {self.host}: initial send complete, waiting for new events")
        while True:
            entries = await self.stream_client.get_entries(after_redis_event_id)

            for entry in entries:
                await self.callback(
                    {
                        "message_type": "event",
                        "event_id": entry.identifier,
                        "event_data": entry.field_values,
                    }
                )
                after_redis_event_id = entry.identifier  # type: ignore
            # get_entries() times out every EVENT_STREAM_MAX_WAIT_MS,
            # to allow us to catch any incidentally missed journal entries
            await self._send_new_journal_entries()

    async def _send_new_journal_entries(self):
        query = RPSLDatabaseJournalQuery().serial_global_range(self.after_global_serial + 1)
        journal_entries = await self.database_handler.execute_query_async(query)

        for entry in journal_entries:
            object_text = remove_auth_hashes(entry["object_text"])
            # The message should include parsed_data (#685), but that info is not available
            # in the journal. Therefore, we reparse the object at the cost of some overhead.
            rpsl_obj = rpsl_object_from_text(object_text, strict_validation=False)
            await self.callback(
                {
                    "message_type": "rpsl_journal",
                    "event_data": {
                        "pk": entry["rpsl_pk"],
                        "source": entry["source"],
                        "operation": entry["operation"].name,
                        "object_class": entry["object_class"],
                        "serial_global": entry["serial_global"],
                        "serial_nrtm": entry["serial_nrtm"],
                        "origin": entry["origin"].name,
                        "timestamp": entry["timestamp"].isoformat(),
                        "object_text": object_text,
                        "parsed_data": rpsl_obj.parsed_data,
                    },
                }
            )
            self.after_global_serial = max([entry["serial_global"], self.after_global_serial])

        logger.debug(
            f"event stream {self.host}: sent new changes up to global serial {self.after_global_serial}"
        )

    async def close(self):
        if self.streaming_task.done():
            raise self.streaming_task.exception()  # pragma: no cover
        if self.streaming_task:
            self.streaming_task.cancel()
            self.streaming_task = None
        await self.stream_client.close()
        self.database_handler.close()
