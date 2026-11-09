from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..models.entities import ScheduledJobStatus


class ScheduledJobResponse(BaseModel):
    id: UUID
    organization_id: UUID | None
    task_type: str
    payload: dict
    scheduled_at: datetime
    timezone: str
    status: ScheduledJobStatus
    retry_count: int
    last_execution_at: datetime | None
    next_execution_at: datetime | None
    error_details: str | None
    lease_until: datetime | None
    worker_id: str | None
    max_attempts: int
    idempotency_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduledJobCreate(BaseModel):
    task_type: str = Field(min_length=1, max_length=80)
    payload: dict = Field(default_factory=dict)
    scheduled_at: datetime
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=160)
    max_attempts: int = Field(default=8, ge=1, le=100)

    @field_validator("scheduled_at")
    @classmethod
    def require_aware_schedule(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone offset.")
        return value
