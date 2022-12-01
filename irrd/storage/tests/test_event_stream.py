from ..event_stream import EventStreamPublisher, AsyncEventStreamRedisClient, REDIS_STREAM_END_IDENTIFIER

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
        entries = await client.get_entries("0-0")
        assert entries[0].field_values == {
            "source": "TEST",
            "operation": "journal_extended",
        }
        assert entries[1].field_values == {
            "source": "TEST",
            "operation": "full_reload",
        }

        publisher.close()
        await client.close()
