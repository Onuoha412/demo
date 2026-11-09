import asyncio
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
