from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ...api.auth_dependencies import get_current_user
from ...db.session import get_db
from ...models import Queue, QueueEntry, Service, User
from ...models.entities import QueueEntryStatus, QueueStatus
from ...schemas.customer import QueueHistoryItem, QueueHistoryResponse
from ...schemas.queue import JoinServiceRequest, PositionResponse
from ...services.queue import QueueService

router = APIRouter(prefix="/customers", tags=["customers"])

ACTIVE_ENTRY_STATUSES = (
    QueueEntryStatus.WAITING,
    QueueEntryStatus.CALLED,
    QueueEntryStatus.SERVING,
)


@router.post("/services/{service_id}/join", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
def join_by_service(
    service_id: UUID,
    branch_id: UUID | None = Query(None),
    queue_id: UUID | None = Query(None),
    payload: JoinServiceRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = db.scalar(
        select(Service).where(Service.id == service_id, Service.is_active.is_(True))
    )
    if service is None or (branch_id is not None and service.branch_id != branch_id):
        raise HTTPException(status_code=404, detail="Service not found")

    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    existing_entry = db.scalar(
        select(QueueEntry)
        .join(Queue, Queue.id == QueueEntry.queue_id)
        .where(
            Queue.service_id == service_id,
            QueueEntry.customer_id == user.id,
            QueueEntry.status.in_(ACTIVE_ENTRY_STATUSES),
        )
        .order_by(QueueEntry.joined_at, QueueEntry.id)
        .limit(1)
    )
    if existing_entry is not None:
        return QueueService(db).position(existing_entry.queue_id, existing_entry.id)

    if queue_id is not None:
        queue = db.scalar(
            select(Queue).where(
                Queue.id == queue_id,
                Queue.service_id == service_id,
            )
        )
        if queue is None:
            raise HTTPException(status_code=404, detail="Queue not found for service")
        candidates = [queue]
    else:
        service_queues = list(
            db.scalars(
                select(Queue)
                .where(Queue.service_id == service_id)
                .order_by(Queue.created_at, Queue.id)
            )
        )
        if not service_queues:
            raise HTTPException(status_code=404, detail="No queue available for service")
        open_queues = [queue for queue in service_queues if queue.status == QueueStatus.OPEN]
        if not open_queues:
            raise HTTPException(
                status_code=409,
                detail="No open queue is available for this service",
            )
        active_counts = dict(
            db.execute(
                select(QueueEntry.queue_id, func.count(QueueEntry.id))
                .join(Queue, Queue.id == QueueEntry.queue_id)
                .where(
                    Queue.service_id == service_id,
                    QueueEntry.status.in_(ACTIVE_ENTRY_STATUSES),
                )
                .group_by(QueueEntry.queue_id)
            ).all()
        )
        candidates = sorted(
            (
                queue
                for queue in open_queues
                if queue.capacity_limit is None
                or active_counts.get(queue.id, 0) < queue.capacity_limit
            ),
            key=lambda queue: (
                active_counts.get(queue.id, 0),
                queue.created_at,
                str(queue.id),
            ),
        )
        if not candidates:
            raise HTTPException(
                status_code=409,
                detail="All open queues for this service have reached capacity",
            )

    for queue in candidates:
        try:
            return QueueService(db).join(
                queue.id,
                user.id,
                request_note=payload.request_note if payload else None,
            )
        except HTTPException as error:
            if queue_id is not None or error.status_code != 409 or error.detail not in {
                "Queue is not open",
                "Queue has reached its capacity",
            }:
                raise

    raise HTTPException(
        status_code=409,
        detail="No open queue is available for this service",
    )


@router.get("/queue-entries/{entry_id}", response_model=PositionResponse)
def queue_entry(entry_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id, QueueEntry.customer_id == user.id).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return QueueService(db).position(entry.queue_id, entry.id)


@router.get("/history", response_model=QueueHistoryResponse)
def history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        db.query(QueueEntry)
        .options(joinedload(QueueEntry.queue))
        .filter(QueueEntry.customer_id == user.id)
        .order_by(QueueEntry.joined_at.desc())
    )
    total = db.query(func.count(QueueEntry.id)).filter(QueueEntry.customer_id == user.id).scalar() or 0
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return QueueHistoryResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[
            QueueHistoryItem(
                entry_id=item.id,
                queue_id=item.queue_id,
                queue_name=item.queue.name,
                queue_prefix=item.queue.prefix,
                queue_number=item.queue_number,
                status=item.status,
                joined_at=item.joined_at,
                completed_at=item.completed_at,
            )
            for item in items
        ],
    )
