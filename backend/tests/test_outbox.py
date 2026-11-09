from datetime import timedelta
import uuid

from app.models import OutboxEvent
from sqlalchemy import delete
from app.models.entities import OutboxStatus
from app.services.outbox import claim, enqueue, mark_failed, mark_published, replay
from app.services.time_engine import utc_now


def test_outbox_claim_publish_and_retry(db_session) -> None:
    db_session.execute(delete(OutboxEvent))
    db_session.commit()
    event = enqueue(
        db_session,
        event_type="ticket.created",
        payload={"ticket": "A1"},
        version=2,
    )
    db_session.commit()

    claimed = claim(db_session)

    assert claimed is not None
    assert claimed.id == event.id
    assert claimed.status is OutboxStatus.PROCESSING
    assert claimed.attempts == 1

    mark_failed(db_session, claimed.id, "temporary failure")
    failed = db_session.get(OutboxEvent, claimed.id)
    assert failed is not None
    assert failed.status is OutboxStatus.PENDING
    assert failed.last_error == "temporary failure"

    failed.available_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    claimed_again = claim(db_session)
    assert claimed_again is not None
    mark_published(db_session, claimed_again.id)
    assert db_session.get(OutboxEvent, event.id).status is OutboxStatus.PUBLISHED


def test_outbox_idempotency_and_ordered_replay(db_session) -> None:
    db_session.execute(delete(OutboxEvent))
    db_session.commit()
    first = enqueue(
        db_session,
        event_type="ticket.created",
        payload={"ticket": "one"},
        idempotency_key="join:one",
    )
    duplicate = enqueue(
        db_session,
        event_type="ticket.created",
        payload={"ticket": "one"},
        idempotency_key="join:one",
    )
    second = enqueue(
        db_session,
        event_type="ticket.called",
        payload={"ticket": "one"},
    )
    db_session.commit()

    assert duplicate.id == first.id
    events, complete = replay(db_session, queue_id=None, after_sequence=0)
    assert complete
    assert [event["event"] for event in events] == ["ticket.created", "ticket.called"]
    assert events[0]["event_sequence"] < events[1]["event_sequence"]
    assert second.sequence_number == events[1]["event_sequence"]
