import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models import Branch, Organization, Queue, Service, User
from app.models.entities import UserRole
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
    assert client.get("/api/v1/admin/organizations?page=1&page_size=1").status_code == 200
    assert client.delete(f"/api/v1/admin/organizations/{organization_id}").status_code == 200
    assert client.get(f"/api/v1/admin/organizations/{organization_id}").json()["is_active"] is False

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
    user_page = client.get("/api/v1/admin/users?search=Safe%20Response&role=customer&page=1&page_size=5")
    assert user_page.status_code == 200
    assert all("password_hash" not in item for item in user_page.json()["items"])
    analytics = client.get("/api/v1/admin/analytics")
    assert analytics.status_code == 200
    assert "completion_rate" in analytics.json()
    app.dependency_overrides.clear()
