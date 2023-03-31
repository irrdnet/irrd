from ..event_stream import (
    REDIS_STREAM_END_IDENTIFIER,
    AsyncEventStreamRedisClient,
    EventStreamPublisher,
)

# Use different stores in tests
TEST_REDIS_STREAM_RPSL = "TEST-irrd-eventstream-rpsl-stream"


class TestRedisEventStream:
    async def test_event_stream(self, monkeypatch):
        monkeypatch.setattr("irrd.storage.event_stream.REDIS_STREAM_RPSL", TEST_REDIS_STREAM_RPSL)
        monkeypatch.setattr("irrd.storage.event_stream.EVENT_STREAM_MAX_WAIT_MS", 1)

        publisher = EventStreamPublisher()
        publisher.reset_stream()
        client = await AsyncEventStreamRedisClient.create()

        publisher.publish_update("TEST")
        publisher.publish_rpsl_full_reload("TEST")

        assert await client.get_entries(REDIS_STREAM_END_IDENTIFIER) == ()
        journal_extended_entry, full_reload_entry = await client.get_entries("0-0")

        assert journal_extended_entry.field_values == {
            "source": "TEST",
            "operation": "journal_extended",
        }
        assert full_reload_entry.field_values == {
            "source": "TEST",
            "operation": "full_reload",
        }

        publisher.close()
        await client.close()
