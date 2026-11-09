import uuid
import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user, get_db
from app.auth.sessions import hash_opaque_token, new_session
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models import (
    AuthSession,
    Branch,
    Counter,
    Organization,
    PasswordResetToken,
    Queue,
    QueueEntry,
    Service,
    User,
)
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


def test_admin_api_authorization_is_enforced_by_backend() -> None:
    class EmptyAdminDb:
        @staticmethod
        def scalar(*args: object) -> int:
            assert args
            return 0

        @staticmethod
        def scalars(*args: object) -> list[object]:
            assert args
            return []

    current_role = {"value": UserRole.CUSTOMER}

    def current_user():
        return SimpleNamespace(
            role=current_role["value"],
            organization_id=None,
        )

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = EmptyAdminDb
    client = TestClient(app)

    for role in (UserRole.CUSTOMER, UserRole.STAFF):
        current_role["value"] = role
        assert client.get("/api/v1/admin/organizations").status_code == 403

    current_role["value"] = UserRole.ADMIN
    assert client.get("/api/v1/admin/organizations").status_code == 200


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
    staff_customers = staff_client.get("/api/v1/staff/customers")
    assert staff_customers.status_code == 200
    assert any(
        item["entry_id"] == entry_id and item["customer"]["id"] == str(customer.id)
        for item in staff_customers.json()
    )
    staff_history = staff_client.get("/api/v1/staff/history")
    assert staff_history.status_code == 200
    assert any(
        item["entry_id"] == entry_id
        and item["queue_name"] == "Auth Queue"
        and item["status"] == "completed"
        for item in staff_history.json()
    )
    assert auth_client(db_session, outsider).get("/api/v1/staff/history").json() == []
    assert staff_client.post(f"/api/v1/queue-entries/{entry_id}/complete").status_code == 409
    waiting = QueueEntry(queue=queue, customer=customer, queue_number=2)
    db_session.add(waiting)
    db_session.commit()
    assert customer_client.post(f"/api/v1/queue-entries/{waiting.id}/cancel").status_code == 200
    assert customer_client.post(f"/api/v1/queue-entries/{waiting.id}/cancel").status_code == 409
    assert staff_client.post(f"/api/v1/staff/queues/{queue.id}/pause").status_code == 200
    assert customer_client.post(f"/api/v1/staff/queues/{queue.id}/resume").status_code == 403
    assert staff_client.post(f"/api/v1/staff/queues/{queue.id}/resume").status_code == 200


def test_public_catalog_returns_database_services_and_queue_ids(db_session: Session) -> None:
    branch, _, queue = make_queue(db_session)

    def override_db():
        yield db_session

    client = TestClient(app)
    app.dependency_overrides[get_db] = override_db

    response = client.get(
        "/api/v1/catalog/services", params={"branch_id": str(branch.id)}
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(queue.service.id),
            "branch_id": str(branch.id),
            "name": "Auth Service",
            "code": queue.service.code,
            "description": queue.service.description,
            "average_service_minutes": queue.service.average_service_minutes,
            "queue_id": str(queue.id),
        }
    ]


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


def test_login_sets_http_only_session_cookie_and_register_hash_is_not_exposed(db_session: Session) -> None:
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
    assert response.json()["session_token"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": response.json()["user"]["email"], "password": "test-password-123"},
    )
    assert login.status_code == 200
    assert "access_token" not in login.json()
    session_token = login.json()["session_token"]
    assert session_token
    assert login.json()["user"]["email"] == response.json()["user"]["email"]
    assert client.cookies.get("queueless_session")
    assert "httponly" in login.headers["set-cookie"].lower()
    assert client.get("/api/v1/auth/me").json()["email"] == response.json()["user"]["email"]
    bearer_client = TestClient(app)
    bearer_client.headers["Authorization"] = f"Bearer {session_token}"
    assert bearer_client.get("/api/v1/auth/me").json()["email"] == response.json()["user"]["email"]
    assert bearer_client.post("/api/v1/auth/logout").status_code == 204
    assert bearer_client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_invalid_authorization_header_cannot_fall_back_to_cookie(
    db_session: Session,
) -> None:
    user = make_user("header-precedence", UserRole.CUSTOMER)
    db_session.add(user)
    db_session.commit()
    session, token = new_session(user)
    db_session.add(session)
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.cookies.set("queueless_session", token)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Basic not-a-bearer-token"},
    )
    assert response.status_code == 401


def test_revoked_session_cannot_issue_websocket_ticket(db_session: Session) -> None:
    customer = make_user("revoked-ws", UserRole.CUSTOMER)
    branch, _, queue = make_queue(db_session)
    customer.organization_id = branch.organization_id
    db_session.add(customer)
    db_session.commit()
    session, token = new_session(customer)
    db_session.add(session)
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.post(
        "/api/v1/auth/ws-ticket",
        json={"queue_id": str(queue.id)},
    ).status_code == 401


