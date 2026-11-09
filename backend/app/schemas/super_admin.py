from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..models.entities import UserRole


class SuperAdminDashboardResponse(BaseModel):
    users: dict[str, int]
    organizations: int
    branches: int
    services: int
    counters: int
    queues: dict[str, int]
    recent_events: list["AuditLogResponse"]


class SuperAdminRoleUpdate(BaseModel):
    role: UserRole
    branch_id: UUID | None = None
    organization_id: UUID | None = None


class SuperAdminInitialSetupRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=160)
    organization_slug: str = Field(min_length=1, max_length=160)
    branch_name: str = Field(min_length=1, max_length=160)
    branch_address: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    service_name: str = Field(min_length=1, max_length=160)
    service_code: str = Field(min_length=1, max_length=32)
    average_service_minutes: int = Field(default=10, ge=1)
    queue_name: str = Field(min_length=1, max_length=160)
    queue_prefix: str = Field(min_length=1, max_length=10)

    @field_validator(
        "organization_name",
        "organization_slug",
        "branch_name",
        "timezone",
        "service_name",
        "service_code",
        "queue_name",
        "queue_prefix",
    )
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field must not be blank.")
        return normalized

    @field_validator("branch_address")
    @classmethod
    def trim_optional_address(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class SuperAdminInitialSetupResponse(BaseModel):
    organization_id: UUID
    branch_id: UUID
    service_id: UUID
    queue_id: UUID


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    actor_email: str | None = None
    action: str
    target_type: str
    target_id: str | None
    details: dict[str, object]
    created_at: datetime


class AuditLogPageResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AuditLogQuery(BaseModel):
    action: str | None = Field(default=None, max_length=100)


class DatabaseBackupResponse(BaseModel):
    filename: str
    size_bytes: int
    created_at: datetime


SuperAdminDashboardResponse.model_rebuild()
