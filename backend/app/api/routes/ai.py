from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...api.auth_dependencies import get_current_user
from ...db.session import get_db
from ...models import QueueEntry, User
from ...models.entities import UserRole
from ...schemas.ai import WaitTimeResponse
from ...services.wait_time import WaitTimePredictionService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/wait-time/{queue_entry_id}", response_model=WaitTimeResponse)
def wait_time(
    queue_entry_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = db.get(QueueEntry, queue_entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    if user.role is UserRole.CUSTOMER and entry.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Queue entry belongs to another customer")
    if user.role is UserRole.STAFF and entry.queue.service.branch_id != user.branch_id:
        raise HTTPException(status_code=403, detail="Queue entry is outside your assigned branch")
    return WaitTimePredictionService(db).predict(queue_entry_id)
