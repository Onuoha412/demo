from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import OutboxEvent
from ..models.entities import OutboxStatus
from ..events import validate_event
from .time_engine import utc_now


def enqueue(
    session: Session,
    *,
    event_type: str,
    payload: dict[str, Any],
    queue_id: UUID | None = None,
    version: int = 1,
    idempotency_key: str | None = None,
) -> OutboxEvent:
    validate_event(event_type, payload, version)
    if idempotency_key is not None:
        existing = session.scalar(
            select(OutboxEvent).where(OutboxEvent.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
    sequence_filter = (
        OutboxEvent.queue_id == queue_id
        if queue_id is not None
        else OutboxEvent.queue_id.is_(None)
    )
    last_sequence = session.scalar(
        select(func.max(OutboxEvent.sequence_number))
        .where(sequence_filter)
        .with_for_update()
    ) or 0
    event = OutboxEvent(
        queue_id=queue_id,
        event_type=event_type,
        event_version=version,
        payload=payload,
        sequence_number=last_sequence + 1,
        idempotency_key=idempotency_key,
    )
    session.add(event)
    return event


def claim(session: Session, *, lease_seconds: int = 60) -> OutboxEvent | None:
    now = utc_now()
    stale_before = now - timedelta(seconds=lease_seconds)
    event = session.scalar(
        select(OutboxEvent)
        .where(
            OutboxEvent.available_at <= now,
            (
                (OutboxEvent.status == OutboxStatus.PENDING)
                | (
                    (OutboxEvent.status == OutboxStatus.PROCESSING)
                    & (OutboxEvent.locked_at < stale_before)
                )
            ),
        )
        .order_by(OutboxEvent.id)
        .limit(1)
    )
    if event is None:
        return None
    changed = session.execute(
        update(OutboxEvent)
        .where(
            OutboxEvent.id == event.id,
            (
                (OutboxEvent.status == OutboxStatus.PENDING)
                | (
                    (OutboxEvent.status == OutboxStatus.PROCESSING)
                    & (OutboxEvent.locked_at < stale_before)
                )
            ),
        )
        .values(
            status=OutboxStatus.PROCESSING,
            attempts=OutboxEvent.attempts + 1,
            locked_at=now,
        )
    )
    if changed.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    session.refresh(event)
    return event


def mark_published(session: Session, event_id: UUID) -> None:
    session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == event_id)
        .values(status=OutboxStatus.PUBLISHED, published_at=utc_now(), last_error=None)
    )
    session.commit()


def mark_failed(
    session: Session,
    event_id: UUID,
    error: str,
    *,
    max_attempts: int = 8,
) -> None:
    event = session.get(OutboxEvent, event_id)
    if event is None:
        return
    event.status = (
        OutboxStatus.DEAD if event.attempts >= max_attempts else OutboxStatus.PENDING
    )
    event.available_at = utc_now() + timedelta(seconds=min(300, 2 ** event.attempts))
    event.last_error = error[:2000]
    event.locked_at = None
    session.commit()


def replay(
    session: Session,
    *,
    queue_id: UUID | None,
    after_sequence: int,
    limit: int = 500,
) -> tuple[list[dict[str, Any]], bool]:
    """Return ordered events after a client cursor and whether replay is complete."""
    queue_filter = (
        OutboxEvent.queue_id == queue_id
        if queue_id is not None
        else OutboxEvent.queue_id.is_(None)
    )
    events = list(
        session.scalars(
            select(OutboxEvent)
            .where(
                queue_filter,
                OutboxEvent.sequence_number > after_sequence,
                OutboxEvent.status != OutboxStatus.DEAD,
            )
            .order_by(OutboxEvent.sequence_number)
            .limit(limit + 1)
        )
    )
    complete = len(events) <= limit and (
        not events
        or events[0].sequence_number == after_sequence + 1
    )
    return [
        {
            "event_id": str(event.id),
            "event_version": event.event_version,
            "event_sequence": event.sequence_number,
            "event": event.event_type,
            "queue_id": str(event.queue_id),
            "data": event.payload,
        }
        for event in events[:limit]
    ], complete
