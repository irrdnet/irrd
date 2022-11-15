import asyncio
import csv
import datetime
import logging
import socket
import sys
import tempfile
from typing import Literal, Any, List, Optional

import pydantic
import ujson
from starlette.endpoints import WebSocketEndpoint, HTTPEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.status import WS_1003_UNSUPPORTED_DATA
from starlette.websockets import WebSocket

from irrd.conf import get_setting
from irrd.rpki.status import RPKIStatus
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.scopefilter.status import ScopeFilterStatus
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.event_stream import AsyncEventStreamClient
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseJournalQuery, RPSLDatabaseQuery, \
    RPSLDatabaseJournalStatisticsQuery
from irrd.utils.text import remove_auth_hashes
from irrd.vendor import postgres_copy

logger = logging.getLogger(__name__)


class EventStreamInitialDownloadEndpoint(HTTPEndpoint):
    async def get(self, request: Request) -> Response:
        sources = request.query_params.get('sources')
        object_classes = request.query_params.get('object_classes')
        return StreamingResponse(
            self.stream_response(
                sources.split(',') if sources else [],
                object_classes.split(',') if object_classes else [],
            ),
            media_type='application/jsonl+json'
        )

    async def stream_response(self, sources: List[str], object_classes: List[str]):
        # This database handler is intentionally not read-only,
        # to make sure our queries run in a single transaction.
        dh = await DatabaseHandler.create_async()

        journal_stats = next(dh.execute_query(RPSLDatabaseJournalStatisticsQuery()))
        yield ujson.encode({
            'data_type': 'irrd_event_stream_initial_download',
            'sources_filter': sources,
            'object_classes_filter': object_classes,
            'max_serial_journal': journal_stats['max_serial_journal'],
            'last_change_timestamp': journal_stats['max_timestamp'].isoformat(),
            'generated_at': datetime.datetime.utcnow().isoformat(),
            'generated_on': socket.gethostname(),
        }) + '\n'

        query = RPSLDatabaseQuery(column_names=[
            'rpsl_pk', 'object_class', 'object_text', 'source', 'updated', 'parsed_data'
        ]).rpki_status(
            [RPKIStatus.not_found.name, RPKIStatus.valid.name]
        ).scopefilter_status(
            [ScopeFilterStatus.in_scope.name]
        )
        if sources:
            query = query.sources(sources)
        if object_classes:
            query = query.object_classes(object_classes)

        with tempfile.TemporaryFile(mode='w+') as fp:
            logger.info(f'Writing to {fp} rows from copy query {query}')
            postgres_copy.copy_to(
                query.finalise_statement(),
                fp,
                dh._connection,
                format='csv'
            )
            logger.info('Wrote rows, now reading')
            fp.seek(0)
            csv.field_size_limit(sys.maxsize)
            for row in csv.reader(fp):
                pk, object_class, object_text, source, updated, parsed_data_text = row
                parsed_data = ujson.decode(parsed_data_text)
                if 'auth' in parsed_data:
                    parsed_data['auth'] = [remove_auth_hashes(p) for p in parsed_data['auth']]
                yield ujson.encode({
                    'pk': pk,
                    'object_class': object_class,
                    'object_text': remove_auth_hashes(object_text),
                    'source': source,
                    'updated': updated,
                    'parsed_data': parsed_data,
                }) + '\n'
        dh.close()


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
        after_journal_serial = await self._send_new_journal_entries(websocket, after_journal_serial)
        while True:
            entries = await self.stream_client.get_entries(after_event_id)

            for entry in entries:
                await websocket.send_text(ujson.encode({
                    'message_type': 'event_rpsl',
                    'rpsl_event_id': entry.identifier,
                    'event_data': entry.field_values,
                }))
                after_event_id = entry.identifier  # type: ignore
            # get_entries() times out every EVENT_STREAM_MAX_WAIT_MS,
            # to allow us to catch any incidentally missed journal entries
            after_journal_serial = await self._send_new_journal_entries(websocket, after_journal_serial)

    async def _send_new_journal_entries(self, websocket: WebSocket, after_journal_serial: int) -> int:
        assert self.database_handler
        query = RPSLDatabaseJournalQuery().serial_journal_range(after_journal_serial + 1)
        journal_entries = await self.database_handler.execute_query_async(query)

        for entry in journal_entries:
            object_text = remove_auth_hashes(entry['object_text'])
            rpsl_obj = rpsl_object_from_text(object_text, strict_validation=False)
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
                    'object_text': object_text,
                    'parsed_data': rpsl_obj.parsed_data,
                }
            }))
            after_journal_serial = max([entry['serial_journal'], after_journal_serial])

        return after_journal_serial

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
        journal_stats = next(self.database_handler.execute_query(RPSLDatabaseJournalStatisticsQuery()))
        max_serial_journal = journal_stats['max_serial_journal']
        if request.after_journal_serial:
            if request.after_journal_serial > max_serial_journal:
                await websocket.send_json({
                    'message_type': 'invalid_request',
                    'errors': [{'msg': f'The maximum known serial is {max_serial_journal}'}],
                })
                self.database_handler.close()
                return

            after_journal_serial = request.after_journal_serial
        else:
            after_journal_serial = max_serial_journal

        self.streaming_task = asyncio.create_task(self._run_monitor(websocket, after_journal_serial))

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
    after_journal_serial: Optional[int]

# {"message_type": "subscribe", "event_type": "rpsl", "after_event_id": "1-0"}
