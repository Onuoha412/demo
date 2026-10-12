"""Process-local, short-lived state for a single backend instance."""

from __future__ import annotations

import asyncio
import secrets
import time


class CacheService:
    def __init__(self) -> None:
        self._local_tickets: dict[str, tuple[dict[str, str], float]] = {}
        self._google_nonces: dict[str, float] = {}
        self._rate_limits: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def increment_with_limit(self, key: str, limit: int, window_seconds: int) -> bool:
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
        async with self._lock:
            stored = self._local_tickets.pop(ticket, None)
        if stored is None or stored[1] < time.monotonic():
            return None
        return stored[0]

    async def issue_google_nonce(self, nonce: str) -> None:
        now = time.monotonic()
        async with self._lock:
            self._google_nonces[nonce] = now + 300
            if len(self._google_nonces) > 10000:
                self._google_nonces = {
                    key: expires_at
                    for key, expires_at in self._google_nonces.items()
                    if expires_at > now
                }

    async def consume_google_nonce(self, nonce: str) -> bool:
        async with self._lock:
            expires_at = self._google_nonces.pop(nonce, None)
        return expires_at is not None and expires_at > time.monotonic()

    async def close(self) -> None:
        async with self._lock:
            self._local_tickets.clear()
            self._rate_limits.clear()
            self._google_nonces.clear()


cache = CacheService()
