from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..models.entities import QueueEntryStatus, QueueRequestStatus, QueueStatus


class JoinServiceRequest(BaseModel):
    request_note: str | None = Field(default=None, max_length=500)

    @field_validator("request_note")
    @classmethod
    def normalize_request_note(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else None
        return normalized or None


class JoinQueueRequest(JoinServiceRequest):
    customer_id: UUID


class QueueRequestCreate(BaseModel):
    branch_id: UUID
    request_text: str = Field(min_length=3, max_length=1000)

    @field_validator("request_text")
    @classmethod
    def normalize_request_text(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Please describe what you need in at least 3 characters.")
        return normalized


class QueueRequestApproval(BaseModel):
    queue_id: UUID


class QueueRequestRejection(BaseModel):
    review_note: str | None = Field(default=None, max_length=500)

    @field_validator("review_note")
    @classmethod
    def normalize_review_note(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else None
        return normalized or None


class QueueRequestCustomerResponse(BaseModel):
    id: UUID
    full_name: str
    email: str


class QueueRequestResponse(BaseModel):
    id: UUID
    customer: QueueRequestCustomerResponse
    branch_id: UUID
    branch_name: str
    request_text: str
    status: QueueRequestStatus
    assigned_queue_id: UUID | None
    assigned_queue_name: str | None
    queue_entry_id: UUID | None
    queue_number: int | None
    queue_prefix: str | None
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime


class QueueRequestPageResponse(BaseModel):
    items: list[QueueRequestResponse]
    total: int
    pending_total: int
    page: int
    page_size: int


class CounterActionRequest(BaseModel):
    counter_id: UUID | None = None


class QueuePriorityRequest(BaseModel):
    priority: int = Field(ge=0, le=5)


class QueueTransferRequest(BaseModel):
    target_queue_id: UUID


class CounterResponse(BaseModel):
    id: UUID
    name: str
    number: int
    status: str


class QueueEntryResponse(BaseModel):
    id: UUID
    queue_id: UUID | None = None
    queue_prefix: str
    queue_number: int
    priority: int = 0
    status: QueueEntryStatus
    people_ahead: int
    estimated_wait_minutes: int
    counter_id: UUID | None
    counter: CounterResponse | None
    joined_at: datetime
    called_at: datetime | None
    service_started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class QueueResponse(BaseModel):
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
    entries: list[QueueEntryResponse]


class PositionResponse(QueueEntryResponse):
    request_note: str | None = None
    verified_at: datetime | None = None
    verified_by_user_id: UUID | None = None
    transferred_to_entry_id: UUID | None = None
