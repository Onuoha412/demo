import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli import create_admin_user, main, seed_demo_catalog
from app.config import settings
from app.core.security import verify_password
from app.models import Branch, Organization, Queue, QueueEntry, Service, User
from app.models.entities import UserRole


def test_create_admin_user_persists_hashed_admin_credentials(db_session: Session) -> None:
    email = f"ADMIN-{uuid.uuid4()}@example.test"
    admin = create_admin_user(
        db_session,
        "  First Admin ",
        f"  {email} ",
        "secure-password-123",
    )

    assert admin.full_name == "First Admin"
    assert admin.email == email.lower()
    assert admin.role is UserRole.ADMIN
    assert verify_password("secure-password-123", admin.password_hash)
    assert admin.password_hash != "secure-password-123"
    assert db_session.scalar(select(User).where(User.id == admin.id)) is not None


@pytest.mark.parametrize(
    ("full_name", "email", "password", "message"),
    [
        ("A", "admin@example.test", "secure-password-123", "Name"),
        ("First Admin", "invalid-email", "secure-password-123", "email"),
        ("First Admin", "admin@example.test", "short", "Password"),
    ],
)
def test_create_admin_user_rejects_invalid_input(
    db_session: Session,
    full_name: str,
    email: str,
    password: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        create_admin_user(db_session, full_name, email, password)


def test_create_admin_user_rejects_duplicate_email(db_session: Session) -> None:
    email = f"admin-{uuid.uuid4()}@example.test"
    create_admin_user(
        db_session, "First Admin", email, "secure-password-123"
    )

    with pytest.raises(ValueError, match="already exists"):
        create_admin_user(
            db_session, "Another Admin", email.upper(), "secure-password-456"
        )


def test_seed_demo_catalog_is_development_data_and_idempotent(
    db_session: Session,
) -> None:
    users_before = db_session.scalar(select(func.count()).select_from(User))
    entries_before = db_session.scalar(select(func.count()).select_from(QueueEntry))
    organization, branch = seed_demo_catalog(db_session)
    repeated_organization, repeated_branch = seed_demo_catalog(db_session)

    assert repeated_organization.id == organization.id
    assert repeated_branch.id == branch.id
    assert organization.name == "QueueLess Demo Center"
    assert db_session.scalar(select(func.count()).select_from(Organization)) == 1
    assert db_session.scalar(select(func.count()).select_from(Branch)) == 1
    assert db_session.scalar(select(func.count()).select_from(Service)) == 3
    assert db_session.scalar(select(func.count()).select_from(Queue)) == 3
    assert db_session.scalar(select(func.count()).select_from(User)) == users_before
    assert db_session.scalar(select(func.count()).select_from(QueueEntry)) == entries_before


def test_seed_demo_command_refuses_non_development_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.argv", ["app.cli", "seed-demo"])
    monkeypatch.setattr(settings, "environment", "test")

    assert main() == 1
    assert "only be seeded" in capsys.readouterr().err
