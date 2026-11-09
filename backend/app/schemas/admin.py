from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ..models.entities import CounterStatus, QueueStatus, UserRole
from .queue import QueueEntryResponse


class PageResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=160)
    description: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None


class BranchCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=160)
    address: str | None = None
    timezone: str = "UTC"


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    address: str | None = None
    timezone: str | None = None


class ServiceCreate(BaseModel):
    branch_id: UUID
    name: str = Field(min_length=1, max_length=160)
    code: str = Field(min_length=1, max_length=32)
    description: str | None = None
    average_service_minutes: int = Field(default=10, ge=1)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    code: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = None
    average_service_minutes: int | None = Field(default=None, ge=1)


class CounterCreate(BaseModel):
    branch_id: UUID
    name: str = Field(min_length=1, max_length=80)
    number: int = Field(ge=1)
    status: CounterStatus = CounterStatus.OFFLINE


class CounterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    number: int | None = Field(default=None, ge=1)
    status: CounterStatus | None = None


class QueueCreate(BaseModel):
    service_id: UUID
    name: str = Field(min_length=1, max_length=160)
    prefix: str = Field(min_length=1, max_length=10)
    status: QueueStatus = QueueStatus.OPEN
    capacity_limit: int | None = Field(default=None, ge=1, le=100_000)
    priority_enabled: bool = False


class QueueUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    prefix: str | None = Field(default=None, min_length=1, max_length=10)
    status: QueueStatus | None = None
    capacity_limit: int | None = Field(default=None, ge=1, le=100_000)
    priority_enabled: bool | None = None


class QueueStatusUpdate(BaseModel):
    status: QueueStatus


class AdminQueueCustomerResponse(BaseModel):
    id: UUID
    full_name: str
    email: str


class AdminQueueEntryResponse(QueueEntryResponse):
    customer: AdminQueueCustomerResponse
    request_note: str | None = None
    verified_at: datetime | None = None
    verified_by_user_id: UUID | None = None


class AdminQueueAuditResponse(BaseModel):
    id: UUID
    name: str
    prefix: str
    status: QueueStatus
    current_number: int
    capacity_limit: int | None = None
    priority_enabled: bool = False
    average_service_minutes: int
    active_counters: int
    total_entries: int
    page: int
    page_size: int
    service_id: UUID
    service_name: str
    branch_id: UUID
    entries: list[AdminQueueEntryResponse]


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(
        min_length=5,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.CUSTOMER
    organization_id: UUID | None = None
    branch_id: UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def staff_requires_branch(self) -> "UserCreate":
        if self.role is UserRole.STAFF and self.branch_id is None:
            raise ValueError("Staff users must be assigned to a branch")
        return self


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: str | None = Field(
        default=None,
        min_length=5,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    role: UserRole | None = None
    organization_id: UUID | None = None
    branch_id: UUID | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None


class AdminUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: UserRole
    organization_id: UUID | None
    branch_id: UUID | None
    is_active: bool
    approval_pending: bool
    auth_provider: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserPageResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AnalyticsResponse(BaseModel):
    organizations: int
    branches: int
    services: int
    counters: int
    queues: int
    users: int
    active_users: int
    queue_entries: int
    waiting_entries: int
    serving_entries: int
    completed_entries: int
    skipped_entries: int
    cancelled_entries: int
    average_wait_minutes: float
    average_service_minutes: float
    period_start: datetime | None = None
    period_end: datetime | None = None
    customers_served_today: int = 0
    customers_waiting: int = 0
    average_waiting_time: float = 0
    average_service_time: float = 0
    completion_rate: float = 0
    skip_rate: float = 0
    cancellation_rate: float = 0
    busiest_service: dict | None = None
    busiest_hour: dict | None = None


class MigrationRowResponse(BaseModel):
    row_number: int
    external_id: str | None
    status: Literal["valid", "invalid", "skipped", "created", "rejected"]
    errors: list[str] = Field(default_factory=list)


class MigrationJobResponse(BaseModel):
    id: UUID
    organization_id: UUID
    source_system: str
    file_sha256: str
    status: Literal["preview", "completed", "failed"]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    created_rows: int
    skipped_rows: int
    rejected_rows: int
    preview_rows: list[MigrationRowResponse]
    result_rows: list[MigrationRowResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MigrationJobPageResponse(BaseModel):
    items: list[MigrationJobResponse]
    total: int
    page: int
    page_size: int
