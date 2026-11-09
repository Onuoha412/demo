"""Versioned internal event contracts.

Events are validated before entering the transactional outbox. The outbox remains
the durable source of truth; this module only defines the wire contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QueueEventPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    queue_id: UUID
    queue_entry_id: UUID | None = None
    event: str


class DomainEventPayload(BaseModel):
    """Base contract for events stored in the durable outbox."""

    model_config = ConfigDict(extra="allow")

    occurred_at: datetime | None = None


class VersionedEvent(BaseModel):
    event_type: str = Field(min_length=1, max_length=100)
    event_version: int = Field(ge=1)
    payload: dict[str, Any]
    schema_name: str = "queueless.event"


EVENT_TYPES: ClassVar[frozenset[str]] = frozenset(
    {
        "customer.registered",
        "customer.joined_queue",
        "customer.cancelled_ticket",
        "ticket.created",
        "ticket.called",
        "ticket.serving",
        "ticket.completed",
        "ticket.skipped",
        "queue.position_changed",
        "queue.wait_time_updated",
        "queue.opened",
        "queue.paused",
        "queue.closed",
        "appointment.created",
        "appointment.reminder_due",
        "notification.created",
        "feedback.submitted",
    }
)


def validate_event(event_type: str, payload: dict[str, Any], version: int) -> VersionedEvent:
    """Validate the currently supported event envelope before persistence."""
    if version < 1:
        raise ValueError(f"Unsupported event version: {version}")
    if event_type not in EVENT_TYPES and not event_type.startswith("queue."):
        raise ValueError(f"Unsupported event type: {event_type}")
    if event_type.startswith("queue."):
        QueueEventPayload.model_validate(payload)
    else:
        DomainEventPayload.model_validate(payload)
    return VersionedEvent(
        event_type=event_type,
        event_version=version,
        payload=payload,
    )
