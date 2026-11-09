import uuid
from collections.abc import Generator
from datetime import timedelta, timezone, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app import cli
from app.api.auth_dependencies import get_db
from app.auth.sessions import hash_opaque_token, new_session
from app.core.security import hash_password
from app.db.base import Base
from app.main import app
from app.models import (
    AuditLog,
    Announcement,
    AuthSession,
    Branch,
    Counter,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    Service,
    User,
)
from app.models.entities import QueueEntryStatus, UserRole


def make_user(
    role: UserRole,
    *,
    email: str | None = None,
    verified: bool = True,
) -> User:
    return User(
        full_name=role.value,
        email=email or f"{role.value}-{uuid.uuid4()}@example.test",
        password_hash=hash_password("test-password-123"),
        role=role,
        email_verified=verified,
    )


def make_super_admin(db: Session) -> User:
    existing = db.scalar(select(User).where(User.role == UserRole.SUPER_ADMIN))
    if existing is not None:
        return existing
    user = make_user(UserRole.SUPER_ADMIN)
    db.add(user)
    db.commit()
    return user


def authenticated_client(db: Session, user: User) -> tuple[TestClient, str]:
    session, token = new_session(user)
    db.add(session)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client, token


@pytest.fixture
def isolated_setup_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Session, None, None]:
    database_url = f"sqlite:///{(tmp_path / 'initial-setup.db').as_posix()}"
    monkeypatch.setattr("app.config.settings.database_url", database_url)
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    alembic_config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(alembic_config, "head")
    isolated_session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield isolated_session
    finally:
        isolated_session.close()
        engine.dispose()


def test_super_admin_bootstrap_requires_configured_verified_existing_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    isolated_session = sessionmaker(bind=engine, expire_on_commit=False)()
    email = f"Owner-{uuid.uuid4()}@example.test"
    owner = make_user(UserRole.CUSTOMER, email=email)
    session, _ = new_session(owner)
    isolated_session.add_all([owner, session])
    isolated_session.commit()
    monkeypatch.setattr(cli.settings, "super_admin_email", f"  {email.upper()}  ")

    promoted = cli.bootstrap_super_admin(isolated_session)

    assert promoted.id == owner.id
    assert promoted.email == email
    assert promoted.role is UserRole.SUPER_ADMIN
    isolated_session.refresh(session)
    assert session.revoked_at is not None
    assert isolated_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "super_admin.bootstrap"
        )
    ) == 1
    assert cli.bootstrap_super_admin(isolated_session).id == owner.id
    assert isolated_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "super_admin.bootstrap"
        )
    ) == 1
    isolated_session.close()
    engine.dispose()


def test_super_admin_bootstrap_does_not_create_or_promote_unverified_accounts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = f"unverified-{uuid.uuid4()}@example.test"
    user = make_user(UserRole.CUSTOMER, email=email, verified=False)
    db_session.add(user)
    db_session.commit()
    monkeypatch.setattr(cli.settings, "super_admin_email", email)

    with pytest.raises(ValueError, match="not verified"):
        cli.bootstrap_super_admin(db_session)
    assert user.role is UserRole.CUSTOMER

    monkeypatch.setattr(
        cli.settings, "super_admin_email", f"missing-{uuid.uuid4()}@example.test"
    )
    with pytest.raises(ValueError, match="Register and verify"):
        cli.bootstrap_super_admin(db_session)

    monkeypatch.setattr(cli.settings, "super_admin_email", None)
    with pytest.raises(ValueError, match="SUPER_ADMIN_EMAIL"):
        cli.bootstrap_super_admin(db_session)


