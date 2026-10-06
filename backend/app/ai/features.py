"""Feature extraction for the queue wait-time model.

The extractor deliberately returns a small, serialisable feature object.  A
different model can therefore be introduced without changing the API or the
database layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Counter, Queue, QueueEntry
from ..models.entities import CounterStatus, QueueEntryStatus


@dataclass(frozen=True)
class WaitTimeFeatures:
    people_ahead: int
    queue_length: int
    average_service_minutes: float
    active_counters: int
    recent_completed_durations: tuple[float, ...]
    service_type: str
    hour: int
    day_of_week: int
    processing_rate_per_hour: float


def _duration_minutes(entry: QueueEntry) -> float | None:
    if entry.service_started_at is None or entry.completed_at is None:
        return None
    seconds = (entry.completed_at - entry.service_started_at).total_seconds()
    return seconds / 60 if seconds > 0 else None


class WaitTimeFeatureExtractor:
    """Build features from PostgreSQL queue and historical completion records."""

    def __init__(self, history_limit: int = 200) -> None:
        self.history_limit = max(1, history_limit)

    def extract(self, session: Session, entry: QueueEntry) -> WaitTimeFeatures:
        queue = entry.queue
        service = queue.service
        now = datetime.now(timezone.utc)

        queue_length = session.scalar(
            select(func.count(QueueEntry.id)).where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.status == QueueEntryStatus.WAITING,
            )
        ) or 0
        ahead = session.scalar(
            select(func.count(QueueEntry.id)).where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.status == QueueEntryStatus.WAITING,
                QueueEntry.queue_number < entry.queue_number,
            )
        ) or 0
        if entry.status != QueueEntryStatus.WAITING:
            ahead = 0
        active = session.scalar(
            select(func.count(Counter.id))
            .where(
                Counter.branch_id == service.branch_id,
                Counter.is_active.is_(True),
                Counter.status != CounterStatus.OFFLINE,
            )
        ) or 0

        history = list(
            session.scalars(
                select(QueueEntry)
                .join(Queue, Queue.id == QueueEntry.queue_id)
                .where(
                    Queue.service_id == service.id,
                    QueueEntry.status == QueueEntryStatus.COMPLETED,
                    QueueEntry.service_started_at.is_not(None),
                    QueueEntry.completed_at.is_not(None),
                )
                .order_by(QueueEntry.completed_at.desc())
                .limit(self.history_limit)
            )
        )
        durations = tuple(
            duration for item in history if (duration := _duration_minutes(item)) is not None
        )
        recent = [item for item in history if item.completed_at and item.completed_at >= now - timedelta(hours=1)]
        recent_completed = sum(1 for item in recent if _duration_minutes(item) is not None)
        return WaitTimeFeatures(
            people_ahead=max(0, int(ahead)),
            queue_length=max(0, int(queue_length)),
            average_service_minutes=max(0.0, float(service.average_service_minutes or 0)),
            active_counters=max(0, int(active)),
            recent_completed_durations=durations,
            service_type=service.code or service.name,
            hour=now.hour,
            day_of_week=now.weekday(),
            processing_rate_per_hour=float(recent_completed),
        )
