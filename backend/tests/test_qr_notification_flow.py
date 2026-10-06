import asyncio
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.auth_dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import (
    Branch,
    Notification,
    NotificationPreference,
    Organization,
    Queue,
    QueueEntry,
    Service,
    User,
)
from app.models.entities import QueueEntryStatus, UserRole
from app.services.notifications import NotificationService
from app.services.queue import QueueService
from app.services.realtime import RealtimeManager


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_queue(session: Session) -> tuple[Branch, Service, Queue]:
    organization = Organization(name="QR Org", slug=f"qr-{uuid.uuid4()}")
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Admissions", code="ADM", branch=branch)
    queue = Queue(name="Admissions", prefix="A", service=service)
    session.add_all([organization, queue])
    session.flush()
    return branch, service, queue


def make_customer(name: str) -> User:
    return User(
        full_name=name,
        email=f"{uuid.uuid4()}@example.test",
        password_hash="test-hash",
        role=UserRole.CUSTOMER,
    )


def test_qr_join_creates_ticket_and_joined_and_called_notifications(
    session: Session,
) -> None:
    branch, service, _ = create_queue(session)
    customer = make_customer("Customer")
    staff = User(
        full_name="Staff",
        email=f"{uuid.uuid4()}@example.test",
        password_hash="test-hash",
        role=UserRole.STAFF,
        branch=branch,
    )
    session.add_all([customer, staff])
    session.commit()

    def override_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: customer
    client = TestClient(app)

    catalog_response = client.get(f"/api/v1/catalog/services/{service.id}")
    assert catalog_response.status_code == 200
    assert catalog_response.json()["branch_id"] == str(branch.id)
    assert "password" not in catalog_response.text.lower()
    assert "customer" not in catalog_response.text.lower()

    joined = client.post(
        f"/api/v1/customers/services/{service.id}/join",
        params={"branch_id": str(branch.id)},
    )
    assert joined.status_code == 201, joined.text
    ticket = joined.json()
    assert ticket["queue_number"] == 1

    notices = client.get("/api/v1/notifications").json()["items"]
    assert [item["type"] for item in notices] == ["queue_joined"]
    assert client.get("/api/v1/notifications/unread-count").json()["count"] == 1

    app.dependency_overrides[get_current_user] = lambda: staff
    called = client.post(f"/api/v1/queue-entries/{ticket['id']}/call")
    assert called.status_code == 200

    app.dependency_overrides[get_current_user] = lambda: customer
    notices = client.get("/api/v1/notifications").json()["items"]
    assert {item["type"] for item in notices} == {"queue_joined", "customer_called"}
    called_notice = next(item for item in notices if item["type"] == "customer_called")
    assert client.post(
        f"/api/v1/notifications/{called_notice['id']}/read"
    ).status_code == 204
    assert client.get("/api/v1/notifications/unread-count").json()["count"] == 1


def test_approaching_and_queue_status_events_are_idempotent(session: Session) -> None:
    _, _, queue = create_queue(session)
    first_customer = make_customer("First")
    second_customer = make_customer("Second")
    session.add_all([first_customer, second_customer])
    session.commit()

    queue_service = QueueService(session)
    queue_service.join(queue.id, first_customer.id)
    second_ticket = queue_service.join(queue.id, second_customer.id)
    second_entry = session.get(QueueEntry, second_ticket["id"])
    assert second_entry is not None

    notifications = NotificationService(session)
    notifications.approaching(second_entry)
    session.commit()
    assert session.scalar(
        select(Notification.id).where(
            Notification.user_id == second_customer.id,
            Notification.event_key == f"entry:{second_entry.id}:approaching",
        )
    ) is not None

    from app.models.entities import QueueStatus

    queue_service.set_status(queue.id, QueueStatus.PAUSED)
    queue_service.set_status(queue.id, QueueStatus.OPEN)
    queue_service.set_status(queue.id, QueueStatus.OPEN)

    second_notices = list(
        session.scalars(
            select(Notification).where(Notification.user_id == second_customer.id)
        )
    )
    event_keys = [notice.event_key for notice in second_notices]
    assert len(event_keys) == len(set(event_keys))
    assert {notice.type.value for notice in second_notices} == {
        "queue_joined",
        "queue_approaching",
        "queue_paused",
        "queue_resumed",
    }


def test_notification_preferences_can_disable_event_types(session: Session) -> None:
    _, _, queue = create_queue(session)
    customer = make_customer("Opted out")
    session.add(customer)
    session.flush()
    session.add(NotificationPreference(user_id=customer.id, joined=False))
    session.flush()

    QueueService(session).join(queue.id, customer.id)

    assert session.scalar(
        select(Notification.id).where(Notification.user_id == customer.id)
    ) is None


def test_realtime_queue_events_encode_uuid_and_datetime_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.realtime.cache.publish", AsyncMock())
    monkeypatch.setattr("app.services.realtime.cache.set_json", AsyncMock())
    manager = RealtimeManager()
    queue_id = uuid.uuid4()
    entry_id = uuid.uuid4()
    captured: dict[str, object] = {}

    class FakeWebSocket:
        async def send_json(self, message: dict[str, object]) -> None:
            captured.update(message)

    async def publish_event() -> None:
        manager._connections[queue_id].add(FakeWebSocket())  # noqa: SLF001
        await manager.publish(
            queue_id,
            "CUSTOMER_CALLED",
            {
                "id": entry_id,
                "status": QueueEntryStatus.CALLED,
                "called_at": datetime(2026, 10, 6, tzinfo=timezone.utc),
            },
        )

    asyncio.run(publish_event())

    assert captured["queue_id"] == str(queue_id)
    assert captured["data"] == {
        "id": str(entry_id),
        "status": "called",
        "called_at": "2026-10-06T00:00:00+00:00",
    }
