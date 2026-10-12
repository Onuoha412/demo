import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Branch,
    Notification,
    NotificationPreference,
    Organization,
    Queue,
    QueueEntry,
    Service,
    User,
)
from app.models.entities import NotificationType, QueueEntryStatus
from app.services.notifications import NotificationService


def test_join_notification_is_idempotent(db_session: Session) -> None:
    organization = Organization(name="Notify Org", slug=str(uuid.uuid4()))
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Admissions", code=str(uuid.uuid4())[:8], branch=branch)
    queue = Queue(name="Admissions", prefix="A", service=service)
    user = User(full_name="Customer", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    db_session.add_all([organization, queue, user])
    db_session.flush()
    entry = QueueEntry(queue=queue, customer=user, queue_number=1)
    db_session.add(entry)
    db_session.flush()
    service_layer = NotificationService(db_session)
    service_layer.for_entry(entry, "joined")
    service_layer.for_entry(entry, "joined")
    service_layer.for_entry(entry, "called")
    db_session.commit()
    notifications = list(db_session.scalars(select(Notification).where(Notification.user_id == user.id)))
    assert len(notifications) == 2
    assert len({notification.event_key for notification in notifications}) == 2
    assert service_layer.unread_count(user.id) == 2
    service_layer.mark_read(user.id, notifications[0].id)
    assert service_layer.unread_count(user.id) == 1


def test_approaching_notification_is_created_once(db_session: Session) -> None:
    organization = Organization(name="Approaching Org", slug=str(uuid.uuid4()))
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Admissions", code=str(uuid.uuid4())[:8], branch=branch)
    queue = Queue(name="Admissions", prefix="A", service=service)
    earlier_customer = User(
        full_name="Earlier Customer",
        email=f"{uuid.uuid4()}@example.com",
        password_hash="hash",
    )
    customer = User(full_name="Customer", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    earlier_entry = QueueEntry(
        queue=queue,
        customer=earlier_customer,
        queue_number=1,
        status=QueueEntryStatus.WAITING,
    )
    entry = QueueEntry(
        queue=queue,
        customer=customer,
        queue_number=2,
        status=QueueEntryStatus.WAITING,
    )
    db_session.add_all([organization, earlier_entry, entry])
    db_session.flush()

    service_layer = NotificationService(db_session)
    service_layer.approaching(entry)
    service_layer.approaching(entry)
    db_session.commit()

    notifications = list(
        db_session.scalars(select(Notification).where(Notification.user_id == customer.id))
    )
    assert len(notifications) == 1
    assert notifications[0].type.value == "queue_approaching"


def test_approaching_notification_returns_a_realtime_event_only_once(
    db_session: Session,
) -> None:
    organization = Organization(name="Realtime Org", slug=str(uuid.uuid4()))
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Admissions", code=str(uuid.uuid4())[:8], branch=branch)
    queue = Queue(name="Admissions", prefix="A", service=service)
    earlier_customer = User(
        full_name="Earlier Customer",
        email=f"{uuid.uuid4()}@example.com",
        password_hash="hash",
    )
    customer = User(full_name="Customer", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    earlier_entry = QueueEntry(queue=queue, customer=earlier_customer, queue_number=1)
    entry = QueueEntry(queue=queue, customer=customer, queue_number=2)
    db_session.add_all([organization, earlier_entry, entry])
    db_session.flush()
    service_layer = NotificationService(db_session)

    first_event = service_layer.approaching(entry)
    duplicate_event = service_layer.approaching(entry)

    assert first_event == {
        "queue_id": queue.id,
        "data": {
            "queue_entry_id": str(entry.id),
            "queue_number": entry.queue_number,
            "people_ahead": 1,
        },
    }
    assert duplicate_event is None


def test_queue_status_notifications_use_event_id_for_idempotency(
    db_session: Session,
) -> None:
    organization = Organization(name="Status Org", slug=str(uuid.uuid4()))
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Admissions", code=str(uuid.uuid4())[:8], branch=branch)
    queue = Queue(name="Admissions", prefix="A", service=service)
    customer = User(full_name="Customer", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    entry = QueueEntry(queue=queue, customer=customer, queue_number=1)
    db_session.add_all([organization, entry])
    db_session.flush()
    service_layer = NotificationService(db_session)
    paused_event = uuid.uuid4()
    resumed_event = uuid.uuid4()

    service_layer.queue_status(queue.id, "paused", paused_event)
    service_layer.queue_status(queue.id, "paused", paused_event)
    service_layer.queue_status(queue.id, "resumed", resumed_event)
    db_session.commit()

    notices = list(
        db_session.scalars(
            select(Notification).where(Notification.user_id == customer.id)
        )
    )
    assert {notice.type for notice in notices} == {
        NotificationType.QUEUE_PAUSED,
        NotificationType.QUEUE_RESUMED,
    }


def test_disabled_preferences_do_not_create_notifications(db_session: Session) -> None:
    organization = Organization(name="Preference Org", slug=str(uuid.uuid4()))
    branch = Branch(name="Main", organization=organization)
    service = Service(name="Admissions", code=str(uuid.uuid4())[:8], branch=branch)
    queue = Queue(name="Admissions", prefix="A", service=service)
    customer = User(full_name="Customer", email=f"{uuid.uuid4()}@example.com", password_hash="hash")
    entry = QueueEntry(queue=queue, customer=customer, queue_number=1)
    db_session.add_all([organization, entry])
    db_session.flush()
    db_session.add(NotificationPreference(user_id=customer.id, joined=False))

    NotificationService(db_session).for_entry(entry, "joined")
    db_session.commit()

    assert db_session.scalar(
        select(Notification.id).where(Notification.user_id == customer.id)
    ) is None
