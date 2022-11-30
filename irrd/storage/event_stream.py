import asyncio
import logging
from typing import Tuple

import coredis
import redis
from coredis.response.types import StreamInfo, StreamEntry

from irrd.conf import get_setting

EVENT_STREAM_MAX_WAIT_MS = 60000

OPERATION_FULL_RELOAD = 'full_reload'
OPERATION_JOURNAL_EXTENDED = 'journal_extended'

EVENT_STREAM_WS_CHUNK_SIZE = 1000
REDIS_STREAM_RPSL = 'irrd-eventstream-rpsl-stream'
REDIS_STREAM_MAX_LEN = 1000


class AsyncEventStreamRedisClient:
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

    async def journal_status(self) -> StreamInfo:
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
            block=EVENT_STREAM_MAX_WAIT_MS,
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
        self._redis_conn = redis.Redis.from_url(get_setting('redis_url'), decode_responses=True)

    def publish_update(self, source) -> None:
        self._redis_conn.xadd(
            name=REDIS_STREAM_RPSL,
            maxlen=REDIS_STREAM_MAX_LEN,
            fields={
                'source': source,
                'operation': OPERATION_JOURNAL_EXTENDED,
            }
        )

    def publish_rpsl_full_reload(self, source: str) -> None:
        self._redis_conn.xadd(
            name=REDIS_STREAM_RPSL,
            maxlen=REDIS_STREAM_MAX_LEN,
            fields={
                'source': source,
                'operation': OPERATION_FULL_RELOAD,
            }
        )
        return

    def close(self):
        self._redis_conn.close()
