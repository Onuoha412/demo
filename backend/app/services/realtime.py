"""In-process queue broadcasts with optional Redis fan-out."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from fastapi import WebSocket

from ..config import settings
from .cache import cache


class RealtimeManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, queue_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._loop = asyncio.get_running_loop()
        self._connections[queue_id].add(websocket)

    def disconnect(self, queue_id: UUID, websocket: WebSocket) -> None:
        subscribers = self._connections.get(queue_id)
        if subscribers:
            subscribers.discard(websocket)
            if not subscribers:
                self._connections.pop(queue_id, None)
        if not self._connections:
                self._loop = None

    async def publish(self, queue_id: UUID, event: str, data: Any = None) -> None:
        # ``event`` is the public contract used by the existing clients;
        # ``type`` is retained for consumers following common WS conventions.
        message = {
            "event": event,
            "type": event,
            "queue_id": str(queue_id),
            "data": jsonable_encoder(data),
        }
        subscribers = list(self._connections.get(queue_id, ()))
        if subscribers:
            results = await asyncio.gather(
                *(socket.send_json(message) for socket in subscribers),
                return_exceptions=True,
            )
            for socket, result in zip(subscribers, results):
                if isinstance(result, Exception):
                    self.disconnect(queue_id, socket)
        await cache.publish(f"{settings.realtime_channel_prefix}{queue_id}", message)
        await cache.set_json(f"{settings.realtime_channel_prefix}{queue_id}:active", message, 120)

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
