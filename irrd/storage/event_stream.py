from collections import namedtuple

import valkey
import valkey.asyncio

from irrd.conf import get_setting

EVENT_STREAM_MAX_WAIT_MS = 60000

OPERATION_FULL_RELOAD = "full_reload"
OPERATION_JOURNAL_EXTENDED = "journal_extended"

EVENT_STREAM_WS_CHUNK_SIZE = 1000
REDIS_STREAM_RPSL = "irrd-eventstream-rpsl-stream"
REDIS_STREAM_MAX_LEN = 1000
REDIS_STREAM_END_IDENTIFIER = "$"

EventStreamEntry = namedtuple("EventStreamEntry", ["identifier", "field_values"])


class AsyncEventStreamRedisClient:
    @classmethod
    async def create(cls):
        redis_conn = valkey.asyncio.Valkey.from_url(get_setting("redis_url"), decode_responses=True)
        return cls(redis_conn)

    def __init__(self, redis_conn: valkey.asyncio.Valkey):
        self.redis_conn = redis_conn

    async def get_entries(self, after_event_id: str) -> tuple[EventStreamEntry, ...]:
        streams = await self.redis_conn.xread(
            streams={REDIS_STREAM_RPSL: after_event_id},
            block=EVENT_STREAM_MAX_WAIT_MS,
            count=EVENT_STREAM_WS_CHUNK_SIZE,
        )
        if not streams:
            return ()
        _, entries = streams[0]
        return tuple(EventStreamEntry(identifier, fields) for identifier, fields in entries)

    async def close(self):
        await self.redis_conn.aclose()


class EventStreamPublisher:
    def __init__(self):
        self._redis_conn = valkey.Valkey.from_url(get_setting("redis_url"), decode_responses=True)

    def reset_stream(self) -> None:
        self._redis_conn.delete(REDIS_STREAM_RPSL.encode())

    def publish_update(self, source) -> None:
        self._redis_conn.xadd(
            name=REDIS_STREAM_RPSL,
            maxlen=REDIS_STREAM_MAX_LEN,
            fields={
                "source": source,
                "operation": OPERATION_JOURNAL_EXTENDED,
            },
        )

    def publish_rpsl_full_reload(self, source: str) -> None:
        self._redis_conn.xadd(
            name=REDIS_STREAM_RPSL,
            maxlen=REDIS_STREAM_MAX_LEN,
            fields={
                "source": source,
                "operation": OPERATION_FULL_RELOAD,
            },
        )

    def close(self):
        self._redis_conn.close()
