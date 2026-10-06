from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from ..models.entities import QueueEntryStatus


class QueueHistoryItem(BaseModel):
    entry_id: UUID
    queue_id: UUID
    queue_name: str
    queue_prefix: str
    queue_number: int
    status: QueueEntryStatus
    joined_at: datetime
    completed_at: datetime | None


class QueueHistoryResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[QueueHistoryItem]