def test_registration_normalizes_email_and_rejects_case_insensitive_duplicate(
    db_session: Session,
) -> None:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    email = f"{uuid.uuid4()}@example.test"
    first = client.post(
        "/api/v1/auth/register",
        json={"full_name": "First Person", "email": email.upper(), "password": "test-password-123"},
    )
    assert first.status_code == 201
    assert first.json()["user"]["email"] == email
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Another Person", "email": email, "password": "test-password-123"},
    )
    assert duplicate.status_code == 409


def test_new_organization_requires_admin_approval_before_customer_login(
    db_session: Session,
) -> None:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    email = f"{uuid.uuid4()}@example.test"
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "New Customer",
            "email": email,
            "password": "customer-password",
            "organization_name": "New Customer Organization",
        },
    )
    assert registration.status_code == 202
    assert registration.json()["status"] == "pending_approval"
    assert "session_token" not in registration.json()
    organization = db_session.scalar(
        select(Organization).where(
            Organization.slug == "new-customer-organization"
        )
    )
    user = db_session.scalar(select(User).where(User.email == email))
    assert organization is not None and not organization.is_approved
    assert user is not None and not user.is_active and user.approval_pending

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "customer-password"},
    )
    assert login.status_code == 403
    assert "awaiting administrator approval" in login.json()["detail"]

    super_admin = db_session.scalar(
        select(User).where(User.role == UserRole.SUPER_ADMIN)
    )
    if super_admin is None:
        super_admin = make_user("approval-super-admin", UserRole.SUPER_ADMIN)
        db_session.add(super_admin)
        db_session.commit()
    auth_session, session_token = new_session(super_admin)
    db_session.add(auth_session)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    client.headers["Authorization"] = "Bearer " + session_token
    admin_create_pending_account = client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "Admin-Created Pending Customer",
            "email": f"{uuid.uuid4()}@example.test",
            "password": "customer-password",
            "role": "customer",
            "organization_id": str(organization.id),
        },
    )
    assert admin_create_pending_account.status_code == 409
    assert (
        client.post(
            f"/api/v1/admin/organizations/{organization.id}/activate"
        ).status_code
        == 409
    )
    approval = client.post(
        f"/api/v1/admin/organizations/{organization.id}/approve"
    )
    assert approval.status_code == 200
    assert approval.json()["approved_accounts"] == 1
    db_session.refresh(organization)
    db_session.refresh(user)
    assert organization.is_approved and organization.is_active
    assert user.is_active and not user.approval_pending

    successful_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "customer-password"},
    )
    assert successful_login.status_code == 200
    assert successful_login.json()["user"]["organization_id"] == str(organization.id)

    existing_organization_registration = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Existing Organization Customer",
            "email": f"{uuid.uuid4()}@example.test",
            "password": "customer-password",
            "organization_name": "New Customer Organization",
        },
    )
    assert existing_organization_registration.status_code == 201
    assert (
        existing_organization_registration.json()["user"]["organization_id"]
        == str(organization.id)
    )


def test_profile_update_and_password_change_are_authenticated_and_revoke_other_sessions(
    db_session: Session,
) -> None:
    user = make_user("profile", UserRole.CUSTOMER)
    db_session.add(user)
    db_session.flush()
    current_session, current_token = new_session(user)
    other_session, _ = new_session(user)
    db_session.add_all([current_session, other_session])
    db_session.commit()

    client = auth_client(db_session, user)
    client.headers["Authorization"] = f"Bearer {current_token}"

    updated = client.patch("/api/v1/auth/me", json={"full_name": "Updated Name"})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Name"
    assert updated.json()["role"] == "customer"
    assert client.patch("/api/v1/auth/me", json={"full_name": " "}).status_code == 422

    incorrect = client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "incorrect-password",
            "new_password": "new-password-123",
        },
    )
    assert incorrect.status_code == 400
    assert verify_password("test-password-123", user.password_hash)

    changed = client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "test-password-123",
            "new_password": "new-password-123",
        },
    )
    assert changed.status_code == 200
    assert "Other active sessions" in changed.json()["message"]
    assert verify_password("new-password-123", user.password_hash)
    db_session.refresh(current_session)
    db_session.refresh(other_session)
    assert current_session.revoked_at is None
    assert other_session.revoked_at is not None
    assert client.get("/api/v1/auth/me").status_code == 200


def test_password_reset_is_one_time_and_revokes_existing_sessions(db_session: Session) -> None:
    user = make_user("password-reset", UserRole.CUSTOMER)
    db_session.add(user)
    db_session.commit()
    raw_token = secrets.token_urlsafe(48)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_opaque_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db_session.add(reset_token)
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "test-password-123"},
    )
    assert login.status_code == 200
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "password": "new-password-456"},
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "password": "another-password-789"},
    ).status_code == 400
    assert client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "new-password-456"},
    ).status_code == 200


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
