from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Notification, NotificationPreference, QueueEntry
from ..models.entities import NotificationType, QueueEntryStatus


class NotificationService:
    """Creates durable, idempotent customer notifications."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _enabled(self, user_id: UUID, field: str) -> bool:
        preferences = self.session.get(NotificationPreference, user_id)
        return bool(preferences is None or (preferences.enabled and getattr(preferences, field)))

    def create(
        self,
        user_id: UUID,
        event_key: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        queue_entry_id: UUID | None = None,
        preference: str = "queue_updates",
    ) -> Notification | None:
        notification, _ = self._create_once(
            user_id,
            event_key,
            notification_type,
            title,
            message,
            queue_entry_id,
            preference,
        )
        return notification

    def _create_once(
        self,
        user_id: UUID,
        event_key: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        queue_entry_id: UUID | None = None,
        preference: str = "queue_updates",
    ) -> tuple[Notification | None, bool]:
        if not self._enabled(user_id, preference):
            return None, False
        existing = self.session.scalar(
            select(Notification).where(
                Notification.user_id == user_id, Notification.event_key == event_key
            )
        )
        if existing:
            return existing, False
        notification = Notification(
            user_id=user_id,
            queue_entry_id=queue_entry_id,
            event_key=event_key,
            type=notification_type,
            title=title,
            message=message,
        )
        try:
            with self.session.begin_nested():
                self.session.add(notification)
                self.session.flush()
        except IntegrityError:
            existing = self.session.scalar(
                select(Notification).where(
                    Notification.user_id == user_id, Notification.event_key == event_key
                )
            )
            if existing is None:
                raise
            return existing, False
        return notification, True

    def for_entry(self, entry: QueueEntry, kind: str) -> None:
        number = f"{entry.queue.prefix}{entry.queue_number}"
        if kind == "joined":
            self.create(
                entry.customer_id, f"entry:{entry.id}:joined", NotificationType.QUEUE_JOINED,
                "You joined the queue", f"Your ticket {number} is in the queue.",
                entry.id, "joined",
            )
        elif kind == "called":
            self.create(
                entry.customer_id, f"entry:{entry.id}:called", NotificationType.CUSTOMER_CALLED,
                "Your turn is now",
                f"Ticket {number} has been called. Proceed to "
                f"{entry.counter.name if entry.counter is not None else 'the counter'}.",
                entry.id, "called",
            )
        elif kind == "completed":
            self.create(
                entry.customer_id, f"entry:{entry.id}:completed", NotificationType.SERVICE_COMPLETED,
                "Service completed", f"Your service for ticket {number} is complete.",
                entry.id, "completed",
            )
        elif kind == "approaching":
            self.create(
                entry.customer_id, f"entry:{entry.id}:approaching", NotificationType.QUEUE_APPROACHING,
                "Your turn is approaching", f"Only {self._people_ahead(entry)} people are ahead of ticket {number}.",
                entry.id, "approaching",
            )

    def _people_ahead(self, entry: QueueEntry) -> int:
        return self.session.scalar(
            select(func.count(QueueEntry.id)).where(
                QueueEntry.queue_id == entry.queue_id,
                QueueEntry.status == QueueEntryStatus.WAITING,
                QueueEntry.queue_number < entry.queue_number,
            )
        ) or 0

    def approaching(self, entry: QueueEntry) -> dict | None:
        people_ahead = self._people_ahead(entry)
        if 0 < people_ahead <= settings.notification_approaching_threshold:
            event_key = f"entry:{entry.id}:approaching"
            notification, created = self._create_once(
                entry.customer_id,
                event_key,
                NotificationType.QUEUE_APPROACHING,
                "Your turn is approaching",
                f"Only {people_ahead} people are ahead of ticket "
                f"{entry.queue.prefix}{entry.queue_number}.",
                entry.id,
                "approaching",
            )
            if notification is not None and created:
                return {
                    "queue_id": entry.queue_id,
                    "data": {
                        "queue_entry_id": str(entry.id),
                        "queue_number": entry.queue_number,
                        "people_ahead": people_ahead,
                    },
                }
        return None

    def approaching_queue(self, queue_id: UUID) -> list[dict]:
        entries = self.session.scalars(
            select(QueueEntry)
            .where(
                QueueEntry.queue_id == queue_id,
                QueueEntry.status == QueueEntryStatus.WAITING,
            )
            .order_by(QueueEntry.queue_number)
            .limit(settings.notification_approaching_threshold + 1)
        )
        events = []
        for position, entry in enumerate(entries):
            if position > 0:
                event = self.approaching(entry)
                if event is not None:
                    events.append(event)
        return events

    def queue_status(self, queue_id: UUID, status: str, event_id: UUID | None = None) -> None:
        entries = self.session.scalars(
            select(QueueEntry).where(
                QueueEntry.queue_id == queue_id,
                QueueEntry.status == QueueEntryStatus.WAITING,
            )
        )
        for entry in entries:
            notification_type = {
                "paused": NotificationType.QUEUE_PAUSED,
                "resumed": NotificationType.QUEUE_RESUMED,
                "closed": NotificationType.QUEUE_CLOSED,
            }.get(status)
            if notification_type is None:
                raise ValueError(f"Unsupported queue status notification: {status}")
            self.create(
                entry.customer_id, f"queue:{queue_id}:{status}:{event_id or entry.id}:{entry.id}",
                notification_type,
                f"Queue {status}", f"Your queue is now {status}.", entry.id,
            )

    def commit(self) -> None:
        self.session.commit()

    def list_for_user(self, user_id: UUID, page: int, page_size: int) -> dict:
        query = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
        total = self.session.scalar(select(func.count(Notification.id)).where(Notification.user_id == user_id)) or 0
        return {"page": page, "page_size": page_size, "total": total,
                "items": list(self.session.scalars(query.offset((page - 1) * page_size).limit(page_size)))}

    def unread_count(self, user_id: UUID) -> int:
        return self.session.scalar(select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )) or 0

    def mark_read(self, user_id: UUID, notification_id: UUID | None = None) -> bool:
        query = update(Notification).where(Notification.user_id == user_id)
        if notification_id:
            query = query.where(Notification.id == notification_id)
        result = self.session.execute(query.values(is_read=True))
        self.session.commit()
        return notification_id is None or result.rowcount > 0
