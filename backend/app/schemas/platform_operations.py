from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


AnnouncementAudience = Literal["all", "customer", "staff"]


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=5000)
    audience: AnnouncementAudience = "all"
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_content(self):
        self.title = self.title.strip()
        self.body = self.body.strip()
        if not self.title or not self.body:
            raise ValueError("Title and announcement text must not be blank.")
        return self


class AnnouncementResponse(BaseModel):
    id: UUID
    organization_id: UUID | None
    title: str
    body: str
    audience: AnnouncementAudience
    published_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformSettingsUpdate(BaseModel):
    maintenance_mode: bool
    maintenance_message: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def normalize_message(self):
        self.maintenance_message = self.maintenance_message.strip()
        if not self.maintenance_message:
            raise ValueError("Maintenance message must not be blank.")
        return self


class PlatformSettingsResponse(BaseModel):
    maintenance_mode: bool
    maintenance_message: str
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
