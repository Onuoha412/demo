import asyncio
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.db.session import get_db
from app.main import app
from app.models import (
    Counter,
    Branch,
    Notification,
    NotificationPreference,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    Service,
    User,
)
from app.models.entities import CounterStatus, QueueEntryStatus, QueueStatus, UserRole
from app.services.notifications import NotificationService
from app.services.queue import QueueService
from app.services.realtime import RealtimeManager


@pytest.fixture
def session(database_engine) -> Generator[Session, None, None]:
    db = Session(database_engine, expire_on_commit=False)
    try:
        yield db
    finally:
        app.dependency_overrides.clear()
        db.close()


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
    admin = User(
        full_name="Admin",
        email=f"{uuid.uuid4()}@example.test",
        password_hash="test-hash",
        role=UserRole.ADMIN,
        organization=branch.organization,
    )
    session.add_all([customer, staff, admin])
    session.commit()
    session.add(
        OrganizationMembership(
            user_id=admin.id,
            organization_id=branch.organization_id,
            role=UserRole.ADMIN.value,
        )
    )
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

    with patch("app.services.queue.realtime.publish_nowait") as publish:
        joined = client.post(
            f"/api/v1/customers/services/{service.id}/join",
            params={"branch_id": str(branch.id)},
            json={"request_note": "  Renewing my passport  "},
        )
    assert joined.status_code == 201, joined.text
    ticket = joined.json()
    assert ticket["queue_number"] == 1
    assert ticket["queue_prefix"] == "A"
    assert ticket["request_note"] == "Renewing my passport"
    assert ticket["verified_at"] is None
    public_queue = client.get(f"/api/v1/queues/{ticket['queue_id']}")
    assert "Renewing my passport" not in public_queue.text
    assert all(
        "request_note" not in call.args[2]
        for call in publish.call_args_list
        if len(call.args) > 2 and isinstance(call.args[2], dict)
    )

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
    unauthorized_verification = client.post(
        f"/api/v1/admin/queue-entries/{ticket['id']}/verify"
    )
    assert unauthorized_verification.status_code == 403
    app.dependency_overrides[get_current_user] = lambda: admin
    verified = client.post(f"/api/v1/admin/queue-entries/{ticket['id']}/verify")
    assert verified.status_code == 200, verified.text
    verified_ticket = verified.json()
    assert verified_ticket["request_note"] == "Renewing my passport"
    assert verified_ticket["verified_at"] is not None
    assert verified_ticket["verified_by_user_id"] == str(admin.id)
    repeated_verification = client.post(
        f"/api/v1/admin/queue-entries/{ticket['id']}/verify"
    )
    assert repeated_verification.json()["verified_at"] == verified_ticket["verified_at"]


def test_generic_service_join_chooses_the_least_loaded_open_queue(
    session: Session,
) -> None:
    branch, service, first_queue = create_queue(session)
    second_queue = Queue(name="Admissions overflow", prefix="B", service=service)
    existing_customers = [make_customer(f"Existing {index}") for index in range(3)]
    joining_customer = make_customer("New customer")
    session.add_all([second_queue, *existing_customers, joining_customer])
    session.commit()

    for customer in existing_customers[:2]:
        QueueService(session).join(first_queue.id, customer.id)
    QueueService(session).join(second_queue.id, existing_customers[2].id)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: joining_customer
    response = TestClient(app).post(
        f"/api/v1/customers/services/{service.id}/join",
        params={"branch_id": str(branch.id)},
    )

    assert response.status_code == 201, response.text
    assert response.json()["queue_id"] == str(second_queue.id)


