from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func, select
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.db.session import get_db
from app.core.security import create_access_token
from app.models import (
    Branch,
    Counter,
    Notification,
    Organization,
    Queue,
    QueueEntry,
    QueueEvent,
    Service,
    User,
)
from app.models.entities import CounterStatus, QueueEventType, QueueStatus, UserRole
from app.services.queue import QueueService


def create_fixture(db: Session) -> tuple[Queue, Counter, list[User]]:
    organization = Organization(name="Queue Org", slug=str(uuid.uuid4()))
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Admissions", code=str(uuid.uuid4())[:8], branch=branch, average_service_minutes=10)
    counter = Counter(name="Counter 1", number=1, status=CounterStatus.AVAILABLE, branch=branch)
    queue = Queue(name="Admissions", prefix="A", service=service)
    users = [
        User(full_name=f"Customer {index}", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
        for index in range(3)
    ]
    db.add_all([organization, counter, queue, *users])
    db.commit()
    db.refresh(queue)
    db.refresh(counter)
    return queue, counter, users


def client_for(db: Session) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def authorize(client: TestClient, user: User) -> None:
    client.headers["Authorization"] = f"Bearer {create_access_token(user.id)}"


def create_staff(db: Session, queue: Queue) -> User:
    staff = User(
        full_name="Queue Staff",
        email=f"{uuid.uuid4()}@example.com",
        password_hash="hash",
        role=UserRole.STAFF,
        branch_id=queue.service.branch_id,
    )
    db.add(staff)
    db.commit()
    return staff


def test_customer_workflow_and_position(db_session: Session) -> None:
    queue, counter, users = create_fixture(db_session)
    staff = create_staff(db_session, queue)
    with client_for(db_session) as client:
        joined = []
        for user in users:
            authorize(client, user)
            joined.append(
                client.post(
                    f"/api/v1/queues/{queue.id}/join",
                    json={"customer_id": str(user.id)},
                ).json()
            )
        assert [item["queue_number"] for item in joined] == [1, 2, 3]
        assert joined[2]["people_ahead"] == 2
        authorize(client, users[0])
        retried = client.post(
            f"/api/v1/queues/{queue.id}/join",
            json={"customer_id": str(users[0].id)},
        )
        assert retried.status_code == 201
        assert retried.json()["id"] == joined[0]["id"]
        assert retried.json()["queue_number"] == joined[0]["queue_number"]

        authorize(client, staff)
        called_a = client.post(
            f"/api/v1/queues/{queue.id}/next",
            json={"counter_id": str(counter.id)},
        )
        assert called_a.status_code == 200
        assert called_a.json()["status"] == "called"

        completed_a = client.post(
            f"/api/v1/queue-entries/{joined[0]['id']}/start",
            json={"counter_id": str(counter.id)},
        )
        assert completed_a.json()["status"] == "serving"
        completed_a = client.post(f"/api/v1/queue-entries/{joined[0]['id']}/complete")
        assert completed_a.json()["status"] == "completed"
        assert completed_a.json()["completed_at"] is not None

        called_b = client.get(
            f"/api/v1/queues/{queue.id}/position/{joined[1]['id']}"
        )
        assert called_b.json()["status"] == "called"


def test_invalid_transitions_and_cancel_skip(db_session: Session) -> None:
    queue, counter, users = create_fixture(db_session)
    staff = create_staff(db_session, queue)
    with client_for(db_session) as client:
        entries = []
        for user in users:
            authorize(client, user)
            entries.append(
                client.post(
                    f"/api/v1/queues/{queue.id}/join",
                    json={"customer_id": str(user.id)},
                ).json()
            )
        authorize(client, staff)
        assert client.post(f"/api/v1/queue-entries/{entries[0]['id']}/complete").status_code == 409
        authorize(client, users[0])
        assert client.post(f"/api/v1/queue-entries/{entries[0]['id']}/cancel").status_code == 200
        assert client.post(f"/api/v1/queue-entries/{entries[0]['id']}/cancel").status_code == 409
        authorize(client, staff)
        client.post(f"/api/v1/queue-entries/{entries[1]['id']}/call", json={"counter_id": str(counter.id)})
        assert client.post(f"/api/v1/queue-entries/{entries[1]['id']}/skip").status_code == 200
        assert client.post(f"/api/v1/queue-entries/{entries[1]['id']}/start").status_code == 409
        next_entry = client.get(
            f"/api/v1/queues/{queue.id}/position/{entries[2]['id']}"
        )
        assert next_entry.json()["status"] == "called"
        assert next_entry.json()["counter_id"] == str(counter.id)


def test_counter_cannot_serve_two_customers(db_session: Session) -> None:
    queue, counter, users = create_fixture(db_session)
    staff = create_staff(db_session, queue)
    with client_for(db_session) as client:
        entries = []
        for user in users[:2]:
            authorize(client, user)
            entries.append(
                client.post(
                    f"/api/v1/queues/{queue.id}/join",
                    json={"customer_id": str(user.id)},
                ).json()
            )
        authorize(client, staff)
        assert client.post(
            f"/api/v1/queue-entries/{entries[0]['id']}/call",
            json={"counter_id": str(counter.id)},
        ).status_code == 200
        assert client.post(
            f"/api/v1/queue-entries/{entries[1]['id']}/call",
        ).status_code == 200
        assert client.post(
            f"/api/v1/queue-entries/{entries[0]['id']}/start",
            json={"counter_id": str(counter.id)},
        ).status_code == 200
        assert client.post(
            f"/api/v1/queue-entries/{entries[1]['id']}/start",
            json={"counter_id": str(counter.id)},
        ).status_code == 409


def test_offline_counter_cannot_be_assigned() -> None:
    branch_id = uuid.uuid4()
    counter = SimpleNamespace(
        id=uuid.uuid4(),
        is_active=True,
        status=CounterStatus.OFFLINE,
        branch_id=branch_id,
    )
    entry = SimpleNamespace(
        queue=SimpleNamespace(service=SimpleNamespace(branch_id=branch_id))
    )
    session = Mock()
    session.scalar.return_value = counter

    with pytest.raises(HTTPException) as error:
        QueueService(session)._counter(counter.id, entry)

    assert error.value.status_code == 400
    session.scalar.assert_called_once()


def test_duplicate_join_returns_existing_active_entry() -> None:
    queue_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    existing_entry = SimpleNamespace(id=uuid.uuid4())
    queue = SimpleNamespace(id=queue_id, status=QueueStatus.OPEN)
    session = Mock()
    session.scalar.return_value = existing_entry
    service = QueueService(session)
    service._queue = Mock(return_value=queue)
    service._response = Mock(return_value={"id": existing_entry.id})
    service.number_service = Mock()

    result = service.join(queue_id, customer_id)

    assert result == {"id": existing_entry.id}
    service.number_service.next_number.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_closing_queue_records_closed_event_and_notifies_waiting_customers() -> None:
    queue_id = uuid.uuid4()
    event_id = uuid.uuid4()
    queue = SimpleNamespace(id=queue_id, status=QueueStatus.OPEN)
    service = QueueService(Mock())
    service._queue = Mock(return_value=queue)
    service._record = Mock(return_value=SimpleNamespace(id=event_id))
    service._commit = Mock()
    notifier = Mock()

    with (
        patch("app.services.queue.NotificationService", return_value=notifier),
        patch("app.services.queue.realtime.publish_nowait") as publish,
    ):
        result = service.set_status(queue_id, QueueStatus.CLOSED)

    assert result == {"id": queue_id, "status": QueueStatus.CLOSED}
    service._record.assert_called_once_with(queue, None, QueueEventType.CLOSED)
    notifier.queue_status.assert_called_once_with(queue_id, "closed", event_id)
    assert publish.call_args_list[0].args[1] == "QUEUE_CLOSED"


def test_queue_pagination(db_session: Session) -> None:
    queue, _, users = create_fixture(db_session)
    with client_for(db_session) as client:
        for user in users:
            authorize(client, user)
            client.post(f"/api/v1/queues/{queue.id}/join", json={"customer_id": str(user.id)})
        response = client.get(f"/api/v1/queues/{queue.id}?page=2&page_size=2")
        assert response.status_code == 200
        assert response.json()["page"] == 2
        assert len(response.json()["entries"]) == 1


def test_concurrent_joins_have_unique_numbers(database_engine) -> None:
    session_factory = sessionmaker(bind=database_engine, expire_on_commit=False)
    with session_factory() as queue_session:
        queue, _, _ = create_fixture(queue_session)
        queue_id = queue.id

    def join_once(_: int) -> int:
        with session_factory() as session:
            user = User(
                full_name="Concurrent",
                email=f"{uuid.uuid4()}@example.com",
                password_hash="hash",
            )
            session.add(user)
            session.commit()
            entry = QueueService(session).join(queue_id, user.id)
            return entry["queue_number"]

    concurrent_customers = 50
    with ThreadPoolExecutor(max_workers=concurrent_customers) as executor:
        numbers = list(executor.map(join_once, range(concurrent_customers)))
    assert len(numbers) == concurrent_customers
    assert sorted(numbers) == list(range(1, concurrent_customers + 1))
    with session_factory() as session:
        assert session.scalar(
            select(Queue.current_number).where(Queue.id == queue_id)
        ) == concurrent_customers
        assert session.scalar(
            select(func.count(QueueEvent.id)).where(QueueEvent.queue_id == queue_id)
        ) == concurrent_customers


def test_concurrent_retry_by_same_customer_creates_one_entry(database_engine) -> None:
    session_factory = sessionmaker(bind=database_engine, expire_on_commit=False)
    with session_factory() as session:
        queue, _, users = create_fixture(session)
        queue_id = queue.id
        customer_id = users[0].id

    def join_once(_: int) -> tuple[str, int]:
        with session_factory() as session:
            entry = QueueService(session).join(queue_id, customer_id)
            return str(entry["id"]), entry["queue_number"]

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(join_once, range(20)))

    assert len(set(results)) == 1
    entry_id, queue_number = results[0]
    assert queue_number == 1
    with session_factory() as session:
        assert session.scalar(
            select(Queue.current_number).where(Queue.id == queue_id)
        ) == 1
        assert session.scalar(
            select(QueueEntry.id).where(QueueEntry.id == uuid.UUID(entry_id))
        ) is not None
        assert session.scalar(
            select(func.count(QueueEntry.id)).where(QueueEntry.queue_id == queue_id)
        ) == 1
        assert session.scalar(
            select(func.count(QueueEvent.id)).where(QueueEvent.queue_id == queue_id)
        ) == 1
        assert session.scalar(
            select(func.count(Notification.id)).where(Notification.user_id == customer_id)
        ) == 1


