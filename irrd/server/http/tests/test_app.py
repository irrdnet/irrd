import limits.aio.strategies
import limits.storage
import pytest

from ..app import rate_limiter_storage_url


@pytest.mark.parametrize(
    "redis_url,expected",
    [
        ("redis://localhost", "async+redis://localhost"),
        ("redis://localhost/4", "async+redis://localhost/4"),
        ("redis://localhost:6379", "async+redis://localhost:6379"),
        ("rediss://localhost", "async+rediss://localhost"),
        ("valkey://localhost", "async+valkey://localhost"),
        ("valkeys://localhost", "async+valkeys://localhost"),
        ("unix:///var/run/redis.sock", "async+redis+unix:///var/run/redis.sock"),
    ],
)
def test_rate_limiter_storage_url(redis_url, expected):
    url = rate_limiter_storage_url(redis_url)
    assert url == expected
    # The storage must be an async one, or the HTTP worker fails to start.
    storage = limits.storage.storage_from_string(url, implementation="valkey")
    limits.aio.strategies.MovingWindowRateLimiter(storage)
