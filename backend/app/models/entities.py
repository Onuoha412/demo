from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    STAFF = "staff"
    ADMIN = "admin"


class QueueStatus(str, enum.Enum):
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class QueueEntryStatus(str, enum.Enum):
    WAITING = "waiting"
    CALLED = "called"
    SERVING = "serving"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class CounterStatus(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class QueueEventType(str, enum.Enum):
    CREATED = "created"
    JOINED = "joined"
    CALLED = "called"
    SERVING = "serving"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RESUMED = "resumed"


class NotificationType(str, enum.Enum):
    QUEUE_JOINED = "queue_joined"
    QUEUE_APPROACHING = "queue_approaching"
    CUSTOMER_CALLED = "customer_called"
    SERVICE_COMPLETED = "service_completed"
    QUEUE_PAUSED = "queue_paused"
    QUEUE_RESUMED = "queue_resumed"
    QUEUE_UPDATE = "queue_update"
    TURN_APPROACHING = "turn_approaching"
    TURN_CALLED = "turn_called"
    SYSTEM = "system"


class TimestampedEntity(TimestampMixin, Base):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class Organization(TimestampedEntity):
    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organizations_is_active", "is_active"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    users: Mapped[list[User]] = relationship(back_populates="organization")
    branches: Mapped[list[Branch]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class User(TimestampedEntity):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_organization_id", "organization_id"),
        Index("ix_users_branch_id", "branch_id"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL")
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=UserRole.CUSTOMER.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    organization: Mapped[Organization | None] = relationship(back_populates="users")
    branch: Mapped[Branch | None] = relationship(
        back_populates="staff_users", foreign_keys=[branch_id]
    )
    queue_entries: Mapped[list[QueueEntry]] = relationship(back_populates="customer")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Branch(TimestampedEntity):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_branches_organization_name"),
        Index("ix_branches_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    organization: Mapped[Organization] = relationship(back_populates="branches")
    staff_users: Mapped[list[User]] = relationship(
        back_populates="branch", foreign_keys="User.branch_id"
    )
    services: Mapped[list[Service]] = relationship(
        back_populates="branch", cascade="all, delete-orphan"
    )
    counters: Mapped[list[Counter]] = relationship(
        back_populates="branch", cascade="all, delete-orphan"
    )


class Service(TimestampedEntity):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("branch_id", "code", name="uq_services_branch_code"),
        Index("ix_services_branch_id", "branch_id"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    average_service_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    branch: Mapped[Branch] = relationship(back_populates="services")
    queues: Mapped[list[Queue]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )


class Counter(TimestampedEntity):
    __tablename__ = "counters"
    __table_args__ = (
        UniqueConstraint("branch_id", "number", name="uq_counters_branch_number"),
        Index("ix_counters_branch_id", "branch_id"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CounterStatus] = mapped_column(
        Enum(
            CounterStatus,
            name="counter_status",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=CounterStatus.OFFLINE.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    branch: Mapped[Branch] = relationship(back_populates="counters")
    queue_entries: Mapped[list[QueueEntry]] = relationship(back_populates="counter")


class Queue(TimestampedEntity):
    __tablename__ = "queues"
    __table_args__ = (
        UniqueConstraint("service_id", "name", name="uq_queues_service_name"),
        Index("ix_queues_service_id", "service_id"),
        Index("ix_queues_status", "status"),
    )

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(
            QueueStatus,
            name="queue_status",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=QueueStatus.OPEN.value,
    )
    current_number: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    service: Mapped[Service] = relationship(back_populates="queues")
    entries: Mapped[list[QueueEntry]] = relationship(
        back_populates="queue", cascade="all, delete-orphan"
    )
    events: Mapped[list[QueueEvent]] = relationship(
        back_populates="queue", cascade="all, delete-orphan"
    )


class QueueEntry(TimestampedEntity):
    __tablename__ = "queue_entries"
    __table_args__ = (
        UniqueConstraint("queue_id", "queue_number", name="uq_queue_entries_queue_number"),
        Index("ix_queue_entries_queue_status", "queue_id", "status"),
        Index("ix_queue_entries_customer_id", "customer_id"),
        CheckConstraint("queue_number > 0", name="ck_queue_entries_queue_number_positive"),
        CheckConstraint(
            "estimated_wait_minutes IS NULL OR estimated_wait_minutes >= 0",
            name="ck_queue_entries_estimated_wait_nonnegative",
        ),
    )

    queue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queues.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    queue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[QueueEntryStatus] = mapped_column(
        Enum(
            QueueEntryStatus,
            name="queue_entry_status",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=QueueEntryStatus.WAITING.value,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    service_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_wait_minutes: Mapped[int | None] = mapped_column(Integer)
    counter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("counters.id", ondelete="SET NULL")
    )

    queue: Mapped[Queue] = relationship(back_populates="entries")
    customer: Mapped[User] = relationship(back_populates="queue_entries")
    counter: Mapped[Counter | None] = relationship(back_populates="queue_entries")
    events: Mapped[list[QueueEvent]] = relationship(
        back_populates="queue_entry", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="queue_entry")
    feedback: Mapped[Feedback | None] = relationship(
        back_populates="queue_entry", uselist=False
    )


class QueueEvent(Base):
    __tablename__ = "queue_events"
    __table_args__ = (
        Index("ix_queue_events_queue_created_at", "queue_id", "created_at"),
        Index("ix_queue_events_queue_entry_id", "queue_entry_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queues.id", ondelete="CASCADE"), nullable=False
    )
    queue_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="SET NULL")
    )
    event_type: Mapped[QueueEventType] = mapped_column(
        Enum(
            QueueEventType,
            name="queue_event_type",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"), nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    queue: Mapped[Queue] = relationship(back_populates="events")
    queue_entry: Mapped[QueueEntry | None] = relationship(back_populates="events")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_notifications_user_event_key"),
        Index("ix_notifications_user_created_at", "user_id", "created_at"),
        Index("ix_notifications_user_is_read", "user_id", "is_read"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_key: Mapped[str] = mapped_column(String(160), nullable=False)
    queue_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="SET NULL")
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            native_enum=False,
            length=30,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="notifications")
    queue_entry: Mapped[QueueEntry | None] = relationship(back_populates="notifications")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    joined: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    called: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    approaching: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    queue_updates: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating_range"),
        Index("ix_feedback_queue_entry_id", "queue_entry_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    queue_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    queue_entry: Mapped[QueueEntry] = relationship(back_populates="feedback")
