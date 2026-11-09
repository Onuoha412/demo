from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TimeNowResponse(BaseModel):
    server_time: datetime
    local_time: datetime
    timezone: str


class TimeHealthResponse(BaseModel):
    server_time: datetime
    timezone_database: str
    clock_skew_seconds: float


class TimeZoneResponse(BaseModel):
    timezone: str


class QueueEstimateResponse(BaseModel):
    queue_id: UUID
    people_ahead: int
    estimated_wait_minutes: int
    estimated_start_at: datetime
    estimated_completion_at: datetime
    calculated_at: datetime
    is_estimate: bool = True