def test_only_super_admin_can_read_global_dashboard(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(
        "app.api.routes.super_admin.settings.database_backup_dir",
        str(tmp_path / "backups"),
    )
    admin = make_user(UserRole.ADMIN)
    super_admin = make_super_admin(db_session)
    db_session.add(admin)
    db_session.commit()

    admin_client, _ = authenticated_client(db_session, admin)
    assert admin_client.get("/api/v1/super-admin/dashboard").status_code == 403

    super_client, _ = authenticated_client(db_session, super_admin)
    response = super_client.get("/api/v1/super-admin/dashboard")
    assert response.status_code == 200
    assert response.json()["users"]["super_admin"] == 1
    expected_waiting = db_session.scalar(
        select(func.count(QueueEntry.id)).where(
            QueueEntry.status == QueueEntryStatus.WAITING
        )
    )
    assert response.json()["queues"]["waiting"] == expected_waiting
    assert response.json()["services"] == db_session.scalar(
        select(func.count(Service.id))
    )
    assert response.json()["counters"] == db_session.scalar(
        select(func.count(Counter.id))
    )
    assert super_client.get("/api/v1/super-admin/system-health").json() == {
        "api": "ok",
        "database": "connected",
        "backup_monitoring": "no snapshots",
    }
    app.dependency_overrides.clear()


def test_announcement_publication_is_role_filtered_and_audited(
    db_session: Session,
) -> None:
    super_admin = make_super_admin(db_session)
    customer = make_user(UserRole.CUSTOMER)
    staff = make_user(UserRole.STAFF)
    db_session.add_all([customer, staff])
    db_session.commit()
    admin_client, _ = authenticated_client(db_session, super_admin)
    customer_client, _ = authenticated_client(db_session, customer)
    staff_client, _ = authenticated_client(db_session, staff)

    response = admin_client.post(
        "/api/v1/super-admin/announcements",
        json={
            "title": "Opening hours",
            "body": "The branch closes at 16:00 today.",
            "audience": "customer",
            "expires_at": None,
        },
    )
    assert response.status_code == 201, response.text
    announcement_id = response.json()["id"]
    assert customer_client.get("/api/v1/announcements").json() == []
    assert (
        TestClient(app)
        .post("/api/v1/auth/announcements-ws-ticket")
        .status_code
        == 401
    )
    ticket = customer_client.post("/api/v1/auth/announcements-ws-ticket")
    assert ticket.status_code == 200
    assert ticket.json()["ticket"]

    published = admin_client.post(
        f"/api/v1/super-admin/announcements/{announcement_id}/publish"
    )
    assert published.status_code == 200, published.text
    customer_announcements = customer_client.get("/api/v1/announcements")
    assert customer_announcements.status_code == 200
    assert [item["title"] for item in customer_announcements.json()] == [
        "Opening hours"
    ]
    assert staff_client.get("/api/v1/announcements").json() == []
    assert db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "announcement.published"
        )
    ) == 1

    admin_user = make_user(UserRole.ADMIN)
    db_session.add(admin_user)
    db_session.commit()
    regular_admin_client, _ = authenticated_client(db_session, admin_user)
    assert (
        regular_admin_client.get("/api/v1/super-admin/announcements").status_code
        == 403
    )


def test_platform_settings_gate_api_but_preserve_super_admin_controls(
    db_session: Session,
) -> None:
    super_admin = make_super_admin(db_session)
    customer = make_user(UserRole.CUSTOMER)
    db_session.add(customer)
    db_session.commit()
    admin_client, _ = authenticated_client(db_session, super_admin)
    customer_client, _ = authenticated_client(db_session, customer)
    changed = admin_client.put(
        "/api/v1/super-admin/platform-settings",
        json={
            "maintenance_mode": True,
            "maintenance_message": "Scheduled maintenance.",
        },
    )
    assert changed.status_code == 200, changed.text
    assert (
        admin_client.get("/api/v1/super-admin/platform-settings").json()[
            "maintenance_mode"
        ]
        is True
    )
    unavailable = customer_client.get("/api/v1/catalog/organizations")
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "maintenance_mode"
    assert admin_client.get("/api/v1/super-admin/dashboard").status_code == 200
    assert admin_client.get("/api/v1/system-status").json()["maintenance_mode"] is True
    disabled = admin_client.put(
        "/api/v1/super-admin/platform-settings",
        json={
            "maintenance_mode": False,
            "maintenance_message": "Scheduled maintenance.",
        },
    )
    assert disabled.status_code == 200
    assert customer_client.get("/api/v1/catalog/organizations").status_code == 200


