from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import Counter, Queue, QueueEntry, QueueEvent, Service, User
from ..models.entities import (
    CounterStatus,
    QueueEntryStatus,
    QueueEventType,
    QueueStatus,
)
from .queue_number import QueueNumberService
from .queue_position import QueuePositionService
from .realtime import realtime
from .notifications import NotificationService


class QueueService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.number_service = QueueNumberService()
        self.position_service = QueuePositionService()

    def _queue(self, queue_id: UUID, lock: bool = False) -> Queue:
        query = (
            select(Queue)
            .options(joinedload(Queue.service))
            .where(Queue.id == queue_id)
        )
        if lock:
            query = query.with_for_update()
        queue = self.session.scalar(query)
        if queue is None:
            raise HTTPException(status_code=404, detail="Queue not found")
        return queue

    def _entry(self, entry_id: UUID, lock: bool = False) -> QueueEntry:
        query = (
            select(QueueEntry)
            .options(joinedload(QueueEntry.queue).joinedload(Queue.service))
            .where(QueueEntry.id == entry_id)
        )
        if lock:
            query = query.with_for_update()
        entry = self.session.scalar(query)
        if entry is None:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        return entry

    def _record(self, queue: Queue, entry: QueueEntry | None, event: QueueEventType) -> QueueEvent:
        record = QueueEvent(
            queue_id=queue.id,
            queue_entry_id=entry.id if entry else None,
            event_type=event,
            metadata_={},
        )
        self.session.add(record)
        return record

    def _counter(self, counter_id: UUID | None, entry: QueueEntry) -> Counter | None:
        if counter_id is None:
            return None
        counter = self.session.scalar(
            select(Counter)
            .where(Counter.id == counter_id)
            .with_for_update()
        )
        if counter is None or not counter.is_active:
            raise HTTPException(status_code=400, detail="Counter is not active")
        if counter.branch_id != entry.queue.service.branch_id:
            raise HTTPException(status_code=400, detail="Counter belongs to another branch")
        active = self.session.scalar(
            select(QueueEntry.id).where(
                QueueEntry.counter_id == counter.id,
                QueueEntry.status.in_(
                    [QueueEntryStatus.CALLED, QueueEntryStatus.SERVING]
                ),
                QueueEntry.id != entry.id,
            ).with_for_update()
        )
        if active is not None:
            raise HTTPException(status_code=409, detail="Counter is serving another customer")
        return counter

    def _commit(self) -> None:
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _response(self, entry: QueueEntry) -> dict:
        ahead, estimate = self.position_service.estimate(
            self.session, entry.queue, entry
        )
        return {
            "id": entry.id,
            "queue_id": entry.queue_id,
            "queue_number": entry.queue_number,
            "status": entry.status,
            "people_ahead": ahead,
            "estimated_wait_minutes": estimate,
            "counter_id": entry.counter_id,
            "counter": (
                {
                    "id": entry.counter.id,
                    "name": entry.counter.name,
                    "number": entry.counter.number,
                    "status": entry.counter.status.value,
                }
                if entry.counter is not None
                else None
            ),
            "joined_at": entry.joined_at,
            "called_at": entry.called_at,
            "service_started_at": entry.service_started_at,
            "completed_at": entry.completed_at,
        }

    def join(self, queue_id: UUID, customer_id: UUID) -> dict:
        queue = self._queue(queue_id, lock=True)
        if queue.status != QueueStatus.OPEN:
            raise HTTPException(status_code=409, detail="Queue is not open")
        if self.session.get(User, customer_id) is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        number = self.number_service.next_number(self.session, queue)
        entry = QueueEntry(
            queue_id=queue.id,
            customer_id=customer_id,
            queue_number=number,
            status=QueueEntryStatus.WAITING,
        )
        self.session.add(entry)
        self.session.flush()
        self._record(queue, entry, QueueEventType.JOINED)
        self._commit()
        self.session.refresh(entry)
        NotificationService(self.session).for_entry(entry, "joined")
        NotificationService(self.session).approaching(entry)
        self.session.commit()
        response = self._response(entry)
        realtime.publish_nowait(queue.id, "CUSTOMER_JOINED", response)
        realtime.publish_nowait(queue.id, "QUEUE_UPDATED", response)
        return response

    def get_queue(self, queue_id: UUID, page: int, page_size: int) -> dict:
        if page < 1 or page_size < 1 or page_size > 100:
            raise HTTPException(status_code=422, detail="Invalid pagination parameters")
        queue = self._queue(queue_id)
        query = select(QueueEntry).where(QueueEntry.queue_id == queue.id).order_by(QueueEntry.queue_number)
        entries = list(self.session.scalars(query.offset((page - 1) * page_size).limit(page_size)))
        total = self.session.scalar(
            select(func.count(QueueEntry.id)).where(QueueEntry.queue_id == queue.id)
        ) or 0
        active = self.position_service.active_counter_count(self.session, queue)
        return {
            "id": queue.id,
            "queue_id": queue.id,
            "name": queue.name,
            "prefix": queue.prefix,
            "status": queue.status,
            "current_number": queue.current_number,
            "average_service_minutes": queue.service.average_service_minutes,
            "active_counters": active,
            "total_entries": total,
            "page": page,
            "page_size": page_size,
            "entries": [self._response(entry) for entry in entries],
        }

    def position(self, queue_id: UUID, entry_id: UUID) -> dict:
        entry = self._entry(entry_id)
        if entry.queue_id != queue_id:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        return self._response(entry)

    def call(self, entry_id: UUID, counter_id: UUID | None = None) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status != QueueEntryStatus.WAITING:
            raise HTTPException(status_code=409, detail="Only waiting customers can be called")
        counter = self._counter(counter_id, entry)
        entry.status = QueueEntryStatus.CALLED
        entry.called_at = datetime.now(timezone.utc)
        if counter:
            entry.counter_id = counter.id
        self._record(entry.queue, entry, QueueEventType.CALLED)
        self._commit()
        notifier = NotificationService(self.session)
        notifier.for_entry(entry, "called")
        notifier.approaching_queue(entry.queue_id)
        self.session.commit()
        response = self._response(entry)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_CALLED", response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", response)
        return response

    def next(self, queue_id: UUID, counter_id: UUID | None = None) -> dict:
        queue = self._queue(queue_id, lock=True)
        if queue.status != QueueStatus.OPEN:
            raise HTTPException(status_code=409, detail="Queue is not open")
        entry = self.session.scalar(
            select(QueueEntry)
            .where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.status == QueueEntryStatus.WAITING,
            )
            .order_by(QueueEntry.queue_number)
            .with_for_update(skip_locked=True)
        )
        if entry is None:
            raise HTTPException(status_code=404, detail="No waiting customers")
        return self.call(entry.id, counter_id)

    def start(self, entry_id: UUID, counter_id: UUID | None = None) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status != QueueEntryStatus.CALLED:
            raise HTTPException(status_code=409, detail="Only called customers can start service")
        counter = self._counter(counter_id or entry.counter_id, entry)
        if counter is None:
            raise HTTPException(status_code=400, detail="A counter is required to start service")
        entry.counter_id = counter.id
        entry.status = QueueEntryStatus.SERVING
        entry.service_started_at = datetime.now(timezone.utc)
        counter.status = CounterStatus.BUSY
        self._record(entry.queue, entry, QueueEventType.SERVING)
        self._commit()
        response = self._response(entry)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_STARTED", response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", response)
        return response

    def complete(self, entry_id: UUID) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status != QueueEntryStatus.SERVING:
            raise HTTPException(status_code=409, detail="Only serving customers can be completed")
        entry.status = QueueEntryStatus.COMPLETED
        entry.completed_at = datetime.now(timezone.utc)
        if entry.counter_id:
            counter = self.session.get(Counter, entry.counter_id)
            if counter:
                counter.status = CounterStatus.AVAILABLE
        self._record(entry.queue, entry, QueueEventType.COMPLETED)
        self._commit()
        NotificationService(self.session).for_entry(entry, "completed")
        self.session.commit()
        response = self._response(entry)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_COMPLETED", response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", response)
        return response

    def skip(self, entry_id: UUID) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status != QueueEntryStatus.CALLED:
            raise HTTPException(status_code=409, detail="Only called customers can be skipped")
        entry.status = QueueEntryStatus.SKIPPED
        if entry.counter_id:
            counter = self.session.get(Counter, entry.counter_id)
            if counter:
                counter.status = CounterStatus.AVAILABLE
        self._record(entry.queue, entry, QueueEventType.SKIPPED)
        self._commit()
        response = self._response(entry)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_SKIPPED", response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", response)
        return response

    def cancel(self, entry_id: UUID) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status != QueueEntryStatus.WAITING:
            raise HTTPException(status_code=409, detail="Only waiting customers can be cancelled")
        entry.status = QueueEntryStatus.CANCELLED
        self._record(entry.queue, entry, QueueEventType.CANCELLED)
        self._commit()
        notifier = NotificationService(self.session)
        notifier.approaching_queue(entry.queue_id)
        self.session.commit()
        response = self._response(entry)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_CANCELLED", response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", response)
        return response

    def set_status(self, queue_id: UUID, status: QueueStatus) -> dict:
        queue = self._queue(queue_id, lock=True)
        if queue.status == QueueStatus.CLOSED:
            raise HTTPException(status_code=409, detail="Closed queues cannot be changed")
        if queue.status == status:
            return {"id": queue.id, "status": queue.status}
        queue.status = status
        queue_event = self._record(
            queue,
            None,
            QueueEventType.PAUSED if status == QueueStatus.PAUSED else QueueEventType.RESUMED,
        )
        self._commit()
        event = "QUEUE_PAUSED" if status == QueueStatus.PAUSED else "QUEUE_RESUMED"
        notifier = NotificationService(self.session)
        notifier.queue_status(
            queue.id,
            "paused" if status == QueueStatus.PAUSED else "resumed",
            queue_event.id,
        )
        self.session.commit()
        response = {"id": queue.id, "status": queue.status}
        realtime.publish_nowait(
            queue.id,
            event,
            {**response, "event_id": str(queue_event.id)},
        )
        realtime.publish_nowait(queue.id, "QUEUE_UPDATED", response)
        return response