def test_generic_service_join_skips_paused_and_full_queues(
    session: Session,
) -> None:
    branch, service, paused_queue = create_queue(session)
    paused_queue.status = QueueStatus.PAUSED
    full_queue = Queue(
        name="Full queue",
        prefix="F",
        service=service,
        capacity_limit=1,
    )
    available_queue = Queue(name="Available queue", prefix="A", service=service)
    existing_customer = make_customer("Already queued")
    joining_customer = make_customer("New customer")
    session.add_all([full_queue, available_queue, existing_customer, joining_customer])
    session.commit()
    QueueService(session).join(full_queue.id, existing_customer.id)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: joining_customer
    client = TestClient(app)
    response = client.post(
        f"/api/v1/customers/services/{service.id}/join",
        params={"branch_id": str(branch.id)},
    )

    assert response.status_code == 201, response.text
    assert response.json()["queue_id"] == str(available_queue.id)

    exact_target = make_customer("Exact QR customer")
    session.add(exact_target)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: exact_target
    unavailable_target = client.post(
        f"/api/v1/customers/services/{service.id}/join",
        params={"branch_id": str(branch.id), "queue_id": str(paused_queue.id)},
    )
    assert unavailable_target.status_code == 409

    available_queue.status = QueueStatus.CLOSED
    session.commit()
    no_open_queue_customer = make_customer("No open queue customer")
    session.add(no_open_queue_customer)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: no_open_queue_customer
    no_open_queue = client.post(
        f"/api/v1/customers/services/{service.id}/join",
        params={"branch_id": str(branch.id)},
    )
    assert no_open_queue.status_code == 409


def test_customer_reuses_active_entry_for_service_across_queues(
    session: Session,
) -> None:
    branch, service, first_queue = create_queue(session)
    second_queue = Queue(name="Admissions overflow", prefix="B", service=service)
    customer = make_customer("Returning customer")
    session.add_all([second_queue, customer])
    session.commit()
    existing = QueueService(session).join(first_queue.id, customer.id)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: customer
    response = TestClient(app).post(
        f"/api/v1/customers/services/{service.id}/join",
        params={"branch_id": str(branch.id), "queue_id": str(second_queue.id)},
    )

    assert response.status_code == 201, response.text
    assert response.json()["id"] == str(existing["id"])
    assert response.json()["queue_id"] == str(first_queue.id)


def test_queue_realtime_events_are_published_after_database_commit(
    session: Session,
) -> None:
    _, _, queue = create_queue(session)
    customer = make_customer("Committed customer")
    session.add(customer)
    session.commit()
    observed_events: list[str] = []

    def assert_durable_before_publish(queue_id, event, data=None) -> None:
        assert queue_id == queue.id
        with Session(session.bind) as observer:
            entry = observer.scalar(
                select(QueueEntry).where(
                    QueueEntry.queue_id == queue_id,
                    QueueEntry.customer_id == customer.id,
                )
            )
            assert entry is not None
            assert entry.status is QueueEntryStatus.WAITING
            observed_events.append(event)

    with patch(
        "app.services.queue.realtime.publish_nowait",
        side_effect=assert_durable_before_publish,
    ):
        QueueService(session).join(queue.id, customer.id)

    assert observed_events == ["CUSTOMER_JOINED", "QUEUE_UPDATED"]


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


def test_completing_called_customer_auto_calls_next_on_same_counter(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch, _, queue = create_queue(session)
    counter = Counter(
        name="Counter 2",
        number=2,
        branch=branch,
        status=CounterStatus.AVAILABLE,
    )
    customers = [make_customer(f"Customer {index}") for index in range(2)]
    session.add_all([counter, *customers])
    session.commit()

    queue_service = QueueService(session)
    first = queue_service.join(queue.id, customers[0].id)
    second = queue_service.join(queue.id, customers[1].id)
    called = queue_service.call(first["id"], counter.id)

    events: list[tuple[str, object]] = []
    monkeypatch.setattr(
        "app.services.queue.realtime.publish_nowait",
        lambda queue_id, name, data: events.append((name, data)),
    )
    completed = queue_service.complete(called["id"])

    assert completed["status"] == QueueEntryStatus.COMPLETED
    updated = queue_service.position(queue.id, second["id"])
    assert updated["status"] == QueueEntryStatus.CALLED
    assert updated["counter_id"] == counter.id
    assert updated["counter"]["name"] == "Counter 2"
    assert session.get(Counter, counter.id).status == CounterStatus.AVAILABLE
    assert [name for name, _ in events] == [
        "CUSTOMER_COMPLETED",
        "QUEUE_UPDATED",
        "CUSTOMER_CALLED",
        "QUEUE_UPDATED",
    ]


def test_realtime_queue_events_encode_uuid_and_datetime_payloads() -> None:
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
