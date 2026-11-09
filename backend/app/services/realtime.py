"""Process-local broadcasts to connected queue clients."""

from __future__ import annotations

import asyncio
import json
import secrets
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from fastapi import WebSocket
import sentry_sdk
from redis.asyncio import Redis

from ..config import settings
from .cache import cache


class RealtimeManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._feedback_connections: dict[
            WebSocket, tuple[UUID, UUID | None, str]
        ] = {}
        self._super_admin_connections: set[WebSocket] = set()
        self._announcement_connections: dict[
            WebSocket, tuple[str, str | None]
        ] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._redis: Redis[str] | None = None
        self._pubsub = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._publish_tasks: set[asyncio.Task[None]] = set()
        self._instance_id = secrets.token_urlsafe(12)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if settings.redis_url:
            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(settings.realtime_pubsub_channel)
            self._subscriber_task = asyncio.create_task(self._listen_for_broadcasts())

    async def stop(self) -> None:
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None
        publish_tasks = tuple(self._publish_tasks)
        for task in publish_tasks:
            task.cancel()
        if publish_tasks:
            await asyncio.gather(*publish_tasks, return_exceptions=True)
        self._publish_tasks.clear()
        if self._pubsub is not None:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        self._connections.clear()
        self._feedback_connections.clear()
        self._super_admin_connections.clear()
        self._announcement_connections.clear()
        self._loop = None

    async def _listen_for_broadcasts(self) -> None:
        if self._pubsub is None:
            return
        async for message in self._pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                envelope = json.loads(message["data"])
                if envelope.get("source") == self._instance_id:
                    continue
                await self._broadcast(
                    UUID(envelope["queue_id"]),
                    envelope["message"],
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                sentry_sdk.capture_message(
                    "QueueLess received an invalid realtime broadcast",
                    level="warning",
                )

    async def connect_super_admin(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._super_admin_connections.add(websocket)

    def disconnect_super_admin(self, websocket: WebSocket) -> None:
        self._super_admin_connections.discard(websocket)

    async def connect_announcements(
        self,
        websocket: WebSocket,
        role: str,
        organization_id: str | None = None,
    ) -> None:
        await websocket.accept()
        self._announcement_connections[websocket] = (role, organization_id)

    def disconnect_announcements(self, websocket: WebSocket) -> None:
        self._announcement_connections.pop(websocket, None)

    async def publish_announcement(
        self,
        audience: str,
        data: dict[str, Any],
        event: str,
        organization_id: str | None = None,
    ) -> None:
        recipients = [
            socket
            for socket, (role, subscriber_organization_id) in
            self._announcement_connections.items()
            if (
                role == "super_admin"
                or (
                    organization_id is None
                    and (role == "admin" or audience == "all" or audience == role)
                )
                or (
                    organization_id is not None
                    and subscriber_organization_id == organization_id
                    and role in {"admin", "staff"}
                )
            )
        ]
        if not recipients:
            return
        message = {"event": event, "data": jsonable_encoder(data)}
        results = await asyncio.gather(
            *(socket.send_json(message) for socket in recipients),
            return_exceptions=True,
        )
        for socket, result in zip(recipients, results):
            if isinstance(result, Exception):
                sentry_sdk.capture_message(
                    "QueueLess announcement event delivery failed",
                    level="warning",
                )
                self.disconnect_announcements(socket)

    def publish_announcement_nowait(
        self,
        audience: str,
        data: dict[str, Any],
        event: str,
        organization_id: str | None = None,
    ) -> None:
        coroutine = self.publish_announcement(
            audience,
            data,
            event,
            organization_id=organization_id,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.create_task, coroutine)
            else:
                coroutine.close()
            return
        loop.create_task(coroutine)

    async def connect_feedback(
        self,
        websocket: WebSocket,
        user_id: UUID,
        organization_id: UUID | None,
        role: str,
    ) -> None:
        await websocket.accept()
        self._feedback_connections[websocket] = (user_id, organization_id, role)

    def disconnect_feedback(self, websocket: WebSocket) -> None:
        self._feedback_connections.pop(websocket, None)

    async def publish_feedback(
        self,
        *,
        report_id: UUID,
        reporter_user_id: UUID | None,
        assigned_user_id: UUID | None,
        organization_id: UUID | None,
        category: str,
        event: str,
        status: str,
    ) -> None:
        message = {
            "event": event,
            "report_id": str(report_id),
            "status": status,
        }
        deliveries: list[tuple[WebSocket, bool]] = []
        for websocket, (user_id, org_id, role) in list(
            self._feedback_connections.items()
        ):
            is_owner = reporter_user_id is not None and reporter_user_id == user_id
            is_assignee = assigned_user_id is not None and assigned_user_id == user_id
            is_global_admin = role == "super_admin"
            is_authorized_assignee = is_assignee and (
                category != "security_privacy" or is_global_admin
            )
            is_organization_admin = (
                role == "admin"
                and organization_id is not None
                and org_id == organization_id
                and category != "security_privacy"
            )
            if is_owner or is_authorized_assignee or is_global_admin or is_organization_admin:
                deliveries.append((websocket, True))
        if deliveries:
            results = await asyncio.gather(
                *(websocket.send_json(message) for websocket, _ in deliveries),
                return_exceptions=True,
            )
            for (websocket, _), result in zip(deliveries, results):
                if isinstance(result, Exception):
                    sentry_sdk.capture_message(
                        "QueueLess feedback event delivery failed",
                        level="warning",
                    )
                    self.disconnect_feedback(websocket)

    def publish_feedback_nowait(
        self,
        *,
        report_id: UUID,
        reporter_user_id: UUID | None,
        assigned_user_id: UUID | None,
        organization_id: UUID | None,
        category: str,
        event: str,
        status: str,
    ) -> None:
        coroutine = self.publish_feedback(
            report_id=report_id,
            reporter_user_id=reporter_user_id,
            assigned_user_id=assigned_user_id,
            organization_id=organization_id,
            category=category,
            event=event,
            status=status,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.create_task, coroutine)
            else:
                coroutine.close()
            return
        loop.create_task(coroutine)

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
        if self._redis is not None:
            await self._redis.publish(
                settings.realtime_pubsub_channel,
                json.dumps(
                    {
                        "source": self._instance_id,
                        "queue_id": str(queue_id),
                        "message": message,
                    }
                ),
            )

    async def _broadcast(self, queue_id: UUID, message: dict[str, Any]) -> None:
        subscribers = list(
            self._connections.get(queue_id, set()) | self._super_admin_connections
        )
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
                    self.disconnect_super_admin(socket)

    def publish_nowait(self, queue_id: UUID, event: str, data: Any = None) -> None:
        def schedule() -> None:
            task = asyncio.create_task(self.publish(queue_id, event, data))
            self._publish_tasks.add(task)
            task.add_done_callback(self._publish_tasks.discard)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(schedule)
            return
        schedule()

    async def allow_connection(self, queue_id: UUID) -> bool:
        return await cache.increment_with_limit(
            f"{settings.realtime_channel_prefix}{queue_id}:connections",
            limit=settings.realtime_queue_connection_limit,
            window_seconds=60,
        )

    async def allow_feedback_connection(self, user_id: UUID) -> bool:
        return await cache.increment_with_limit(
            f"queueless:feedback:{user_id}:connections",
            limit=20,
            window_seconds=60,
        )

    async def allow_super_admin_connection(self, user_id: UUID) -> bool:
        return await cache.increment_with_limit(
            f"queueless:super-admin:{user_id}:connections",
            limit=20,
            window_seconds=60,
        )

    async def allow_announcement_connection(self, user_id: UUID) -> bool:
        return await cache.increment_with_limit(
            f"queueless:announcements:{user_id}:connections",
            limit=10,
            window_seconds=60,
        )


realtime = RealtimeManager()
