from uuid import UUID

from pydantic import BaseModel


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None

    model_config = {"from_attributes": True}


class BranchSummary(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    address: str | None
    timezone: str

    model_config = {"from_attributes": True}


class ServiceSummary(BaseModel):
    id: UUID
    branch_id: UUID
    name: str
    code: str
    description: str | None
    average_service_minutes: int
    queue_id: UUID | None = None

    model_config = {"from_attributes": True}
