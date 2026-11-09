import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.main import create_app
from app.models import (
    AuditLog,
    AuthSession,
    Branch,
    Notification,
    Organization,
    OrganizationMembership,
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


def test_api_responses_have_security_and_no_store_headers() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_production_api_responses_enable_hsts(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main as main_module

    monkeypatch.setattr(main_module.settings, "environment", "production")
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")
    assert response.headers["strict-transport-security"] == "max-age=31536000"


def setup_client(db: Session, user: User) -> TestClient:
    if user.role is UserRole.ADMIN and user.organization_id is not None:
        membership = db.get(
            OrganizationMembership,
            (user.id, user.organization_id),
        )
        if membership is None:
            db.add(
                OrganizationMembership(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    role=UserRole.ADMIN.value,
                )
            )
            db.commit()

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


def test_admin_can_manage_admin_accounts_and_deactivation_revokes_sessions(
    db_session: Session,
) -> None:
    owner = User(
        full_name="Platform Owner",
        email=f"owner-{uuid.uuid4()}@example.test",
        password_hash=hash_password("owner-password-123"),
        role=UserRole.ADMIN,
    )
    owner.organization = Organization(
        name="Owner Organization",
        slug=f"owner-{uuid.uuid4()}",
    )
    db_session.add(owner)
    db_session.commit()
    client = setup_client(db_session, owner)

    assert client.delete(f"/api/v1/admin/users/{owner.id}").status_code == 409
    assert client.patch(
        f"/api/v1/admin/users/{owner.id}", json={"role": "customer"}
    ).status_code == 409

    email = f"managed-admin-{uuid.uuid4()}@example.test"
    created = client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "Managed Admin",
            "email": email,
            "password": "managed-password-123",
            "role": "admin",
        },
    )
    assert created.status_code == 201
    assert created.json()["role"] == "admin"
    assert "password_hash" not in created.json()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "managed-password-123"},
    )
    assert login.status_code == 200
    managed_token = login.json()["session_token"]
    managed_id = uuid.UUID(created.json()["id"])
    membership = db_session.get(
        OrganizationMembership,
        (managed_id, owner.organization_id),
    )
    assert membership is not None
    assert membership.role == UserRole.ADMIN.value
    session_hash = db_session.query(AuthSession).filter_by(user_id=managed_id).one()

    search = client.get(
        "/api/v1/admin/users",
        params={
            "search": email,
            "role": "admin",
            "active": "true",
            "auth_provider": "local",
        },
    )
    assert search.status_code == 200
    assert [user["id"] for user in search.json()["items"]] == [str(managed_id)]
    assert search.json()["items"][0]["last_login_at"] is not None

    deactivated = client.delete(f"/api/v1/admin/users/{managed_id}")
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    db_session.refresh(session_hash)
    assert session_hash.revoked_at is not None
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {managed_token}"},
    ).status_code == 401
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
    organization_audits = db_session.query(AuditLog).filter(
        AuditLog.target_id == organization_id
    ).all()
    assert {event.action for event in organization_audits} >= {
        "organization.created",
        "organization.updated",
    }
    assert all(event.actor_user_id == admin.id for event in organization_audits)
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
    waiting_customer.full_name = "=SUM(1,1)"
    db_session.commit()
    report = client.get("/api/v1/admin/reports/queue-entries.csv")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    assert "attachment;" in report.headers["content-disposition"]
    assert "'=SUM(1,1)" in report.text
    empty_report = client.get(
        "/api/v1/admin/reports/queue-entries.csv",
        params={"start": "2099-01-01T00:00:00Z"},
    )
    assert empty_report.status_code == 200
    assert "Waiting Customer" not in empty_report.text
    assert client.get(
        "/api/v1/admin/reports/queue-entries.csv",
        params={
            "start": "2026-10-02T00:00:00Z",
            "end": "2026-10-01T00:00:00Z",
        },
    ).status_code == 422
    customer_client = setup_client(db_session, waiting_customer)
    assert customer_client.get(
        f"/api/v1/admin/queues/{queue.json()['id']}/entries"
    ).status_code == 403
    assert customer_client.get(
        "/api/v1/admin/reports/queue-entries.csv"
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
    assert client.delete(f"/api/v1/admin/organizations/{organization_id}").status_code == 403
    assert client.get(f"/api/v1/admin/organizations/{organization_id}").json()["is_active"] is True

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
    staff_membership = db_session.get(
        OrganizationMembership,
        (uuid.UUID(staff_user.json()["id"]), uuid.UUID(organization_id)),
    )
    assert staff_membership is not None
    assert staff_membership.role == UserRole.STAFF.value

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


def test_admin_resources_and_reports_are_scoped_to_their_organization(
    db_session: Session,
) -> None:
    first_organization = Organization(
        name="First Tenant",
        slug=f"first-{uuid.uuid4()}",
    )
    second_organization = Organization(
        name="Second Tenant",
        slug=f"second-{uuid.uuid4()}",
    )
    first_branch = Branch(name="First Branch", organization=first_organization)
    second_branch = Branch(name="Second Branch", organization=second_organization)
    first_service = Service(
        name="First Service",
        code="FIRST",
        branch=first_branch,
    )
    second_service = Service(
        name="Second Service",
        code="SECOND",
        branch=second_branch,
    )
    first_queue = Queue(name="First Queue", prefix="F", service=first_service)
    second_queue = Queue(name="Second Queue", prefix="S", service=second_service)
    admin = User(
        full_name="First Tenant Admin",
        email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("tenant-admin-password"),
        role=UserRole.ADMIN,
        organization=first_organization,
    )
    customer = User(
        full_name="Tenant Customer",
        email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("tenant-customer-password"),
    )
    other_customer = User(
        full_name="Other Tenant Customer",
        email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("other-tenant-password"),
    )
    db_session.add_all([first_queue, second_queue, admin, customer, other_customer])
    db_session.flush()
    db_session.add(
        QueueEntry(
            queue=first_queue,
            customer=customer,
            queue_number=1,
        )
    )
    db_session.add(
        QueueEntry(
            queue=second_queue,
            customer=other_customer,
            queue_number=1,
        )
    )
    db_session.commit()

    client = setup_client(db_session, admin)
    branches = client.get("/api/v1/admin/branches")
    assert branches.status_code == 200
    assert [branch["id"] for branch in branches.json()["items"]] == [
        str(first_branch.id)
    ]
    services = client.get("/api/v1/admin/services")
    assert [service["id"] for service in services.json()["items"]] == [
        str(first_service.id)
    ]
    queues = client.get("/api/v1/admin/queues")
    assert [queue["id"] for queue in queues.json()["items"]] == [
        str(first_queue.id)
    ]
    users = client.get("/api/v1/admin/users")
    assert users.status_code == 200
    assert "Other Tenant Customer" not in {
        user["full_name"] for user in users.json()["items"]
    }
    analytics = client.get("/api/v1/admin/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["organizations"] == 1
    assert analytics.json()["services"] == 1
    assert analytics.json()["queues"] == 1
    assert analytics.json()["queue_entries"] == 1
    assert client.get(
        f"/api/v1/admin/branches/{second_branch.id}"
    ).status_code == 404
    assert client.get(
        f"/api/v1/admin/queues/{second_queue.id}/entries"
    ).status_code == 404
    assert client.post(
        "/api/v1/admin/services",
        json={
            "branch_id": str(second_branch.id),
            "name": "Unauthorized Service",
            "code": "DENIED",
        },
    ).status_code == 404
    assert client.post(
        "/api/v1/admin/organizations",
        json={"name": "Unauthorized Tenant", "slug": f"unauthorized-{uuid.uuid4()}"},
    ).status_code == 403

    report = client.get("/api/v1/admin/reports/queue-entries.csv")
    assert report.status_code == 200
    assert "First Queue" in report.text
    assert "Second Queue" not in report.text
    app.dependency_overrides.clear()
