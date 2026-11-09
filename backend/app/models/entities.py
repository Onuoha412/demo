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
    Uuid,
    UniqueConstraint,
    func,
    text,
)
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
    SUPER_ADMIN = "super_admin"


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


class QueueRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AppointmentStatus(str, enum.Enum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


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
    CLOSED = "closed"


class NotificationType(str, enum.Enum):
    QUEUE_JOINED = "queue_joined"
    QUEUE_APPROACHING = "queue_approaching"
    CUSTOMER_CALLED = "customer_called"
    SERVICE_COMPLETED = "service_completed"
    QUEUE_PAUSED = "queue_paused"
    QUEUE_RESUMED = "queue_resumed"
    QUEUE_CLOSED = "queue_closed"
    QUEUE_UPDATE = "queue_update"
    TURN_APPROACHING = "turn_approaching"
    TURN_CALLED = "turn_called"
    SYSTEM = "system"


class TimestampedEntity(TimestampMixin, Base):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class Organization(TimestampedEntity):
    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organizations_is_active", "is_active"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Africa/Lagos"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_approved: Mapped[bool] = mapped_column(
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
        Index("ix_users_role_active_created_at", "role", "is_active", "created_at"),
        Index("ix_users_active_created_at", "is_active", "created_at"),
        Index(
            "uq_users_single_super_admin",
            "role",
            unique=True,
            sqlite_where=text("role = 'super_admin'"),
            postgresql_where=text("role = 'super_admin'"),
        ),
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
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    auth_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", server_default="local"
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    approval_pending: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    organization: Mapped[Organization | None] = relationship(back_populates="users")
    branch: Mapped[Branch | None] = relationship(
        back_populates="staff_users", foreign_keys=[branch_id]
    )
    queue_entries: Mapped[list[QueueEntry]] = relationship(
        back_populates="customer", foreign_keys="QueueEntry.customer_id"
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_tokens_user", "user_id"),
        Index("ix_password_reset_tokens_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"

    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    actor: Mapped[User | None] = relationship()


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('staff', 'admin')",
            name="ck_organization_memberships_role",
        ),
        Index(
            "ix_organization_memberships_org_role_active",
            "organization_id",
            "role",
            "is_active",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MigrationJob(Base):
    __tablename__ = "migration_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('preview', 'completed', 'failed')",
            name="ck_migration_jobs_status",
        ),
        Index(
            "ix_migration_jobs_organization_created",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="preview", server_default="preview"
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preview_rows: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    result_rows: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MigrationMapping(Base):
    __tablename__ = "migration_mappings"
    __table_args__ = (
        Index(
            "ix_migration_mappings_target_user",
            "target_user_id",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    source_system: Mapped[str] = mapped_column(
        String(80), primary_key=True
    )
    external_id: Mapped[str] = mapped_column(
        String(160), primary_key=True
    )
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    migration_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("migration_jobs.id", ondelete="RESTRICT"), nullable=False
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
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
        CheckConstraint("average_service_minutes > 0"),
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
        CheckConstraint("current_number >= 0"),
        CheckConstraint(
            "capacity_limit IS NULL OR capacity_limit > 0",
            name="ck_queues_capacity_limit_positive",
        ),
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
    capacity_limit: Mapped[int | None] = mapped_column(Integer)
    priority_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
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
        Index("ix_queue_entries_position", "queue_id", "status", "queue_number"),
        Index("ix_queue_entries_customer_id", "customer_id"),
        CheckConstraint("queue_number > 0", name="ck_queue_entries_queue_number_positive"),
        CheckConstraint(
            "priority BETWEEN 0 AND 5", name="ck_queue_entries_priority_range"
        ),
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
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
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
    request_note: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    queue: Mapped[Queue] = relationship(back_populates="entries")
    customer: Mapped[User] = relationship(
        back_populates="queue_entries", foreign_keys=[customer_id]
    )
    verified_by: Mapped[User | None] = relationship(foreign_keys=[verified_by_user_id])
    counter: Mapped[Counter | None] = relationship(back_populates="queue_entries")
    events: Mapped[list[QueueEvent]] = relationship(
        back_populates="queue_entry", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="queue_entry")
    feedback: Mapped[Feedback | None] = relationship(
        back_populates="queue_entry", uselist=False
    )


class AppointmentSlot(TimestampedEntity):
    __tablename__ = "appointment_slots"
    __table_args__ = (
        UniqueConstraint("service_id", "starts_at", name="uq_appointment_slots_service_start"),
        Index("ix_appointment_slots_service_start", "service_id", "starts_at"),
        CheckConstraint("ends_at > starts_at", name="ck_appointment_slots_end_after_start"),
        CheckConstraint("capacity > 0", name="ck_appointment_slots_capacity_positive"),
        CheckConstraint("booked_count >= 0", name="ck_appointment_slots_booked_nonnegative"),
        CheckConstraint("booked_count <= capacity", name="ck_appointment_slots_booked_within_capacity"),
    )

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    booked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    service: Mapped[Service] = relationship()
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )


class Appointment(TimestampedEntity):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked', 'checked_in', 'cancelled', 'completed', 'no_show')",
            name="ck_appointments_status",
        ),
        Index("ix_appointments_customer_created", "customer_id", "created_at"),
        Index("ix_appointments_slot_status", "slot_id", "status"),
        Index(
            "uq_appointments_active_customer_slot",
            "slot_id",
            "customer_id",
            unique=True,
            sqlite_where=text("status IN ('booked', 'checked_in')"),
            postgresql_where=text("status IN ('booked', 'checked_in')"),
        ),
    )

    slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointment_slots.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=AppointmentStatus.BOOKED.value,
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    slot: Mapped[AppointmentSlot] = relationship(back_populates="appointments")
    customer: Mapped[User] = relationship()


class QueueTransfer(TimestampedEntity):
    __tablename__ = "queue_transfers"
    __table_args__ = (
        UniqueConstraint("target_entry_id", name="uq_queue_transfers_target_entry"),
        Index("ix_queue_transfers_source_created", "source_queue_id", "created_at"),
        Index("ix_queue_transfers_target_created", "target_queue_id", "created_at"),
    )

    source_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="RESTRICT"), nullable=False
    )
    target_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="RESTRICT"), nullable=False
    )
    source_queue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queues.id", ondelete="RESTRICT"), nullable=False
    )
    target_queue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queues.id", ondelete="RESTRICT"), nullable=False
    )
    source_queue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target_queue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class QueueRequest(TimestampedEntity):
    __tablename__ = "queue_requests"
    __table_args__ = (
        Index("ix_queue_requests_customer_created", "customer_id", "created_at"),
        Index("ix_queue_requests_branch_status_created", "branch_id", "status", "created_at"),
        UniqueConstraint("queue_entry_id", name="uq_queue_requests_queue_entry"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[QueueRequestStatus] = mapped_column(
        Enum(
            QueueRequestStatus,
            name="queue_request_status",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=QueueRequestStatus.PENDING.value,
    )
    assigned_queue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("queues.id", ondelete="SET NULL")
    )
    queue_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("queue_entries.id", ondelete="SET NULL")
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[User] = relationship(foreign_keys=[customer_id])
    branch: Mapped[Branch] = relationship()
    assigned_queue: Mapped[Queue | None] = relationship()
    queue_entry: Mapped[QueueEntry | None] = relationship()
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_user_id])


