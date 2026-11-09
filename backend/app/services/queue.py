from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, aliased, joinedload

from ..models import (
    Counter,
    Queue,
    QueueEntry,
    QueueEvent,
    QueueRequest,
    QueueTransfer,
    User,
)
from ..models.entities import (
    CounterStatus,
    QueueEntryStatus,
    QueueEventType,
    QueueRequestStatus,
    QueueStatus,
)
from .queue_number import QueueNumberService
from .queue_position import QueuePositionService
from .realtime import realtime
from .notifications import NotificationService
from .audit import record_audit
from .outbox import enqueue as enqueue_outbox
from .time_engine import utc_now


class QueueService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.number_service = QueueNumberService()
        self.position_service = QueuePositionService()

    def _queue(self, queue_id: UUID, lock: bool = False) -> Queue:
        if lock and self.session.get_bind().dialect.name == "sqlite":
            self.session.execute(
                update(Queue)
                .where(Queue.id == queue_id)
                .values(current_number=Queue.current_number)
            )
        query = (
            select(Queue)
            .options(joinedload(Queue.service))
            .where(Queue.id == queue_id)
        )
        if lock:
            query = query.with_for_update(of=Queue)
        queue = self.session.scalar(query)
        if queue is None:
            raise HTTPException(status_code=404, detail="Queue not found")
        return queue

    def _entry(self, entry_id: UUID, lock: bool = False) -> QueueEntry:
        if lock and self.session.get_bind().dialect.name == "sqlite":
            self.session.execute(
                update(QueueEntry)
                .where(QueueEntry.id == entry_id)
                .values(status=QueueEntry.status)
            )
        query = (
            select(QueueEntry)
            .options(joinedload(QueueEntry.queue).joinedload(Queue.service))
            .where(QueueEntry.id == entry_id)
        )
        if lock:
            query = query.with_for_update(of=QueueEntry)
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
        enqueue_outbox(
            self.session,
            queue_id=queue.id,
            event_type=f"queue.{event.value}",
            payload={
                "queue_id": str(queue.id),
                "queue_entry_id": str(entry.id) if entry is not None else None,
                "event": event.value,
                "occurred_at": utc_now().isoformat(),
            },
        )
        return record

    def _counter(self, counter_id: UUID | None, entry: QueueEntry) -> Counter | None:
        if counter_id is None:
            return None
        if self.session.get_bind().dialect.name == "sqlite":
            self.session.execute(
                update(Counter)
                .where(Counter.id == counter_id)
                .values(status=Counter.status)
            )
        counter = self.session.scalar(
            select(Counter)
            .where(Counter.id == counter_id)
            .with_for_update()
        )
        if (
            counter is None
            or not counter.is_active
            or counter.status == CounterStatus.OFFLINE
        ):
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

    def _response(
        self,
        entry: QueueEntry,
        *,
        people_ahead: int | None = None,
        active_counters: int | None = None,
        average_service_minutes: int | None = None,
    ) -> dict:
        if people_ahead is None or active_counters is None:
            ahead, estimate = self.position_service.estimate(
                self.session, entry.queue, entry
            )
        else:
            ahead = people_ahead
            estimate = round(
                ahead
                * (
                    average_service_minutes
                    if average_service_minutes is not None
                    else entry.queue.service.average_service_minutes
                )
                / max(active_counters, 1)
            )
        return {
            "id": entry.id,
            "queue_id": entry.queue_id,
            "queue_prefix": entry.queue.prefix,
            "queue_number": entry.queue_number,
            "priority": entry.priority,
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
            "request_note": entry.request_note,
            "verified_at": entry.verified_at,
            "verified_by_user_id": entry.verified_by_user_id,
        }

    @staticmethod
    def _public_event_response(response: dict) -> dict:
        return {
            key: value
            for key, value in response.items()
            if key not in {"request_note", "verified_at", "verified_by_user_id"}
        }

    def join(
        self, queue_id: UUID, customer_id: UUID, request_note: str | None = None
    ) -> dict:
        queue = self._queue(queue_id, lock=True)
        existing_entry = self.session.scalar(
            select(QueueEntry)
            .options(
                joinedload(QueueEntry.queue).joinedload(Queue.service),
                joinedload(QueueEntry.counter),
            )
            .where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.customer_id == customer_id,
                QueueEntry.status.in_(
                    [
                        QueueEntryStatus.WAITING,
                        QueueEntryStatus.CALLED,
                        QueueEntryStatus.SERVING,
                    ]
                ),
            )
            .order_by(QueueEntry.queue_number)
            .limit(1)
            .with_for_update(of=QueueEntry)
        )
        if existing_entry is not None:
            return self._response(existing_entry)
        if queue.status != QueueStatus.OPEN:
            raise HTTPException(status_code=409, detail="Queue is not open")
        if queue.capacity_limit is not None:
            active_entries = self.session.scalar(
                select(func.count(QueueEntry.id)).where(
                    QueueEntry.queue_id == queue.id,
                    QueueEntry.status.in_(
                        [
                            QueueEntryStatus.WAITING,
                            QueueEntryStatus.CALLED,
                            QueueEntryStatus.SERVING,
                        ]
                    ),
                )
            ) or 0
            if active_entries >= queue.capacity_limit:
                raise HTTPException(status_code=409, detail="Queue has reached its capacity")
        if self.session.get(User, customer_id) is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        try:
            number = self.number_service.next_number(self.session, queue)
            entry = QueueEntry(
                queue_id=queue.id,
                customer_id=customer_id,
                queue_number=number,
                status=QueueEntryStatus.WAITING,
                request_note=request_note,
            )
            self.session.add(entry)
            self.session.flush()
            self._record(queue, entry, QueueEventType.JOINED)
            notifier = NotificationService(self.session)
            notifier.for_entry(entry, "joined")
            approaching_event = notifier.approaching(entry)
            self._commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(entry)
        response = self._response(entry)
        public_response = self._public_event_response(response)
        if approaching_event is not None:
            realtime.publish_nowait(
                queue.id,
                "QUEUE_APPROACHING",
                approaching_event["data"],
            )
        realtime.publish_nowait(queue.id, "CUSTOMER_JOINED", public_response)
        realtime.publish_nowait(queue.id, "QUEUE_UPDATED", public_response)
        return response

    def get_queue(self, queue_id: UUID, page: int, page_size: int) -> dict:
        if page < 1 or page_size < 1 or page_size > 100:
            raise HTTPException(status_code=422, detail="Invalid pagination parameters")
        queue = self._queue(queue_id)
        entry_order = [QueueEntry.queue_number]
        if queue.priority_enabled:
            entry_order.insert(0, QueueEntry.priority.desc())
        query = (
            select(QueueEntry)
            .options(joinedload(QueueEntry.counter))
            .where(QueueEntry.queue_id == queue.id)
            .order_by(*entry_order)
        )
        entries = list(self.session.scalars(query.offset((page - 1) * page_size).limit(page_size)))
        total = self.session.scalar(
            select(func.count(QueueEntry.id)).where(QueueEntry.queue_id == queue.id)
        ) or 0
        active = self.position_service.active_counter_count(self.session, queue)
        ahead_counts: dict[UUID, int] = {}
        if entries:
            earlier_entry = aliased(QueueEntry)
            ahead_condition = (
                or_(
                    earlier_entry.priority > QueueEntry.priority,
                    and_(
                        earlier_entry.priority == QueueEntry.priority,
                        earlier_entry.queue_number < QueueEntry.queue_number,
                    ),
                )
                if queue.priority_enabled
                else earlier_entry.queue_number < QueueEntry.queue_number
            )
            ahead_counts = dict(
                self.session.execute(
                    select(QueueEntry.id, func.count(earlier_entry.id))
                    .outerjoin(
                        earlier_entry,
                        and_(
                            earlier_entry.queue_id == QueueEntry.queue_id,
                            earlier_entry.status == QueueEntryStatus.WAITING,
                            ahead_condition,
                        ),
                    )
                    .where(QueueEntry.id.in_([entry.id for entry in entries]))
                    .group_by(QueueEntry.id)
                ).all()
            )
        return {
            "id": queue.id,
            "queue_id": queue.id,
            "name": queue.name,
            "prefix": queue.prefix,
            "status": queue.status,
            "current_number": queue.current_number,
            "capacity_limit": queue.capacity_limit,
            "priority_enabled": queue.priority_enabled,
            "average_service_minutes": queue.service.average_service_minutes,
            "active_counters": active,
            "total_entries": total,
            "page": page,
            "page_size": page_size,
            "entries": [
                self._response(
                    entry,
                    people_ahead=ahead_counts.get(entry.id, 0),
                    active_counters=active,
                    average_service_minutes=queue.service.average_service_minutes,
                )
                for entry in entries
            ],
        }

    def position(self, queue_id: UUID, entry_id: UUID) -> dict:
        entry = self._entry(entry_id)
        if entry.queue_id != queue_id:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        response = self._response(entry)
        response["transferred_to_entry_id"] = self.session.scalar(
            select(QueueTransfer.target_entry_id).where(
                QueueTransfer.source_entry_id == entry.id
            )
        )
        return response

    def verify_request(self, entry_id: UUID, admin_id: UUID) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status not in (
            QueueEntryStatus.WAITING,
            QueueEntryStatus.CALLED,
            QueueEntryStatus.SERVING,
        ):
            raise HTTPException(
                status_code=409,
                detail="Only active queue requests can be verified",
            )
        if entry.verified_at is None:
            entry.verified_at = datetime.now(timezone.utc)
            entry.verified_by_user_id = admin_id
            self._commit()
            self.session.refresh(entry)
        response = self._response(entry)
        public_response = self._public_event_response(response)
        realtime.publish_nowait(entry.queue_id, "QUEUE_UPDATED", public_response)
        return response

    def approve_queue_request(
        self, request_id: UUID, queue_id: UUID, reviewer_id: UUID
    ) -> QueueRequest:
        if self.session.get_bind().dialect.name == "sqlite":
            self.session.execute(
                update(QueueRequest)
                .where(QueueRequest.id == request_id)
                .values(status=QueueRequest.status)
            )
        queue_request = self.session.scalar(
            select(QueueRequest)
            .where(QueueRequest.id == request_id)
            .with_for_update(of=QueueRequest)
        )
        if queue_request is None:
            raise HTTPException(status_code=404, detail="Queue request not found")
        if queue_request.status is not QueueRequestStatus.PENDING:
            raise HTTPException(
                status_code=409, detail="This queue request has already been reviewed"
            )

        queue = self._queue(queue_id, lock=True)
        if queue.status is not QueueStatus.OPEN:
            raise HTTPException(
                status_code=409, detail="The selected queue is not open"
            )
        if not queue.service.is_active or not queue.service.branch.is_active:
            raise HTTPException(
                status_code=409,
                detail="The selected queue is not available for new requests",
            )
        if queue.capacity_limit is not None:
            active_entries = self.session.scalar(
                select(func.count(QueueEntry.id)).where(
                    QueueEntry.queue_id == queue.id,
                    QueueEntry.status.in_(
                        [
                            QueueEntryStatus.WAITING,
                            QueueEntryStatus.CALLED,
                            QueueEntryStatus.SERVING,
                        ]
                    ),
                )
            ) or 0
            if active_entries >= queue.capacity_limit:
                raise HTTPException(
                    status_code=409, detail="Queue has reached its capacity"
                )
        if queue.service.branch_id != queue_request.branch_id:
            raise HTTPException(
                status_code=422,
                detail="Choose an open queue in the requested branch",
            )
        active_entry = self.session.scalar(
            select(QueueEntry.id).where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.customer_id == queue_request.customer_id,
                QueueEntry.status.in_(
                    [
                        QueueEntryStatus.WAITING,
                        QueueEntryStatus.CALLED,
                        QueueEntryStatus.SERVING,
                    ]
                ),
            )
        )
        if active_entry is not None:
            raise HTTPException(
                status_code=409,
                detail="This customer already has an active ticket in the selected queue",
            )
        number = self.number_service.next_number(self.session, queue)
        entry = QueueEntry(
            queue_id=queue.id,
            customer_id=queue_request.customer_id,
            queue_number=number,
            status=QueueEntryStatus.WAITING,
            request_note=queue_request.request_text,
        )
        self.session.add(entry)
        self.session.flush()
        now = datetime.now(timezone.utc)
        queue_request.status = QueueRequestStatus.APPROVED
        queue_request.assigned_queue = queue
        queue_request.queue_entry = entry
        queue_request.reviewed_by_user_id = reviewer_id
        queue_request.reviewed_at = now
        self._record(queue, entry, QueueEventType.JOINED)
        notifier = NotificationService(self.session)
        notifier.for_entry(entry, "joined")
        approaching_event = notifier.approaching(entry)
        self._commit()
        self.session.refresh(entry)
        self.session.refresh(queue_request)

        response = self._response(entry)
        public_response = self._public_event_response(response)
        if approaching_event is not None:
            realtime.publish_nowait(
                queue.id,
                "QUEUE_APPROACHING",
                approaching_event["data"],
            )
        realtime.publish_nowait(queue.id, "CUSTOMER_JOINED", public_response)
        realtime.publish_nowait(queue.id, "QUEUE_UPDATED", public_response)
        return queue_request

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
        approaching_events = notifier.approaching_queue(entry.queue_id)
        self.session.commit()
        response = self._response(entry)
        for event in approaching_events:
            realtime.publish_nowait(
                event["queue_id"], "QUEUE_APPROACHING", event["data"]
            )
        public_response = self._public_event_response(response)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_CALLED", public_response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", public_response)
        return response

    def next(self, queue_id: UUID, counter_id: UUID | None = None) -> dict:
        queue = self._queue(queue_id, lock=True)
        if queue.status != QueueStatus.OPEN:
            raise HTTPException(status_code=409, detail="Queue is not open")
        entry_order = [QueueEntry.queue_number]
        if queue.priority_enabled:
            entry_order.insert(0, QueueEntry.priority.desc())
        entry = self.session.scalar(
            select(QueueEntry)
            .where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.status == QueueEntryStatus.WAITING,
            )
            .order_by(*entry_order)
            .with_for_update(of=QueueEntry, skip_locked=True)
        )
        if entry is None:
            raise HTTPException(status_code=404, detail="No waiting customers")
        return self.call(entry.id, counter_id)

    def _call_next_waiting(self, queue_id: UUID, counter_id: UUID | None) -> dict | None:
        queue = self._queue(queue_id, lock=True)
        if queue.status != QueueStatus.OPEN:
            return None
        entry_order = [QueueEntry.queue_number]
        if queue.priority_enabled:
            entry_order.insert(0, QueueEntry.priority.desc())
        entry = self.session.scalar(
            select(QueueEntry)
            .where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.status == QueueEntryStatus.WAITING,
            )
            .order_by(*entry_order)
            .with_for_update(of=QueueEntry, skip_locked=True)
        )
        if entry is None:
            return None
        return self.call(entry.id, counter_id)

    def set_priority(
        self, entry_id: UUID, priority: int, actor_user_id: UUID
    ) -> dict:
        entry = self._entry(entry_id, lock=True)
        if not entry.queue.priority_enabled:
            raise HTTPException(
                status_code=409,
                detail="Priority handling is not enabled for this queue",
            )
        if entry.status is not QueueEntryStatus.WAITING:
            raise HTTPException(
                status_code=409,
                detail="Priority can only be changed for waiting customers",
            )
        previous_priority = entry.priority
        entry.priority = priority
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="queue_entry.priority_changed",
            target_type="queue_entry",
            target_id=entry.id,
            details={"from": previous_priority, "to": priority},
        )
        self._commit()
        response = self._response(entry)
        public_response = self._public_event_response(response)
        realtime.publish_nowait(
            entry.queue_id, "QUEUE_PRIORITY_CHANGED", public_response
        )
        realtime.publish_nowait(entry.queue_id, "QUEUE_UPDATED", public_response)
        return response

    def transfer(
        self, entry_id: UUID, target_queue_id: UUID, actor_user_id: UUID
    ) -> dict:
        source = self._entry(entry_id, lock=True)
        if source.status is not QueueEntryStatus.WAITING:
            raise HTTPException(
                status_code=409, detail="Only waiting customers can be transferred"
            )
        if source.queue_id == target_queue_id:
            raise HTTPException(
                status_code=422, detail="Choose a different destination queue"
            )
        target_queue = self._queue(target_queue_id, lock=True)
        if target_queue.status is not QueueStatus.OPEN:
            raise HTTPException(
                status_code=409, detail="The destination queue is not open"
            )
        if not target_queue.service.is_active or not target_queue.service.branch.is_active:
            raise HTTPException(
                status_code=409, detail="The destination queue is not available"
            )

        active_entries = self.session.scalar(
            select(func.count(QueueEntry.id)).where(
                QueueEntry.queue_id == target_queue.id,
                QueueEntry.status.in_(
                    [
                        QueueEntryStatus.WAITING,
                        QueueEntryStatus.CALLED,
                        QueueEntryStatus.SERVING,
                    ]
                ),
            )
        ) or 0
        if (
            target_queue.capacity_limit is not None
            and active_entries >= target_queue.capacity_limit
        ):
            raise HTTPException(
                status_code=409, detail="The destination queue has reached capacity"
            )
        existing = self.session.scalar(
            select(QueueEntry.id).where(
                QueueEntry.queue_id == target_queue.id,
                QueueEntry.customer_id == source.customer_id,
                QueueEntry.status.in_(
                    [
                        QueueEntryStatus.WAITING,
                        QueueEntryStatus.CALLED,
                        QueueEntryStatus.SERVING,
                    ]
                ),
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="This customer already has an active entry in the destination queue",
            )

        source_queue_id = source.queue_id
        source_queue_number = source.queue_number
        target_number = self.number_service.next_number(self.session, target_queue)
        target_entry = QueueEntry(
            queue_id=target_queue.id,
            customer_id=source.customer_id,
            queue_number=target_number,
            status=QueueEntryStatus.WAITING,
            priority=source.priority if target_queue.priority_enabled else 0,
            request_note=source.request_note,
        )
        source.status = QueueEntryStatus.CANCELLED
        self.session.add(target_entry)
        self._record(source.queue, source, QueueEventType.CANCELLED)
        self.session.flush()
        transfer = QueueTransfer(
            source_entry_id=source.id,
            target_entry_id=target_entry.id,
            source_queue_id=source_queue_id,
            target_queue_id=target_queue.id,
            source_queue_number=source_queue_number,
            target_queue_number=target_number,
            actor_user_id=actor_user_id,
        )
        self.session.add(transfer)
        self.session.flush()
        record_audit(
            self.session,
            actor_user_id=actor_user_id,
            action="queue_entry.transferred",
            target_type="queue_transfer",
            target_id=transfer.id,
            details={
                "source_entry_id": str(source.id),
                "target_entry_id": str(target_entry.id),
                "source_queue_id": str(source_queue_id),
                "target_queue_id": str(target_queue.id),
                "source_queue_number": source_queue_number,
                "target_queue_number": target_number,
            },
        )
        self._record(target_queue, target_entry, QueueEventType.JOINED)
        notifier = NotificationService(self.session)
        notifier.for_entry(target_entry, "joined")
        target_approaching = notifier.approaching(target_entry)
        self._commit()
        self.session.refresh(target_entry)

        source_event = {
            "entry_id": str(source.id),
            "transferred_to_entry_id": str(target_entry.id),
            "target_queue_id": str(target_queue.id),
            "target_queue_number": target_number,
        }
        realtime.publish_nowait(source_queue_id, "CUSTOMER_TRANSFERRED", source_event)
        target_response = self._response(target_entry)
        target_public_response = self._public_event_response(target_response)
        if target_approaching is not None:
            realtime.publish_nowait(
                target_queue.id,
                "QUEUE_APPROACHING",
                target_approaching["data"],
            )
        realtime.publish_nowait(
            target_queue.id, "CUSTOMER_JOINED", target_public_response
        )
        realtime.publish_nowait(
            target_queue.id, "QUEUE_UPDATED", target_public_response
        )
        return target_response

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
        public_response = self._public_event_response(response)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_STARTED", public_response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", public_response)
        return response

    def complete(self, entry_id: UUID) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status not in (QueueEntryStatus.CALLED, QueueEntryStatus.SERVING):
            raise HTTPException(
                status_code=409,
                detail="Only called or serving customers can be completed",
            )
        queue_id = entry.queue_id
        counter_id = entry.counter_id
        entry.status = QueueEntryStatus.COMPLETED
        entry.completed_at = datetime.now(timezone.utc)
        if counter_id:
            counter = self.session.get(Counter, counter_id)
            if counter:
                counter.status = CounterStatus.AVAILABLE
        self._record(entry.queue, entry, QueueEventType.COMPLETED)
        self._commit()
        NotificationService(self.session).for_entry(entry, "completed")
        self.session.commit()
        response = self._response(entry)
        public_response = self._public_event_response(response)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_COMPLETED", public_response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", public_response)
        self._call_next_waiting(queue_id, counter_id)
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
        public_response = self._public_event_response(response)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_SKIPPED", public_response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", public_response)
        self._call_next_waiting(entry.queue_id, entry.counter_id)
        return response

    def cancel(self, entry_id: UUID) -> dict:
        entry = self._entry(entry_id, lock=True)
        if entry.status != QueueEntryStatus.WAITING:
            raise HTTPException(status_code=409, detail="Only waiting customers can be cancelled")
        entry.status = QueueEntryStatus.CANCELLED
        self._record(entry.queue, entry, QueueEventType.CANCELLED)
        self._commit()
        notifier = NotificationService(self.session)
        approaching_events = notifier.approaching_queue(entry.queue_id)
        self.session.commit()
        response = self._response(entry)
        for event in approaching_events:
            realtime.publish_nowait(
                event["queue_id"], "QUEUE_APPROACHING", event["data"]
            )
        public_response = self._public_event_response(response)
        realtime.publish_nowait(entry.queue.id, "CUSTOMER_CANCELLED", public_response)
        realtime.publish_nowait(entry.queue.id, "QUEUE_UPDATED", public_response)
        return response

    def set_status(self, queue_id: UUID, status: QueueStatus) -> dict:
        queue = self._queue(queue_id, lock=True)
        if queue.status == QueueStatus.CLOSED:
            raise HTTPException(status_code=409, detail="Closed queues cannot be changed")
        if queue.status == status:
            return {"id": queue.id, "status": queue.status}
        queue.status = status
        event_details = {
            QueueStatus.PAUSED: (
                QueueEventType.PAUSED,
                "QUEUE_PAUSED",
                "paused",
            ),
            QueueStatus.OPEN: (
                QueueEventType.RESUMED,
                "QUEUE_RESUMED",
                "resumed",
            ),
            QueueStatus.CLOSED: (
                QueueEventType.CLOSED,
                "QUEUE_CLOSED",
                "closed",
            ),
        }
        event_type, event, notification_status = event_details[status]
        queue_event = self._record(
            queue,
            None,
            event_type,
        )
        self._commit()
        notifier = NotificationService(self.session)
        notifier.queue_status(
            queue.id,
            notification_status,
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
