import asyncio
import logging
from typing import Literal, Any

import pydantic
import ujson
from starlette.endpoints import WebSocketEndpoint
from starlette.status import WS_1003_UNSUPPORTED_DATA
from starlette.websockets import WebSocket

from irrd.conf import get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.event_stream import AsyncEventStreamClient, OPERATION_JOURNAL_EXTENDED
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseJournalQuery
from irrd.utils.text import remove_auth_hashes

logger = logging.getLogger(__name__)


class EventStreamEndpoint(WebSocketEndpoint):
    encoding = "text"
    streaming_task = None
    stream_client = None
    database_handler = None

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

        await websocket.send_json({
            'message_type': 'stream_status',
            'streamed_sources': journaled_sources,
            'last_reload_times': sources_created,
        })

    async def _run_monitor(self, websocket: WebSocket, after_journal_serial: int) -> None:
        assert self.stream_client
        after_event_id = '$'
        logging.debug(f'ws {websocket} starting run after serial {after_journal_serial} after event {after_event_id} about to send initial')
        after_journal_serial = await self._send_new_journal_entries(websocket, after_journal_serial)
        while True:
            # TODO: timeout to periodically catch straggling entries?
            logging.debug(
                f'ws {websocket} waiting run after serial {after_journal_serial} after event {after_event_id}')
            entries = await self.stream_client.get_entries(after_event_id)
            if not entries:
                continue
            logging.debug(
                f'ws {websocket} received entries')

            for entry in entries:
                await websocket.send_text(ujson.encode({
                    'message_type': 'event_rpsl',
                    'rpsl_event_id': entry.identifier,
                    'event_data': entry.field_values,
                }))
                after_event_id = entry.identifier  # type: ignore
            if any([
                entry.field_values['operation'] == OPERATION_JOURNAL_EXTENDED
                for entry in entries
            ]):
                logging.debug(
                    f'ws {websocket} match journal extend, starting run after serial {after_journal_serial}')

                after_journal_serial = await self._send_new_journal_entries(websocket, after_journal_serial)

    async def _send_new_journal_entries(self, websocket: WebSocket, after_journal_serial: int) -> int:
        assert self.database_handler
        query = RPSLDatabaseJournalQuery().serial_journal_range(after_journal_serial + 1)
        journal_entries = await self.database_handler.execute_query_async(query)
        new_highest_serial_journal = 0

        for entry in journal_entries:
            await websocket.send_text(ujson.encode({
                'message_type': 'rpsl_journal',
                'event_data': {
                    'pk': entry['rpsl_pk'],
                    'source': entry['source'],
                    'operation': entry['operation'].name,
                    'object_class': entry['object_class'],
                    'serial_journal': entry['serial_journal'],
                    'serial_nrtm': entry['serial_nrtm'],
                    'origin': entry['origin'].name,
                    'timestamp': entry['timestamp'].isoformat(),
                    'object_text': remove_auth_hashes(entry['object_text']),
                }
            }))
            new_highest_serial_journal = max([entry['serial_journal'], new_highest_serial_journal])

        return new_highest_serial_journal

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

        self.database_handler = await DatabaseHandler.create_async(readonly=True)
        self.streaming_task = asyncio.create_task(self._run_monitor(websocket, request.after_journal_serial))

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        if self.streaming_task:
            self.streaming_task.cancel()
            self.streaming_task = None
        if self.stream_client:
            await self.stream_client.close()
        if self.database_handler:
            self.database_handler.close()


class EventStreamSubscriptionRequest(pydantic.main.BaseModel):
    message_type: Literal['subscribe']
    event_type: Literal['rpsl']
    after_journal_serial: int

# {"message_type": "subscribe", "event_type": "rpsl", "after_event_id": "1-0"}
