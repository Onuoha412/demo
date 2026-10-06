from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Counter, Queue, QueueEntry, Service
from ..models.entities import CounterStatus, QueueEntryStatus


class QueuePositionService:
    def active_counter_count(self, session: Session, queue: Queue) -> int:
        return session.scalar(
            select(func.count(Counter.id))
            .join(Service, Service.branch_id == Counter.branch_id)
            .where(
                Service.id == queue.service_id,
                Counter.is_active.is_(True),
                Counter.status != CounterStatus.OFFLINE,
            )
        ) or 0

    def people_ahead(self, session: Session, entry: QueueEntry) -> int:
        return session.scalar(
            select(func.count(QueueEntry.id)).where(
                QueueEntry.queue_id == entry.queue_id,
                QueueEntry.status == QueueEntryStatus.WAITING,
                QueueEntry.queue_number < entry.queue_number,
            )
        ) or 0

    def estimate(self, session: Session, queue: Queue, entry: QueueEntry) -> tuple[int, int]:
        ahead = self.people_ahead(session, entry)
        active_counters = max(self.active_counter_count(session, queue), 1)
        estimate = round(
            ahead * queue.service.average_service_minutes / active_counters
        )
        return ahead, estimate
