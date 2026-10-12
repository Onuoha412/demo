import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models import (
    Branch,
    Notification,
    Organization,
    Queue,
    QueueEntry,
    QueueEvent,
    Service,
    User,
)
from app.models.entities import NotificationType, QueueEventType, UserRole
from app.config import Settings
from pydantic import ValidationError


def test_weak_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key="too-short")


def setup_client(db: Session, user: User) -> TestClient:
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(user.id)}"
    return client


def test_password_hashing_and_admin_access_control(db_session: Session) -> None:
    admin = User(
        full_name="Admin",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.ADMIN,
    )
    customer = User(
        full_name="Customer",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.CUSTOMER,
    )
    db_session.add_all([admin, customer])
    db_session.commit()
    assert verify_password("test-password-123", admin.password_hash)
    assert not verify_password("wrong-password", admin.password_hash)
    client = setup_client(db_session, customer)
    assert client.get("/api/v1/admin/organizations").status_code == 403
    app.dependency_overrides.clear()


def test_password_hashing_supports_legacy_and_long_bcrypt_passwords() -> None:
    legacy_password = "test-password-123"
    legacy_hash = hash_password(legacy_password)
    assert legacy_hash.startswith("$2b$")
    assert verify_password(legacy_password, legacy_hash)

    long_password = "x" * 80
    long_hash = hash_password(long_password)
    assert long_hash.startswith("bcrypt-sha256$$2b$")
    assert verify_password(long_password, long_hash)
    assert not verify_password(long_password + "different", long_hash)
    assert not verify_password("not-a-valid-password-hash", "invalid-hash")


