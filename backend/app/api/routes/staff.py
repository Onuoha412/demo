from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ...api.auth_dependencies import require_staff
from ...db.session import get_db
from ...models import Branch, Counter, Queue, QueueEntry, User
from ...models.entities import QueueEntryStatus, QueueStatus
from ...schemas.queue import QueueResponse
from ...services.queue import QueueService

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/dashboard")
def dashboard(user: User = Depends(require_staff), db: Session = Depends(get_db)):
    queues = list(
        db.scalars(
            select(Queue)
            .join(Queue.service)
            .where(Queue.service.has(branch_id=user.branch_id))
            .options(joinedload(Queue.service))
            .order_by(Queue.name)
        )
    )
    counts_by_queue: dict[UUID, dict[QueueEntryStatus, int]] = {}
    if queues:
        for queue_id, entry_status, count in db.execute(
            select(QueueEntry.queue_id, QueueEntry.status, func.count(QueueEntry.id))
            .where(QueueEntry.queue_id.in_([queue.id for queue in queues]))
            .group_by(QueueEntry.queue_id, QueueEntry.status)
        ):
            counts_by_queue.setdefault(queue_id, {})[entry_status] = count
    counters = list(
        db.scalars(
            select(Counter).where(Counter.branch_id == user.branch_id).order_by(Counter.number)
        )
    )
    queue_data = []
    for queue in queues:
        counts = counts_by_queue.get(queue.id, {})
        queue_data.append(
            {
                "id": queue.id,
                "name": queue.name,
                "prefix": queue.prefix,
                "status": queue.status,
                "waiting_count": counts.get(QueueEntryStatus.WAITING, 0),
                "serving_count": counts.get(QueueEntryStatus.SERVING, 0),
                "completed_count": counts.get(QueueEntryStatus.COMPLETED, 0),
                "skipped_count": counts.get(QueueEntryStatus.SKIPPED, 0),
            }
        )
    branch = db.get(Branch, user.branch_id)
    return {
        "branch": {"id": branch.id, "name": branch.name} if branch else None,
        "counters": [
            {"id": counter.id, "name": counter.name, "number": counter.number, "status": counter.status}
            for counter in counters
        ],
        "queues": queue_data,
    }


@router.get("/queues/{queue_id}", response_model=QueueResponse)
def queue(
    queue_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    queue = db.scalar(select(Queue).options(joinedload(Queue.service)).where(Queue.id == queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")
    if queue.service.branch_id != user.branch_id:
        raise HTTPException(status_code=403, detail="Queue is outside your assigned branch")
    return QueueService(db).get_queue(queue_id, page, page_size)


@router.get("/customers")
def customers(user: User = Depends(require_staff), db: Session = Depends(get_db)):
    entries = list(
        db.scalars(
            select(QueueEntry)
            .join(Queue)
            .join(Queue.service)
            .where(Queue.service.has(branch_id=user.branch_id))
            .options(joinedload(QueueEntry.customer))
            .order_by(QueueEntry.joined_at.desc())
            .limit(100)
        )
    )
    return [
        {
            "entry_id": entry.id,
            "queue_number": entry.queue_number,
            "status": entry.status,
            "customer": {"id": entry.customer.id, "full_name": entry.customer.full_name, "email": entry.customer.email},
            "joined_at": entry.joined_at,
        }
        for entry in entries
    ]


@router.get("/history")
def history(user: User = Depends(require_staff), db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(QueueEntry)
            .join(Queue)
            .join(Queue.service)
            .where(
                Queue.service.has(branch_id=user.branch_id),
                QueueEntry.status.in_([QueueEntryStatus.COMPLETED, QueueEntryStatus.SKIPPED]),
            )
            .order_by(QueueEntry.updated_at.desc())
            .limit(100)
        )
    )


@router.post("/queues/{queue_id}/pause")
def pause_queue(queue_id: UUID, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    _ensure_branch(db, queue_id, user)
    return QueueService(db).set_status(queue_id, QueueStatus.PAUSED)


@router.post("/queues/{queue_id}/resume")
def resume_queue(queue_id: UUID, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    _ensure_branch(db, queue_id, user)
    return QueueService(db).set_status(queue_id, QueueStatus.OPEN)


def _ensure_branch(db: Session, queue_id: UUID, user: User) -> None:
    queue = db.scalar(select(Queue).options(joinedload(Queue.service)).where(Queue.id == queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")
    if queue.service.branch_id != user.branch_id:
        raise HTTPException(status_code=403, detail="Queue is outside your assigned branch")
