from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ..models.entities import NotificationType


class NotificationResponse(BaseModel):
    id: UUID
    queue_entry_id: UUID | None
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[NotificationResponse]


class NotificationPreferences(BaseModel):
    enabled: bool = True
    joined: bool = True
    called: bool = True
    approaching: bool = True
    completed: bool = True
    queue_updates: bool = True

    model_config = ConfigDict(from_attributes=True)
