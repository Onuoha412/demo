from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ..models.entities import AppointmentStatus


class AppointmentSlotCreate(BaseModel):
    service_id: UUID
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(default=1, ge=1, le=500)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Appointment times must include a timezone.")
        return value

    @model_validator(mode="after")
    def validate_slot_range(self) -> "AppointmentSlotCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("Appointment end time must follow its start time.")
        return self


class AppointmentSlotResponse(BaseModel):
    id: UUID
    service_id: UUID
    starts_at: datetime
    ends_at: datetime
    capacity: int
    booked_count: int
    is_open: bool


class AppointmentCreate(BaseModel):
    slot_id: UUID


class AppointmentResponse(BaseModel):
    id: UUID
    slot_id: UUID
    service_id: UUID
    service_name: str
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    checked_in_at: datetime | None
    created_at: datetime