class QueueEvent(Base):
    __tablename__ = "queue_events"
    __table_args__ = (
        Index("ix_queue_events_queue_created_at", "queue_id", "created_at"),
        Index("ix_queue_events_queue_entry_id", "queue_entry_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
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
        JSON(), nullable=False, server_default="{}"
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
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
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


class Announcement(TimestampedEntity):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint(
            "audience IN ('all', 'customer', 'staff')",
            name="ck_announcements_audience",
        ),
        Index("ix_announcements_published_expires", "published_at", "expires_at"),
        Index(
            "ix_announcements_org_audience_published",
            "organization_id",
            "audience",
            "published_at",
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column("message", Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class PlatformSettings(Base):
    __tablename__ = "platform_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    maintenance_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    maintenance_message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="QueueLess is temporarily unavailable for scheduled maintenance.",
        server_default="QueueLess is temporarily unavailable for scheduled maintenance.",
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ScheduledJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ScheduledJob(TimestampedEntity):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index("ix_scheduled_jobs_due", "status", "scheduled_at"),
        Index("ix_scheduled_jobs_organization", "organization_id", "scheduled_at"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ScheduledJobStatus] = mapped_column(
        Enum(
            ScheduledJobStatus,
            name="scheduled_job_status",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=ScheduledJobStatus.PENDING.value,
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_execution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_execution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_details: Mapped[str | None] = mapped_column(Text)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(100))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=8, server_default="8")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ScheduledJobExecution(Base):
    __tablename__ = "scheduled_job_executions"
    __table_args__ = (Index("ix_scheduled_job_executions_job_started", "job_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_details: Mapped[str | None] = mapped_column(Text)


class OutboxStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    DEAD = "dead"


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_delivery", "status", "available_at"),
        Index("ix_outbox_events_queue_sequence", "queue_id", "sequence_number"),
        Index("ix_outbox_events_idempotency", "idempotency_key", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    queue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("queues.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, server_default=text("'{}'"))
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(
            OutboxStatus,
            name="outbox_status",
            native_enum=False,
            length=20,
            values_callable=lambda members: [member.value for member in members],
        ),
        nullable=False,
        server_default=OutboxStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating_range"),
        Index("ix_feedback_queue_entry_id", "queue_entry_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
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


class FeedbackReport(TimestampMixin, Base):
    __tablename__ = "feedback_reports"
    __table_args__ = (
        CheckConstraint(
            "category IN ('general', 'bug', 'feature_request', 'ui_accessibility', "
            "'queue_accuracy', 'performance_connection', 'security_privacy', "
            "'account_login', 'staff_service', 'organization_setup_migration', "
            "'notification', 'other')",
            name="ck_feedback_reports_category",
        ),
        CheckConstraint(
            "status IN ('new', 'under_review', 'planned', 'in_progress', "
            "'waiting_for_information', 'resolved', 'declined', 'duplicate')",
            name="ck_feedback_reports_status",
        ),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_feedback_reports_priority"),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_feedback_reports_severity",
        ),
        CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5",
            name="ck_feedback_reports_rating",
        ),
        Index("ix_feedback_reports_org_status_created", "organization_id", "status", "created_at"),
        Index("ix_feedback_reports_category_created", "category", "created_at"),
        Index("ix_feedback_reports_reporter_created", "reporter_user_id", "created_at"),
        UniqueConstraint("idempotency_key", name="uq_feedback_reports_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reporter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reporter_role: Mapped[str | None] = mapped_column(String(20))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL")
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL")
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    improvement_suggestion: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    is_anonymous: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    page_identifier: Mapped[str | None] = mapped_column(String(160))
    app_version: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="new", server_default="new"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default="low", server_default="low"
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    release_version: Mapped[str | None] = mapped_column(String(40))
    resolution_helpful: Mapped[bool | None] = mapped_column(Boolean)
    resolution_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    replies: Mapped[list[FeedbackReply]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    status_history: Mapped[list[FeedbackStatusHistory]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    votes: Mapped[list[FeedbackVote]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    task_links: Mapped[list[FeedbackTaskLink]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class FeedbackReply(Base):
    __tablename__ = "feedback_replies"
    __table_args__ = (Index("ix_feedback_replies_report_created", "report_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped[FeedbackReport] = relationship(back_populates="replies")


class FeedbackStatusHistory(Base):
    __tablename__ = "feedback_status_history"
    __table_args__ = (
        Index("ix_feedback_status_history_report_created", "report_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped[FeedbackReport] = relationship(back_populates="status_history")


class FeedbackVote(Base):
    __tablename__ = "feedback_votes"
    __table_args__ = (
        UniqueConstraint("report_id", "user_id", name="uq_feedback_votes_report_user"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    report: Mapped[FeedbackReport] = relationship(back_populates="votes")


class FeedbackImprovementTask(TimestampMixin, Base):
    __tablename__ = "feedback_improvement_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('reviewed', 'prioritized', 'assigned', 'implemented', "
            "'tested', 'released', 'measured', 'declined')",
            name="ck_feedback_improvement_tasks_status",
        ),
        CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name="ck_feedback_improvement_tasks_priority",
        ),
        CheckConstraint(
            "impact IN ('low', 'medium', 'high', 'critical')",
            name="ck_feedback_improvement_tasks_impact",
        ),
        Index("ix_feedback_improvement_tasks_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    impact: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    affected_features: Mapped[str | None] = mapped_column(String(500))
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    target_release: Mapped[str | None] = mapped_column(String(40))
    release_version: Mapped[str | None] = mapped_column(String(40))
    verification_notes: Mapped[str | None] = mapped_column(Text)
    post_release_outcome: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="reviewed", server_default="reviewed"
    )

    report_links: Mapped[list[FeedbackTaskLink]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class FeedbackTaskLink(Base):
    __tablename__ = "feedback_task_links"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="CASCADE"), primary_key=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback_improvement_tasks.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped[FeedbackReport] = relationship(back_populates="task_links")
    task: Mapped[FeedbackImprovementTask] = relationship(back_populates="report_links")