def test_admin_builds_customer_ready_service_without_hash_leak(db_session: Session) -> None:
    admin = User(
        full_name="Admin",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()
    client = setup_client(db_session, admin)
    organization = client.post(
        "/api/v1/admin/organizations",
        json={"name": "QA Organization", "slug": f"qa-{uuid.uuid4()}"},
    )
    assert organization.status_code == 201
    organization_id = organization.json()["id"]
    organization_read = client.get(f"/api/v1/admin/organizations/{organization_id}")
    assert organization_read.status_code == 200
    organization_page = client.get("/api/v1/admin/organizations")
    assert organization_page.status_code == 200
    assert any(item["id"] == organization_id for item in organization_page.json()["items"])
    assert client.patch(
        f"/api/v1/admin/organizations/{organization_id}",
        json={"description": "Updated description"},
    ).json()["description"] == "Updated description"
    branch = client.post(
        "/api/v1/admin/branches",
        json={"organization_id": organization_id, "name": "QA Branch"},
    )
    assert branch.status_code == 201
    assert client.get(f"/api/v1/admin/branches/{branch.json()['id']}").status_code == 200
    service = client.post(
        "/api/v1/admin/services",
        json={"branch_id": branch.json()["id"], "name": "QA Service", "code": str(uuid.uuid4())[:8]},
    )
    assert service.status_code == 201
    assert client.get(f"/api/v1/admin/services/{service.json()['id']}").status_code == 200
    assert client.patch(
        f"/api/v1/admin/services/{service.json()['id']}",
        json={"description": "Updated service"},
    ).json()["description"] == "Updated service"
    counter = client.post(
        "/api/v1/admin/counters",
        json={"branch_id": branch.json()["id"], "name": "Counter 1", "number": 1, "status": "available"},
    )
    assert counter.status_code == 201
    assert client.get(f"/api/v1/admin/counters/{counter.json()['id']}").status_code == 200
    queue = client.post(
        "/api/v1/admin/queues",
        json={"service_id": service.json()["id"], "name": "QA Queue", "prefix": "Q"},
    )
    assert queue.status_code == 201
    assert client.get(f"/api/v1/admin/queues/{queue.json()['id']}").status_code == 200
    assert client.patch(f"/api/v1/admin/queues/{queue.json()['id']}/status", json={"status": "paused"}).status_code == 200
    assert client.patch(f"/api/v1/admin/queues/{queue.json()['id']}/status", json={"status": "open"}).status_code == 200
    waiting_customer = User(
        full_name="Waiting Customer",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
    )
    db_session.add(waiting_customer)
    db_session.flush()
    waiting_entry = QueueEntry(
        queue_id=uuid.UUID(queue.json()["id"]),
        customer_id=waiting_customer.id,
        queue_number=1,
    )
    db_session.add(waiting_entry)
    db_session.commit()
    queue_audit = client.get(f"/api/v1/admin/queues/{queue.json()['id']}/entries")
    assert queue_audit.status_code == 200
    audit_entry = queue_audit.json()["entries"][0]
    assert audit_entry["id"] == str(waiting_entry.id)
    assert audit_entry["queue_number"] == 1
    assert audit_entry["status"] == "waiting"
    assert audit_entry["customer"] == {
        "id": str(waiting_customer.id),
        "full_name": "Waiting Customer",
        "email": waiting_customer.email,
    }
    customer_client = setup_client(db_session, waiting_customer)
    assert customer_client.get(
        f"/api/v1/admin/queues/{queue.json()['id']}/entries"
    ).status_code == 403
    assert client.patch(
        f"/api/v1/admin/queues/{queue.json()['id']}/status",
        json={"status": "closed"},
    ).status_code == 200
    assert db_session.query(QueueEvent).filter(
        QueueEvent.queue_id == uuid.UUID(queue.json()["id"]),
        QueueEvent.event_type == QueueEventType.CLOSED,
    ).count() == 1
    assert db_session.query(Notification).filter(
        Notification.queue_entry_id == waiting_entry.id,
        Notification.type == NotificationType.QUEUE_CLOSED,
    ).count() == 1
    assert client.patch(
        f"/api/v1/admin/queues/{queue.json()['id']}/status",
        json={"status": "open"},
    ).status_code == 409
    assert client.get("/api/v1/admin/organizations?page=1&page_size=1").status_code == 200
    assert client.delete(f"/api/v1/admin/organizations/{organization_id}").status_code == 200
    assert client.get(f"/api/v1/admin/organizations/{organization_id}").json()["is_active"] is False

    assert client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "Unassigned Staff",
            "email": f"{uuid.uuid4()}@example.com",
            "password": "test-password-123",
            "role": "staff",
        },
    ).status_code == 422
    staff_user = client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "Assigned Staff",
            "email": f"{uuid.uuid4()}@example.com",
            "password": "test-password-123",
            "role": "staff",
            "branch_id": branch.json()["id"],
        },
    )
    assert staff_user.status_code == 201
    assert staff_user.json()["branch_id"] == branch.json()["id"]
    assert staff_user.json()["organization_id"] == organization_id

    created_user = client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "Safe Response",
            "email": f"{uuid.uuid4()}@example.com",
            "password": "test-password-123",
            "role": "customer",
        },
    )
    assert created_user.status_code == 201
    assert "password_hash" not in created_user.json()
    user_id = created_user.json()["id"]
    assert "password_hash" not in client.get(f"/api/v1/admin/users/{user_id}").json()
    updated_user = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "staff", "branch_id": branch.json()["id"]},
    )
    assert updated_user.status_code == 200
    assert updated_user.json()["role"] == "staff"
    assert updated_user.json()["branch_id"] == branch.json()["id"]

    injection_search = client.get(
        "/api/v1/admin/users",
        params={"search": "' OR 1=1 --"},
    )
    assert injection_search.status_code == 200
    assert injection_search.json()["items"] == []
    user_page = client.get("/api/v1/admin/users?search=Safe%20Response&role=customer&page=1&page_size=5")
    assert user_page.status_code == 200
    assert all("password_hash" not in item for item in user_page.json()["items"])
    analytics = client.get("/api/v1/admin/analytics")
    assert analytics.status_code == 200
    assert "completion_rate" in analytics.json()
    app.dependency_overrides.clear()
