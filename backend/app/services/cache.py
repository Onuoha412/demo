"""Optional Redis cache/pub-sub integration.

PostgreSQL remains the source of truth. Redis accelerates coordination but is
not required for queue mutations to persist.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from ..config import settings


class CacheService:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url if redis_url is not None else settings.redis_url
        self._client: Any = None
        self._initialised = False
        self._local_tickets: dict[str, tuple[dict[str, str], float]] = {}

    async def _get_client(self) -> Any:
        if self._initialised:
            return self._client
        self._initialised = True
        if not self.redis_url:
            return None
        try:
            from redis.asyncio import Redis

            client = Redis.from_url(self.redis_url, decode_responses=True)
            await client.ping()
            self._client = client
        except Exception:
            self._client = None
        return self._client

    async def publish(self, channel: str, message: dict[str, Any]) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.publish(channel, json.dumps(message, default=str))
            return True
        except Exception:
            return False

    async def set_json(self, key: str, value: Any, expire_seconds: int = 60) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.set(key, json.dumps(value, default=str), ex=expire_seconds)
            return True
        except Exception:
            return False

    async def increment_with_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        client = await self._get_client()
        if client is None:
            return True
        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window_seconds)
            return count <= limit
        except Exception:
            return True

    async def issue_websocket_ticket(self, user_id: str, queue_id: str) -> str:
        ticket = secrets.token_urlsafe(32)
        payload = {"user_id": user_id, "queue_id": queue_id}
        client = await self._get_client()
        key = f"{settings.realtime_channel_prefix}ws-ticket:{ticket}"
        if client is not None:
            try:
                await client.set(key, json.dumps(payload), ex=30, nx=True)
                return ticket
            except Exception:
                pass
        self._local_tickets[ticket] = (payload, time.monotonic() + 30)
        return ticket

    async def consume_websocket_ticket(self, ticket: str) -> dict[str, str] | None:
        client = await self._get_client()
        key = f"{settings.realtime_channel_prefix}ws-ticket:{ticket}"
        if client is not None:
            try:
                value = await client.getdel(key)
                return json.loads(value) if value else None
            except Exception:
                pass
        stored = self._local_tickets.pop(ticket, None)
        if stored is None or stored[1] < time.monotonic():
            return None
        return stored[0]

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None


cache = CacheService()
