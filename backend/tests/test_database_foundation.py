import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateIndex

from app.db.base import Base
from app.db.session import engine
from app.config import settings
from app.models import (
    Branch,
    Feedback,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    Service,
    User,
)
from app.models.entities import QueueEntryStatus, QueueStatus, UserRole


def test_database_connection(database_engine) -> None:
    with database_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT 1").scalar() == 1


def test_sqlite_connection_pragmas_are_applied() -> None:
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert (
            connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()
            == settings.sqlite_busy_timeout_ms
        )
        synchronous_modes = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}
        actual_mode = synchronous_modes[
            connection.exec_driver_sql("PRAGMA synchronous").scalar_one()
        ]
        assert actual_mode == settings.sqlite_synchronous


def test_migration_schema_tables(database_engine) -> None:
    tables = set(inspect(database_engine).get_table_names())
    assert tables == set(Base.metadata.tables) | {
        "alembic_version",
        "system_settings",
    }
    assert {
        "users",
        "organizations",
        "branches",
        "services",
        "counters",
        "queues",
        "queue_entries",
        "queue_events",
        "notifications",
        "feedback",
        "feedback_reports",
        "feedback_replies",
        "feedback_status_history",
        "feedback_votes",
        "feedback_improvement_tasks",
        "feedback_task_links",
        "appointment_slots",
        "appointments",
        "queue_transfers",
        "scheduled_jobs",
        "scheduled_job_executions",
        "outbox_events",
    } <= tables


def test_database_is_at_current_alembic_revision(database_engine) -> None:
    with database_engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert revision == "0025_remove_google_auth"


def test_user_administration_filters_have_indexes(database_engine) -> None:
    indexes = {
        index["name"]
        for index in inspect(database_engine).get_indexes("users")
    }

    assert "ix_users_role_active_created_at" in indexes
    assert "ix_users_active_created_at" in indexes


def test_user_creation(db_session) -> None:
    user = User(full_name="Ada Lovelace", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    assert user.id is not None
    assert user.role is UserRole.CUSTOMER


def test_organization_branch_relationship(db_session) -> None:
    organization = Organization(name="Org", slug=str(uuid.uuid4()))
    organization.branches.append(Branch(name="Main", address="Campus"))
    db_session.add(organization)
    db_session.commit()
    assert organization.branches[0].organization is organization


def test_service_queue_relationship(db_session) -> None:
    branch = Branch(name="Branch", organization=Organization(name="Org", slug=str(uuid.uuid4())))
    service = Service(name="Admissions", code="ADM", branch=branch)
    service.queues.append(Queue(name="Main", prefix="A"))
    db_session.add(service)
    db_session.commit()
    assert service.queues[0].service is service


def test_queue_entry_relationship(db_session) -> None:
    user = User(full_name="Customer", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    queue = Queue(name="Main", prefix="A", service=Service(name="Service", code="SVC", branch=Branch(name="Branch", organization=Organization(name="Org", slug=str(uuid.uuid4())))))
    entry = QueueEntry(queue=queue, customer=user, queue_number=1)
    db_session.add(entry)
    db_session.commit()
    assert entry.queue is queue
    assert entry.customer is user


def test_unique_email_constraint(db_session) -> None:
    email = f"{uuid.uuid4()}@example.com"
    db_session.add_all([
        User(full_name="One", email=email, password_hash="hash"),
        User(full_name="Two", email=email, password_hash="hash"),
    ])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_database_constraints_are_declared(database_engine) -> None:
    constraints = {
        constraint["name"]
        for constraint in inspect(database_engine).get_check_constraints("feedback")
    }
    assert "ck_feedback_rating_range" in constraints
    membership_constraints = {
        constraint["name"]
        for constraint in inspect(database_engine).get_check_constraints(
            "organization_memberships"
        )
    }
    assert "ck_organization_memberships_role" in membership_constraints


def test_super_admin_unique_index_is_partial_for_postgresql() -> None:
    index = next(
        index
        for index in User.__table__.indexes
        if index.name == "uq_users_single_super_admin"
    )

    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))

    assert "CREATE UNIQUE INDEX" in ddl
    assert "WHERE role = 'super_admin'" in ddl


def test_organization_membership_rejects_platform_role(db_session) -> None:
    user = User(
        full_name="Member",
        email=f"{uuid.uuid4()}@example.test",
        password_hash="hash",
    )
    organization = Organization(name="Member Org", slug=str(uuid.uuid4()))
    db_session.add_all([user, organization])
    db_session.flush()
    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=organization.id,
        role=UserRole.SUPER_ADMIN.value,
    )
    db_session.add(membership)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_feedback_rating_constraint(db_session) -> None:
    user = User(full_name="Customer", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    queue = Queue(
        name="Main",
        prefix="A",
        service=Service(
            name="Service",
            code="SVC",
            branch=Branch(
                name="Branch",
                organization=Organization(name="Org", slug=str(uuid.uuid4())),
            ),
        ),
    )
    entry = QueueEntry(queue=queue, customer=user, queue_number=1)
    db_session.add(Feedback(queue_entry=entry, rating=6))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_queue_entry_status_contract() -> None:
    assert {status.value for status in QueueEntryStatus} == {"waiting", "called", "serving", "completed", "skipped", "cancelled"}
    assert {status.value for status in QueueStatus} == {"open", "paused", "closed"}
