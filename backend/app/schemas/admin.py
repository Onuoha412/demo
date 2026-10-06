from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..models.entities import CounterStatus, QueueStatus, UserRole


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


class QueueUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    prefix: str | None = Field(default=None, min_length=1, max_length=10)
    status: QueueStatus | None = None


class QueueStatusUpdate(BaseModel):
    status: QueueStatus


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.CUSTOMER
    organization_id: UUID | None = None
    branch_id: UUID | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: str | None = Field(default=None, min_length=5, max_length=320)
    role: UserRole | None = None
    organization_id: UUID | None = None
    branch_id: UUID | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: UserRole
    organization_id: UUID | None
    branch_id: UUID | None
    is_active: bool
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
