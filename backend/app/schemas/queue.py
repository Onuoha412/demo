from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..models.entities import QueueEntryStatus, QueueStatus


class JoinQueueRequest(BaseModel):
    customer_id: UUID


class CounterActionRequest(BaseModel):
    counter_id: UUID | None = None


class CounterResponse(BaseModel):
    id: UUID
    name: str
    number: int
    status: str


class QueueEntryResponse(BaseModel):
    id: UUID
    queue_id: UUID | None = None
    queue_number: int
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
    average_service_minutes: int
    active_counters: int
    total_entries: int
    page: int
    page_size: int
    entries: list[QueueEntryResponse]


class PositionResponse(QueueEntryResponse):
    pass
