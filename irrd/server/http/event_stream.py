import asyncio
from typing import Literal, Any

import pydantic
import ujson
from starlette.endpoints import WebSocketEndpoint
from starlette.status import WS_1003_UNSUPPORTED_DATA
from starlette.websockets import WebSocket

from irrd.conf import get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.event_stream import AsyncEventStreamClient
from irrd.storage.queries import DatabaseStatusQuery


class EventStreamEndpoint(WebSocketEndpoint):
    encoding = "text"
    streaming_task = None
    stream_client = None

    async def on_connect(self, websocket: WebSocket) -> None:
        # TODO: this logs an exception for HTTP requests
        await websocket.accept()
        self.stream_client = await AsyncEventStreamClient.create()

        journaled_sources = [
            name
            for name, settings in get_setting('sources').items()
            if settings.get('keep_journal')
        ]
        dh = DatabaseHandler(readonly=True)
        query = DatabaseStatusQuery().sources(journaled_sources)
        sources_created = {
            row['source']: row['created'].isoformat()
            for row in dh.execute_query(query)
        }
        dh.close()

        stream_status = await self.stream_client.stream_status()

        await websocket.send_json({
            'message_type': 'stream_status',
            'event_id_first': stream_status['first-entry'].identifier if stream_status['first-entry'] else None,
            'event_id_last': stream_status['last-entry'].identifier if stream_status['last-entry'] else None,
            'streamed_sources': journaled_sources,
            'last_reload_times': sources_created,
        })

    async def _run_monitor(self, websocket: WebSocket, after_event_id: str):
        assert self.stream_client
        while True:
            entries = await self.stream_client.get_entries(after_event_id)
            if not entries:
                continue
            for entry in entries:
                await websocket.send_text(ujson.encode({
                    'message_type': 'event_rpsl',
                    'rpsl_event_id': entry.identifier,
                    'event_data': entry.field_values,
                }))
                after_event_id = entry.identifier  # type: ignore

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        try:
            request = EventStreamSubscriptionRequest.parse_raw(data)
        except pydantic.ValidationError as exc:
            await websocket.send_json({
                'message_type': 'invalid_request',
                'errors': exc.errors(),
            })
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            return

        if self.streaming_task:
            await websocket.send_json({
                'message_type': 'invalid_request',
                'errors': [{'msg': 'The stream is already running, request ignored.'}],
            })
            return

        self.streaming_task = asyncio.create_task(self._run_monitor(websocket, request.after_event_id))

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        if self.streaming_task:
            self.streaming_task.cancel()
            self.streaming_task = None
        if self.stream_client:
            await self.stream_client.close()


class EventStreamSubscriptionRequest(pydantic.main.BaseModel):
    message_type: Literal['subscribe']
    event_type: Literal['rpsl']
    after_event_id: str

# {"message_type": "subscribe", "event_type": "rpsl", "after_event_id": "1-0"}
