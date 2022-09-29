import asyncio
import datetime
from typing import Tuple

import coredis
import redis
from coredis.response.types import StreamInfo, StreamEntry

from irrd.utils.text import remove_auth_hashes
from ..conf import get_setting
from ..storage.models import JournalEntryOrigin, DatabaseOperation

EVENT_STREAM_WS_CHUNK_SIZE = 1000
REDIS_STREAM_RPSL = 'irrd-eventstream-rpsl'


class AsyncEventStreamClient:
    @classmethod
    async def create(cls):
        redis_conn = await coredis.Redis(
            **redis.connection.parse_url(get_setting('redis_url')),
            protocol_version=2,
            decode_responses=True
        )
        return cls(redis_conn)

    def __init__(self, redis_conn: coredis.Redis):
        self.redis_conn = redis_conn

    async def stream_status(self) -> StreamInfo:
        stream_status = None
        while not stream_status:
            try:
                stream_status = await self.redis_conn.xinfo_stream(REDIS_STREAM_RPSL)
            except (coredis.exceptions.ConnectionError, coredis.exceptions.ResponseError):
                await asyncio.sleep(1)
        return stream_status

    async def get_entries(self, after_event_id: str) -> Tuple[StreamEntry, ...]:
        entries = await self.redis_conn.xread(
            streams={REDIS_STREAM_RPSL: after_event_id},
            block=False,
            count=EVENT_STREAM_WS_CHUNK_SIZE,
        )
        if not entries or REDIS_STREAM_RPSL not in entries:
            return ()
        return entries[REDIS_STREAM_RPSL]

    async def close(self):
        if self.redis_conn:
            await self.redis_conn.quit()
            self.redis_conn = None


class EventStreamPublisher:
    def __init__(self):
        self._redis_conn = redis.Redis.from_url(get_setting('redis_url'))

    def publish_rpsl_journal(self, rpsl_pk: str, source: str, operation: DatabaseOperation,
                             object_class: str, object_text: str, serial_journal: int, serial_nrtm: int,
                             origin: JournalEntryOrigin, timestamp: datetime.datetime) -> None:
        entry_id = f'{serial_journal}-{serial_nrtm}'
        self._redis_conn.xadd(
            name=REDIS_STREAM_RPSL,
            id=entry_id,
            # TODO: limit to maxlen
            fields={
                'pk': rpsl_pk,
                'source': source,
                'operation': operation.name,
                'object_class': object_class,
                'serial_journal': serial_journal,
                'serial_nrtm': serial_nrtm,
                'origin': origin.name,
                'timestamp': timestamp.isoformat(),
                'object_text': remove_auth_hashes(object_text),
            }
        )

    def close(self):
        self._redis_conn.close()
