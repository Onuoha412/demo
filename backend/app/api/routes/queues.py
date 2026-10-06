from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...api.auth_dependencies import get_current_user, require_staff
from ...models import Queue, QueueEntry, User
from ...models.entities import UserRole
from ...schemas.queue import (
    CounterActionRequest,
    JoinQueueRequest,
    PositionResponse,
    QueueEntryResponse,
    QueueResponse,
)
from ...services.queue import QueueService

router = APIRouter(prefix="/queues", tags=["queues"])
entry_router = APIRouter(prefix="/queue-entries", tags=["queue-entries"])


@router.post("/{queue_id}/join", response_model=QueueEntryResponse, status_code=status.HTTP_201_CREATED)
def join_queue(
    queue_id: UUID,
    payload: JoinQueueRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role is not UserRole.CUSTOMER or user.id != payload.customer_id:
        raise HTTPException(status_code=403, detail="Customers may only join queues for themselves")
    return QueueService(db).join(queue_id, payload.customer_id)


@router.get("/{queue_id}", response_model=QueueResponse)
def get_queue(
    queue_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return QueueService(db).get_queue(queue_id, page, page_size)


@router.get("/{queue_id}/position/{entry_id}", response_model=PositionResponse)
def get_position(queue_id: UUID, entry_id: UUID, db: Session = Depends(get_db)):
    return QueueService(db).position(queue_id, entry_id)


@router.post("/{queue_id}/next", response_model=QueueEntryResponse)
def next_customer(
    queue_id: UUID,
    payload: CounterActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    _ensure_queue_branch(db, queue_id, user)
    return QueueService(db).next(queue_id, payload.counter_id if payload else None)


@entry_router.post("/{entry_id}/call", response_model=QueueEntryResponse)
def call_entry(
    entry_id: UUID,
    payload: CounterActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    _ensure_entry_branch(db, entry_id, user)
    return QueueService(db).call(entry_id, payload.counter_id if payload else None)


@entry_router.post("/{entry_id}/start", response_model=QueueEntryResponse)
def start_entry(
    entry_id: UUID,
    payload: CounterActionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    _ensure_entry_branch(db, entry_id, user)
    return QueueService(db).start(entry_id, payload.counter_id if payload else None)


@entry_router.post("/{entry_id}/complete", response_model=QueueEntryResponse)
def complete_entry(
    entry_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    _ensure_entry_branch(db, entry_id, user)
    return QueueService(db).complete(entry_id)


@entry_router.post("/{entry_id}/skip", response_model=QueueEntryResponse)
def skip_entry(
    entry_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    _ensure_entry_branch(db, entry_id, user)
    return QueueService(db).skip(entry_id)


@entry_router.post("/{entry_id}/cancel", response_model=QueueEntryResponse)
def cancel_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entry = db.get(QueueEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    if user.role is not UserRole.CUSTOMER or entry.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Customers may only cancel their own entries")
    return QueueService(db).cancel(entry_id)


def _ensure_queue_branch(db: Session, queue_id: UUID, user: User) -> None:
    queue = db.scalar(select(Queue).where(Queue.id == queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")
    if queue.service.branch_id != user.branch_id:
        raise HTTPException(status_code=403, detail="Queue is outside your assigned branch")


def _ensure_entry_branch(db: Session, entry_id: UUID, user: User) -> None:
    entry = db.scalar(select(QueueEntry).where(QueueEntry.id == entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    if entry.queue.service.branch_id != user.branch_id:
        raise HTTPException(status_code=403, detail="Queue is outside your assigned branch")
