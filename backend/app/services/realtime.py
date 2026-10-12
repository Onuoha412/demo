"""Process-local broadcasts to connected queue clients."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from fastapi import WebSocket
import sentry_sdk

from ..config import settings
from .cache import cache


class RealtimeManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()

    async def stop(self) -> None:
        self._connections.clear()
        self._loop = None

    async def connect(self, queue_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[queue_id].add(websocket)

    def disconnect(self, queue_id: UUID, websocket: WebSocket) -> None:
        subscribers = self._connections.get(queue_id)
        if subscribers:
            subscribers.discard(websocket)
            if not subscribers:
                self._connections.pop(queue_id, None)

    async def publish(self, queue_id: UUID, event: str, data: Any = None) -> None:
        message = {
            "event": event,
            "type": event,
            "queue_id": str(queue_id),
            "data": jsonable_encoder(data),
        }
        await self._broadcast(queue_id, message)

    async def _broadcast(self, queue_id: UUID, message: dict[str, Any]) -> None:
        subscribers = list(self._connections.get(queue_id, ()))
        if subscribers:
            results = await asyncio.gather(
                *(socket.send_json(message) for socket in subscribers),
                return_exceptions=True,
            )
            for socket, result in zip(subscribers, results):
                if isinstance(result, Exception):
                    sentry_sdk.capture_message(
                        "QueueLess WebSocket event delivery failed",
                        level="warning",
                    )
                    self.disconnect(queue_id, socket)

    def publish_nowait(self, queue_id: UUID, event: str, data: Any = None) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(
                    self._loop.create_task, self.publish(queue_id, event, data)
                )
            return
        loop.create_task(self.publish(queue_id, event, data))

    async def allow_connection(self, queue_id: UUID) -> bool:
        return await cache.increment_with_limit(
            f"{settings.realtime_channel_prefix}{queue_id}:connections",
            limit=100,
            window_seconds=60,
        )


realtime = RealtimeManager()
