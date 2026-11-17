import asyncio
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.services.realtime import RealtimeManager


class RecordingWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def accept(self) -> None:
        return

    async def send_json(self, message: dict[str, object]) -> None:
        self.messages.append(message)


class SingleMessagePubSub:
    def __init__(self, message: dict[str, object]) -> None:
        self.message = message

    async def listen(self):
        yield {"type": "message", "data": json.dumps(self.message)}


def test_announcement_realtime_delivery_respects_role_audience() -> None:
    manager = RealtimeManager()
    customer = RecordingWebSocket()
    staff = RecordingWebSocket()
    admin = RecordingWebSocket()

    async def run() -> None:
        await manager.connect_announcements(customer, "customer")
        await manager.connect_announcements(staff, "staff")
        await manager.connect_announcements(admin, "admin")
        await manager.publish_announcement(
            "customer",
            {"id": "announcement-1"},
            "ANNOUNCEMENT_PUBLISHED",
        )

    asyncio.run(run())

    assert customer.messages == [
        {
            "event": "ANNOUNCEMENT_PUBLISHED",
            "data": {"id": "announcement-1"},
        }
    ]
    assert staff.messages == []
    assert len(admin.messages) == 1


def test_organization_announcement_is_only_broadcast_within_organization() -> None:
    manager = RealtimeManager()
    staff = RecordingWebSocket()
    another_staff = RecordingWebSocket()
    admin = RecordingWebSocket()

    async def run() -> None:
        await manager.connect_announcements(staff, "staff", "org-1")
        await manager.connect_announcements(another_staff, "staff", "org-2")
        await manager.connect_announcements(admin, "admin", "org-1")
        await manager.publish_announcement(
            "staff",
            {"id": "announcement-1"},
            "ANNOUNCEMENT_PUBLISHED",
            organization_id="org-1",
        )

    asyncio.run(run())

    assert len(staff.messages) == 1
    assert another_staff.messages == []
    assert len(admin.messages) == 1


def test_redis_announcement_broadcast_reaches_remote_instance_connections() -> None:
    manager = RealtimeManager()
    customer = RecordingWebSocket()
    other_customer = RecordingWebSocket()

    async def run() -> None:
        await manager.connect_announcements(customer, "customer")
        await manager.connect_announcements(other_customer, "staff")
        manager._pubsub = SingleMessagePubSub(
            {
                "source": "another-instance",
                "kind": "announcement",
                "audience": "customer",
                "organization_id": None,
                "message": {
                    "event": "ANNOUNCEMENT_PUBLISHED",
                    "data": {"id": "announcement-1"},
                },
            }
        )
        await manager._listen_for_broadcasts()

    asyncio.run(run())

    assert customer.messages == [
        {
            "event": "ANNOUNCEMENT_PUBLISHED",
            "data": {"id": "announcement-1"},
        }
    ]
    assert other_customer.messages == []


def test_redis_feedback_broadcast_preserves_report_access_scope() -> None:
    manager = RealtimeManager()
    reporter_id = uuid4()
    other_id = uuid4()
    reporter = RecordingWebSocket()
    other_user = RecordingWebSocket()
    report_id = uuid4()

    async def run() -> None:
        await manager.connect_feedback(reporter, reporter_id, None, "customer")
        await manager.connect_feedback(other_user, other_id, None, "customer")
        manager._pubsub = SingleMessagePubSub(
            {
                "source": "another-instance",
                "kind": "feedback",
                "report_id": str(report_id),
                "reporter_user_id": str(reporter_id),
                "assigned_user_id": None,
                "organization_id": None,
                "category": "general",
                "event": "FEEDBACK_UPDATED",
                "status": "in_review",
            }
        )
        await manager._listen_for_broadcasts()

    asyncio.run(run())

    assert reporter.messages == [
        {
            "event": "FEEDBACK_UPDATED",
            "report_id": str(report_id),
            "status": "in_review",
        }
    ]
    assert other_user.messages == []


def test_queue_connection_limit_uses_configured_capacity() -> None:
    manager = RealtimeManager()

    async def run() -> bool:
        with patch(
            "app.services.realtime.cache.increment_with_limit",
            new_callable=AsyncMock,
            return_value=True,
        ) as allow:
            result = await manager.allow_connection(uuid4())
        allow.assert_awaited_once()
        assert allow.call_args.kwargs["limit"] == 1000
        return result

    assert asyncio.run(run()) is True