def test_organization_announcements_are_limited_to_admins_and_their_staff(
    db_session: Session,
) -> None:
    organization = Organization(name="Org One", slug=f"org-{uuid.uuid4()}")
    other_organization = Organization(name="Org Two", slug=f"org-{uuid.uuid4()}")
    db_session.add_all([organization, other_organization])
    db_session.flush()
    branch = Branch(organization_id=organization.id, name="Main")
    other_branch = Branch(organization_id=other_organization.id, name="Main")
    db_session.add_all([branch, other_branch])
    db_session.flush()
    admin = make_user(UserRole.ADMIN)
    admin.organization_id = organization.id
    staff = make_user(UserRole.STAFF)
    staff.branch_id = branch.id
    other_staff = make_user(UserRole.STAFF)
    other_staff.branch_id = other_branch.id
    db_session.add_all([admin, staff, other_staff])
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            user_id=admin.id,
            organization_id=organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db_session.commit()

    admin_client, _ = authenticated_client(db_session, admin)
    staff_client, _ = authenticated_client(db_session, staff)
    other_staff_client, _ = authenticated_client(db_session, other_staff)
    invalid_audience = admin_client.post(
        "/api/v1/admin/announcements",
        json={
            "title": "Customer announcement",
            "body": "This must not be global.",
            "audience": "customer",
        },
    )
    assert invalid_audience.status_code == 422

    created = admin_client.post(
        "/api/v1/admin/announcements",
        json={
            "title": "Team briefing",
            "body": "Please attend the branch briefing.",
            "audience": "staff",
        },
    )
    assert created.status_code == 201, created.text
    announcement_id = created.json()["id"]
    assert admin_client.post(
        f"/api/v1/admin/announcements/{announcement_id}/publish"
    ).status_code == 200
    assert [
        entry["title"] for entry in staff_client.get("/api/v1/announcements").json()
    ] == ["Team briefing"]
    assert other_staff_client.get("/api/v1/announcements").json() == []

    outsider = make_user(UserRole.ADMIN)
    outsider.organization_id = other_organization.id
    db_session.add(outsider)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            user_id=outsider.id,
            organization_id=other_organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db_session.commit()
    outsider_client, _ = authenticated_client(db_session, outsider)
    assert outsider_client.get("/api/v1/admin/announcements").json() == []
    assert (
        outsider_client.post(
            f"/api/v1/admin/announcements/{announcement_id}/publish"
        ).status_code
        == 404
    )


def test_super_admin_initial_setup_creates_real_workspace_in_one_transaction(
    isolated_setup_session: Session,
) -> None:
    super_admin = make_super_admin(isolated_setup_session)
    client, _ = authenticated_client(isolated_setup_session, super_admin)
    payload = {
        "organization_name": "Example Health",
        "organization_slug": "EXAMPLE-HEALTH",
        "branch_name": "Central",
        "branch_address": "1 Main Street",
        "timezone": "Europe/London",
        "service_name": "Appointments",
        "service_code": "appt",
        "average_service_minutes": 15,
        "queue_name": "Appointments queue",
        "queue_prefix": "a",
    }

    response = client.post("/api/v1/super-admin/initial-setup", json=payload)

    assert response.status_code == 201, response.text
    result = response.json()
    organization = isolated_setup_session.get(
        Organization, uuid.UUID(result["organization_id"])
    )
    branch = isolated_setup_session.get(Branch, uuid.UUID(result["branch_id"]))
    service = isolated_setup_session.get(Service, uuid.UUID(result["service_id"]))
    queue = isolated_setup_session.get(Queue, uuid.UUID(result["queue_id"]))
    assert organization is not None
    assert organization.name == "Example Health"
    assert organization.slug == "example-health"
    assert branch is not None
    assert branch.organization_id == organization.id
    assert branch.timezone == "Europe/London"
    assert service is not None
    assert service.branch_id == branch.id
    assert service.code == "APPT"
    assert queue is not None
    assert queue.service_id == service.id
    assert queue.prefix == "A"
    audit = isolated_setup_session.scalar(
        select(AuditLog).where(AuditLog.action == "initial_setup.completed")
    )
    assert audit is not None
    assert audit.actor_user_id == super_admin.id
    assert audit.target_id == str(organization.id)

    duplicate = client.post("/api/v1/super-admin/initial-setup", json=payload)
    assert duplicate.status_code == 409
    assert isolated_setup_session.scalar(select(func.count(Organization.id))) == 1
    assert isolated_setup_session.scalar(select(func.count(Branch.id))) == 1
    assert isolated_setup_session.scalar(select(func.count(Service.id))) == 1
    assert isolated_setup_session.scalar(select(func.count(Queue.id))) == 1
    app.dependency_overrides.clear()


