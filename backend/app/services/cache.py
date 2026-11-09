"""Shared short-lived state for rate limits and one-time WebSocket tickets."""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any

from redis.asyncio import Redis

from ..config import settings


class CacheService:
    def __init__(self) -> None:
        self._redis: Redis[str] | None = (
            Redis.from_url(settings.redis_url, decode_responses=True)
            if settings.redis_url
            else None
        )
        self._local_tickets: dict[str, tuple[dict[str, str], float]] = {}
        self._rate_limits: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def increment_with_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        if self._redis is not None:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, window_seconds)
            return count <= limit
        now = time.monotonic()
        async with self._lock:
            count, expires_at = self._rate_limits.get(key, (0, 0))
            if expires_at <= now:
                count, expires_at = 0, now + window_seconds
            count += 1
            self._rate_limits[key] = (count, expires_at)
            if len(self._rate_limits) > 10000:
                self._rate_limits = {
                    item_key: item for item_key, item in self._rate_limits.items()
                    if item[1] > now
                }
            return count <= limit

    async def issue_websocket_ticket(self, user_id: str, queue_id: str) -> str:
        if self._redis is not None:
            ticket = secrets.token_urlsafe(32)
            await self._redis.set(
                f"queueless:ws-ticket:{ticket}",
                f"{user_id}:{queue_id}",
                ex=30,
            )
            return ticket
        now = time.monotonic()
        ticket = secrets.token_urlsafe(32)
        async with self._lock:
            self._local_tickets[ticket] = (
                {"user_id": user_id, "queue_id": queue_id},
                now + 30,
            )
            if len(self._local_tickets) > 10000:
                self._local_tickets = {
                    key: value for key, value in self._local_tickets.items()
                    if value[1] > now
                }
        return ticket

    async def consume_websocket_ticket(self, ticket: str) -> dict[str, str] | None:
        if self._redis is not None:
            value = await self._redis.getdel(f"queueless:ws-ticket:{ticket}")
            if not value:
                return None
            user_id, separator, queue_id = value.partition(":")
            if not separator or not user_id or not queue_id:
                return None
            return {"user_id": user_id, "queue_id": queue_id}
        async with self._lock:
            stored = self._local_tickets.pop(ticket, None)
        if stored is None or stored[1] < time.monotonic():
            return None
        return stored[0]

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            return
        async with self._lock:
            self._local_tickets.clear()
            self._rate_limits.clear()

    async def ping(self) -> bool:
        if self._redis is None:
            return True
        return bool(await self._redis.ping())


cache = CacheService()
