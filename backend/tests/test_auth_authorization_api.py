import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Branch, Counter, Organization, Queue, QueueEntry, Service, User
from app.models.entities import CounterStatus, QueueEntryStatus, UserRole


def auth_client(db: Session, user: User) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(user.id)}"
    return client


def make_queue(db: Session):
    org = Organization(name="Auth Org", slug=f"auth-{uuid.uuid4()}")
    branch = Branch(name="Auth Branch", organization=org)
    service = Service(name="Auth Service", code=str(uuid.uuid4())[:8], branch=branch)
    counter = Counter(name="Auth Counter", number=1, status=CounterStatus.AVAILABLE, branch=branch)
    queue = Queue(name="Auth Queue", prefix="A", service=service)
    db.add_all([org, counter, queue])
    db.flush()
    return branch, counter, queue


def make_user(email: str, role: UserRole, branch: Branch | None = None) -> User:
    return User(
        full_name=role.value,
        email=f"{email}-{uuid.uuid4()}@example.test",
        password_hash=hash_password("test-password-123"),
        role=role,
        branch=branch,
    )


def test_register_login_and_queue_authorization(db_session: Session) -> None:
    customer = make_user("customer", UserRole.CUSTOMER)
    staff_branch, counter, queue = make_queue(db_session)
    staff = make_user("staff", UserRole.STAFF, staff_branch)
    other_branch = Branch(name="Other branch", organization=Organization(name="Other org", slug=f"other-{uuid.uuid4()}"))
    outsider = make_user("outsider", UserRole.STAFF, other_branch)
    db_session.add_all([customer, staff, other_branch, outsider])
    db_session.commit()

    customer_client = auth_client(db_session, customer)
    joined = customer_client.post(f"/api/v1/queues/{queue.id}/join", json={"customer_id": str(customer.id)})
    assert joined.status_code == 201
    entry_id = joined.json()["id"]
    assert joined.json()["queue_number"] == 1
    assert joined.json()["people_ahead"] == 0
    notifications = customer_client.get("/api/v1/notifications")
    assert notifications.status_code == 200
    assert [item["type"] for item in notifications.json()["items"]] == ["queue_joined"]

    assert customer_client.post(f"/api/v1/queue-entries/{entry_id}/call").status_code == 403
    assert auth_client(db_session, outsider).post(
        f"/api/v1/queues/{queue.id}/next", json={"counter_id": str(counter.id)}
    ).status_code == 403
    staff_client = auth_client(db_session, staff)
    assert staff_client.post(f"/api/v1/queue-entries/{entry_id}/call", json={"counter_id": str(counter.id)}).status_code == 200
    notifications = customer_client.get("/api/v1/notifications")
    assert {item["type"] for item in notifications.json()["items"]} == {
        "queue_joined",
        "customer_called",
    }
    called_notification = next(
        item for item in notifications.json()["items"] if item["type"] == "customer_called"
    )
    assert customer_client.post(
        f"/api/v1/notifications/{called_notification['id']}/read"
    ).status_code == 204
    assert customer_client.get("/api/v1/notifications/unread-count").json()["count"] == 1
    assert staff_client.post(f"/api/v1/queue-entries/{entry_id}/start", json={"counter_id": str(counter.id)}).status_code == 200
    assert staff_client.post(f"/api/v1/queue-entries/{entry_id}/complete").json()["status"] == "completed"
    assert staff_client.post(f"/api/v1/queue-entries/{entry_id}/complete").status_code == 409
    waiting = QueueEntry(queue=queue, customer=customer, queue_number=2)
    db_session.add(waiting)
    db_session.commit()
    assert customer_client.post(f"/api/v1/queue-entries/{waiting.id}/cancel").status_code == 200
    assert customer_client.post(f"/api/v1/queue-entries/{waiting.id}/cancel").status_code == 409
    assert staff_client.post(f"/api/v1/staff/queues/{queue.id}/pause").status_code == 200
    assert customer_client.post(f"/api/v1/staff/queues/{queue.id}/resume").status_code == 403
    assert staff_client.post(f"/api/v1/staff/queues/{queue.id}/resume").status_code == 200


def test_qr_service_join_validates_branch_and_creates_ticket_notification(db_session: Session) -> None:
    customer = make_user("qr-customer", UserRole.CUSTOMER)
    branch, _, queue = make_queue(db_session)
    db_session.add(customer)
    db_session.commit()
    client = auth_client(db_session, customer)

    service_response = client.get(f"/api/v1/catalog/services/{queue.service_id}")
    assert service_response.status_code == 200
    assert service_response.json()["branch_id"] == str(branch.id)

    joined = client.post(
        f"/api/v1/customers/services/{queue.service_id}/join",
        params={"branch_id": str(branch.id)},
    )
    assert joined.status_code == 201
    assert joined.json()["queue_number"] == 1
    notification_response = client.get("/api/v1/notifications")
    assert [item["type"] for item in notification_response.json()["items"]] == ["queue_joined"]

    assert client.post(
        f"/api/v1/customers/services/{queue.service_id}/join",
        params={"branch_id": str(uuid.uuid4())},
    ).status_code == 404


def test_notification_preferences_persist_and_unknown_notification_is_not_found(
    db_session: Session,
) -> None:
    customer = make_user("notification-preferences", UserRole.CUSTOMER)
    db_session.add(customer)
    db_session.commit()
    client = auth_client(db_session, customer)

    defaults = client.get("/api/v1/notifications/preferences")
    assert defaults.status_code == 200
    assert defaults.json()["enabled"] is True
    assert defaults.json()["approaching"] is True
    updated = client.put(
        "/api/v1/notifications/preferences",
        json={
            "enabled": True,
            "joined": False,
            "called": True,
            "approaching": False,
            "completed": True,
            "queue_updates": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["joined"] is False
    assert client.get("/api/v1/notifications/preferences").json()["approaching"] is False
    assert client.post(f"/api/v1/notifications/{uuid.uuid4()}/read").status_code == 404


def test_login_returns_token_and_register_hash_is_not_exposed(db_session: Session) -> None:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Test Account", "email": f"{uuid.uuid4()}@example.test", "password": "test-password-123"},
    )
    assert response.status_code == 201
    assert "password_hash" not in response.json()["user"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": response.json()["user"]["email"], "password": "test-password-123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_wait_prediction_for_active_entry_with_no_history(db_session: Session) -> None:
    customer = make_user("prediction", UserRole.CUSTOMER)
    _, _, queue = make_queue(db_session)
    entry = QueueEntry(queue=queue, customer=customer, queue_number=1, status=QueueEntryStatus.WAITING)
    db_session.add_all([customer, entry])
    db_session.commit()
    response = auth_client(db_session, customer).get(f"/api/v1/ai/wait-time/{entry.id}")
    assert response.status_code == 200
    result = response.json()
    assert result["estimated_minutes"] >= 0
    assert result["lower_bound_minutes"] <= result["estimated_minutes"] <= result["upper_bound_minutes"]
    assert result["factors"]["historical_samples"] == 0


def test_prediction_rejects_unknown_entry(db_session: Session) -> None:
    user = make_user("invalid-prediction", UserRole.CUSTOMER)
    db_session.add(user)
    db_session.commit()
    assert auth_client(db_session, user).get(f"/api/v1/ai/wait-time/{uuid.uuid4()}").status_code == 404
