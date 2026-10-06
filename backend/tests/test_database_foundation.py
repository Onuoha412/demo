import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import Branch, Feedback, Organization, Queue, QueueEntry, Service, User
from app.models.entities import QueueEntryStatus, QueueStatus, UserRole


def test_database_connection(database_engine) -> None:
    with database_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT 1").scalar() == 1


def test_migration_schema_tables(database_engine) -> None:
    tables = set(inspect(database_engine).get_table_names())
    assert {"users", "organizations", "branches", "services", "counters", "queues", "queue_entries", "queue_events", "notifications", "feedback"} <= tables


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
