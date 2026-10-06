from concurrent.futures import ThreadPoolExecutor
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db
from app.models import Branch, Counter, Organization, Queue, Service, User
from app.models.entities import CounterStatus


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


def test_customer_workflow_and_position(db_session: Session) -> None:
    queue, counter, users = create_fixture(db_session)
    with client_for(db_session) as client:
        joined = [
            client.post(f"/api/v1/queues/{queue.id}/join", json={"customer_id": str(user.id)}).json()
            for user in users
        ]
        assert [item["queue_number"] for item in joined] == [1, 2, 3]
        assert joined[2]["people_ahead"] == 2

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

        called_b = client.post(
            f"/api/v1/queues/{queue.id}/next",
            json={"counter_id": str(counter.id)},
        )
        assert called_b.json()["id"] == joined[1]["id"]
        assert called_b.json()["status"] == "called"


def test_invalid_transitions_and_cancel_skip(db_session: Session) -> None:
    queue, counter, users = create_fixture(db_session)
    with client_for(db_session) as client:
        entries = [
            client.post(f"/api/v1/queues/{queue.id}/join", json={"customer_id": str(user.id)}).json()
            for user in users
        ]
        assert client.post(f"/api/v1/queue-entries/{entries[0]['id']}/complete").status_code == 409
        assert client.post(f"/api/v1/queue-entries/{entries[0]['id']}/cancel").status_code == 200
        assert client.post(f"/api/v1/queue-entries/{entries[0]['id']}/cancel").status_code == 409
        client.post(f"/api/v1/queue-entries/{entries[1]['id']}/call", json={"counter_id": str(counter.id)})
        assert client.post(f"/api/v1/queue-entries/{entries[1]['id']}/skip").status_code == 200
        assert client.post(f"/api/v1/queue-entries/{entries[1]['id']}/start").status_code == 409


def test_counter_cannot_serve_two_customers(db_session: Session) -> None:
    queue, counter, users = create_fixture(db_session)
    with client_for(db_session) as client:
        entries = [
            client.post(f"/api/v1/queues/{queue.id}/join", json={"customer_id": str(user.id)}).json()
            for user in users[:2]
        ]
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


def test_queue_pagination(db_session: Session) -> None:
    queue, _, users = create_fixture(db_session)
    with client_for(db_session) as client:
        for user in users:
            client.post(f"/api/v1/queues/{queue.id}/join", json={"customer_id": str(user.id)})
        response = client.get(f"/api/v1/queues/{queue.id}?page=2&page_size=2")
        assert response.status_code == 200
        assert response.json()["page"] == 2
        assert len(response.json()["entries"]) == 1


def test_concurrent_joins_have_unique_numbers(database_engine) -> None:
    queue_session = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
        bind=database_engine, expire_on_commit=False
    )()
    queue, _, _ = create_fixture(queue_session)
    queue_session.close()

    def join_once(_: int) -> int:
        session = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
            bind=database_engine, expire_on_commit=False
        )()
        user = User(full_name="Concurrent", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
        session.add(user)
        session.commit()
        from app.services.queue import QueueService
        entry = QueueService(session).join(queue.id, user.id)
        session.close()
        return entry["queue_number"]

    concurrent_customers = 20
    with ThreadPoolExecutor(max_workers=concurrent_customers) as executor:
        numbers = list(executor.map(join_once, range(concurrent_customers)))
    assert len(numbers) == concurrent_customers
    assert len(set(numbers)) == concurrent_customers