def test_super_admin_initial_setup_rejects_blank_names(
    isolated_setup_session: Session,
) -> None:
    super_admin = make_super_admin(isolated_setup_session)
    client, _ = authenticated_client(isolated_setup_session, super_admin)
    response = client.post(
        "/api/v1/super-admin/initial-setup",
        json={
            "organization_name": "   ",
            "organization_slug": "example",
            "branch_name": "Central",
            "timezone": "UTC",
            "service_name": "Appointments",
            "service_code": "APT",
            "average_service_minutes": 10,
            "queue_name": "Main",
            "queue_prefix": "A",
        },
    )

    assert response.status_code == 422
    assert isolated_setup_session.scalar(select(func.count(Organization.id))) == 0
    app.dependency_overrides.clear()


def test_super_admin_can_create_and_list_verified_backups(
    db_session: Session,
    database_engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.super_admin.settings.database_url",
        database_engine.url.render_as_string(hide_password=False),
    )
    monkeypatch.setattr(
        "app.api.routes.super_admin.settings.database_backup_dir",
        str(tmp_path / "backups"),
    )
    super_admin = make_super_admin(db_session)
    client, _ = authenticated_client(db_session, super_admin)

    assert client.get("/api/v1/super-admin/backups").json() == []
    created = client.post("/api/v1/super-admin/backups")
    assert created.status_code == 201, created.text
    assert created.json()["filename"].endswith(".sqlite3")
    assert created.json()["size_bytes"] > 0
    listed = client.get("/api/v1/super-admin/backups")
    assert listed.status_code == 200
    assert listed.json()[0]["filename"] == created.json()["filename"]
    assert db_session.scalar(
        select(AuditLog).where(AuditLog.action == "database.backup_created")
    ) is not None
    app.dependency_overrides.clear()


def test_regular_admin_cannot_grant_or_modify_super_admin(
    db_session: Session,
) -> None:
    admin = make_user(UserRole.ADMIN)
    super_admin = make_super_admin(db_session)
    db_session.add(admin)
    db_session.commit()
    client, _ = authenticated_client(db_session, admin)

    created = client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "Attempted Super Admin",
            "email": f"attempt-{uuid.uuid4()}@example.test",
            "password": "test-password-123",
            "role": "super_admin",
        },
    )
    changed = client.patch(
        f"/api/v1/admin/users/{super_admin.id}",
        json={"role": "admin"},
    )
    assert created.status_code == 403
    assert changed.status_code == 404
    db_session.refresh(super_admin)
    assert super_admin.role is UserRole.SUPER_ADMIN
    assert client.delete(
        f"/api/v1/admin/users/{super_admin.id}"
    ).status_code == 404
    app.dependency_overrides.clear()


def test_super_admin_sensitive_actions_require_recent_session_and_audit(
    db_session: Session,
) -> None:
    super_admin = make_super_admin(db_session)
    customer = make_user(UserRole.CUSTOMER)
    db_session.add(customer)
    db_session.commit()
    client, token = authenticated_client(db_session, super_admin)

    blocked = client.patch(
        f"/api/v1/super-admin/users/{customer.id}/role",
        json={"role": "super_admin"},
    )
    assert blocked.status_code == 403

    changed = client.patch(
        f"/api/v1/super-admin/users/{customer.id}/role",
        json={"role": "admin"},
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "admin"
    assert db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user.role_changed")
    ) is not None

    session = db_session.scalar(
        select(AuthSession).where(
            AuthSession.session_token_hash == hash_opaque_token(token)
        )
    )
    assert session is not None
    session.created_at = datetime.now(timezone.utc) - timedelta(minutes=6)
    db_session.commit()
    stale = client.post(f"/api/v1/super-admin/users/{customer.id}/revoke-sessions")
    assert stale.status_code == 403

    denied = client.patch(
        f"/api/v1/super-admin/users/{super_admin.id}/role",
        json={"role": "admin"},
    )
    assert denied.status_code == 403
    app.dependency_overrides.clear()


def test_super_admin_account_cannot_be_deactivated(
    db_session: Session,
) -> None:
    super_admin = make_super_admin(db_session)
    client, _ = authenticated_client(db_session, super_admin)

    response = client.post(
        f"/api/v1/super-admin/users/{super_admin.id}/deactivate"
    )

    assert response.status_code == 409
    assert super_admin.is_active is True
    app.dependency_overrides.clear()


def test_failed_login_audit_does_not_store_email_or_password(
    db_session: Session,
) -> None:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    email = f"not-present-{uuid.uuid4()}@example.test"
    password = "never-store-this-password"

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    event = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "auth.login_failed")
    )
    assert event is not None
    assert event.target_id == hash_opaque_token(email)
    assert password not in str(event.details)
    assert email not in str(event.details)
    app.dependency_overrides.clear()