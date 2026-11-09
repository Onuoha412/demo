import asyncio
from unittest.mock import AsyncMock

from app.services.cache import CacheService


def test_redis_rate_limit_is_atomic_and_sets_expiry() -> None:
    cache = CacheService()
    redis = AsyncMock()
    redis.incr.return_value = 1
    cache._redis = redis

    assert asyncio.run(cache.increment_with_limit("rate-key", 5, 60)) is True
    redis.incr.assert_awaited_once_with("rate-key")
    redis.expire.assert_awaited_once_with("rate-key", 60)


def test_redis_websocket_ticket_is_single_use() -> None:
    cache = CacheService()
    redis = AsyncMock()
    redis.getdel.return_value = "user-1:queue-1"
    cache._redis = redis

    assert asyncio.run(cache.consume_websocket_ticket("ticket")) == {
        "user_id": "user-1",
        "queue_id": "queue-1",
    }
    redis.getdel.assert_awaited_once_with("queueless:ws-ticket:ticket")