def test_join_rolls_back_ticket_and_sequence_when_notification_creation_fails(
    db_session: Session,
) -> None:
    queue, _, users = create_fixture(db_session)
    with (
        patch(
            "app.services.queue.NotificationService.for_entry",
            side_effect=RuntimeError("notification persistence failed"),
        ),
        patch("app.services.queue.realtime.publish_nowait") as publish,
        pytest.raises(RuntimeError, match="notification persistence failed"),
    ):
        QueueService(db_session).join(queue.id, users[0].id)

    assert db_session.scalar(select(Queue.current_number).where(Queue.id == queue.id)) == 0
    assert db_session.scalar(
        select(func.count(QueueEntry.id)).where(QueueEntry.queue_id == queue.id)
    ) == 0
    assert db_session.scalar(
        select(func.count(QueueEvent.id)).where(QueueEvent.queue_id == queue.id)
    ) == 0
    assert db_session.scalar(
        select(func.count(Notification.id)).where(Notification.user_id == users[0].id)
    ) == 0
    publish.assert_not_called()


def test_queue_page_reads_use_a_bounded_number_of_queries(db_session: Session) -> None:
    queue, _, users = create_fixture(db_session)
    with client_for(db_session) as client:
        for user in users:
            authorize(client, user)
            response = client.post(
                f"/api/v1/queues/{queue.id}/join",
                json={"customer_id": str(user.id)},
            )
            assert response.status_code == 201

    statements: list[str] = []

    def record_statement(*args) -> None:
        statements.append(args[2])

    event.listen(db_session.get_bind(), "before_cursor_execute", record_statement)
    try:
        response = QueueService(db_session).get_queue(queue.id, page=1, page_size=20)
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", record_statement)

    assert len(response["entries"]) == len(users)
    assert len(statements) <= 5
