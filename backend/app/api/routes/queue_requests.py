from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ...api.auth_dependencies import (
    get_current_user,
    has_active_organization_admin_membership,
)
from ...db.session import get_db
from ...models import Branch, Organization, Queue, QueueEntry, QueueRequest, User
from ...models.entities import QueueRequestStatus, UserRole
from ...schemas.queue import (
    QueueRequestApproval,
    QueueRequestCreate,
    QueueRequestCustomerResponse,
    QueueRequestPageResponse,
    QueueRequestRejection,
    QueueRequestResponse,
)
from ...services.realtime import realtime
from ...services.queue import QueueService

router = APIRouter(tags=["queue requests"])

_request_loads = (
    joinedload(QueueRequest.customer),
    joinedload(QueueRequest.branch),
    joinedload(QueueRequest.assigned_queue),
    joinedload(QueueRequest.queue_entry).joinedload(QueueEntry.queue),
)


def _response(item: QueueRequest) -> QueueRequestResponse:
    entry = item.queue_entry
    return QueueRequestResponse(
        id=item.id,
        customer=QueueRequestCustomerResponse(
            id=item.customer.id,
            full_name=item.customer.full_name,
            email=item.customer.email,
        ),
        branch_id=item.branch_id,
        branch_name=item.branch.name,
        request_text=item.request_text,
        status=item.status,
        assigned_queue_id=item.assigned_queue_id,
        assigned_queue_name=(
            item.assigned_queue.name if item.assigned_queue is not None else None
        ),
        queue_entry_id=item.queue_entry_id,
        queue_number=entry.queue_number if entry is not None else None,
        queue_prefix=entry.queue.prefix if entry is not None else None,
        review_note=item.review_note,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
    )


def _get_request(db: Session, request_id: UUID) -> QueueRequest:
    item = db.scalar(
        select(QueueRequest)
        .options(*_request_loads)
        .where(QueueRequest.id == request_id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Queue request not found")
    return item


def _require_reviewer_access(item: QueueRequest, user: User, db: Session) -> None:
    if (
        user.role is UserRole.ADMIN
        and has_active_organization_admin_membership(db, user)
        and user.organization_id is not None
        and item.branch.organization_id == user.organization_id
    ):
        return
    if user.role is UserRole.STAFF and user.branch_id == item.branch_id:
        return
    raise HTTPException(
        status_code=403,
        detail="You cannot review requests for another branch.",
    )


@router.post(
    "/customers/queue-requests",
    response_model=QueueRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_queue_request(
    payload: QueueRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueueRequestResponse:
    if user.role is not UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Customer access required.")
    branch = db.scalar(
        select(Branch)
        .join(Branch.organization)
        .where(
            Branch.id == payload.branch_id,
            Branch.is_active.is_(True),
            Organization.is_active.is_(True),
            Organization.is_approved.is_(True),
        )
    )
    if branch is None:
        raise HTTPException(
            status_code=404, detail="The selected branch is not available."
        )
    item = QueueRequest(
        customer_id=user.id,
        branch_id=branch.id,
        request_text=payload.request_text,
        status=QueueRequestStatus.PENDING,
    )
    db.add(item)
    db.commit()
    realtime.publish_announcement_nowait(
        "staff",
        {"request_id": str(item.id), "branch_id": str(branch.id)},
        "QUEUE_REQUEST_CREATED",
        organization_id=str(branch.organization_id),
    )
    return _response(_get_request(db, item.id))


@router.get(
    "/customers/queue-requests",
    response_model=list[QueueRequestResponse],
)
def list_customer_queue_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QueueRequestResponse]:
    if user.role is not UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Customer access required.")
    requests = list(
        db.scalars(
            select(QueueRequest)
            .options(*_request_loads)
            .where(QueueRequest.customer_id == user.id)
            .order_by(QueueRequest.created_at.desc())
            .limit(50)
        )
    )
    return [_response(item) for item in requests]


@router.get(
    "/queue-requests/review",
    response_model=QueueRequestPageResponse,
)
def list_queue_requests_for_review(
    request_status: Literal["pending", "approved", "rejected", "reviewed"] = Query(
        "pending", alias="status"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueueRequestPageResponse:
    filters = []
    if request_status == "reviewed":
        filters.append(
            QueueRequest.status.in_(
                [QueueRequestStatus.APPROVED, QueueRequestStatus.REJECTED]
            )
        )
    else:
        filters.append(QueueRequest.status == QueueRequestStatus(request_status))
    if user.role is UserRole.STAFF and user.branch_id is not None:
        filters.append(QueueRequest.branch_id == user.branch_id)
    elif user.role is UserRole.ADMIN:
        if not has_active_organization_admin_membership(db, user):
            raise HTTPException(
                status_code=403,
                detail="An active organization administrator membership is required.",
            )
        branch_ids = select(Branch.id).where(
            Branch.organization_id == user.organization_id
        )
        filters.append(QueueRequest.branch_id.in_(branch_ids))
    elif user.role is not UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Staff or administrator access required.")

    total = db.scalar(
        select(func.count(QueueRequest.id)).where(*filters)
    ) or 0
    pending_filters = [
        QueueRequest.status == QueueRequestStatus.PENDING,
        *(filters[1:]),
    ]
    pending_total = db.scalar(
        select(func.count(QueueRequest.id)).where(*pending_filters)
    ) or 0
    requests = list(
        db.scalars(
            select(QueueRequest)
            .options(*_request_loads)
            .where(*filters)
            .order_by(QueueRequest.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return QueueRequestPageResponse(
        items=[_response(item) for item in requests],
        total=total,
        pending_total=pending_total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/queue-requests/{request_id}/approve",
    response_model=QueueRequestResponse,
)
def approve_queue_request(
    request_id: UUID,
    payload: QueueRequestApproval,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueueRequestResponse:
    if user.role not in (UserRole.ADMIN, UserRole.STAFF):
        raise HTTPException(status_code=403, detail="Staff or administrator access required.")
    item = _get_request(db, request_id)
    _require_reviewer_access(item, user, db)
    assigned_queue = db.scalar(
        select(Queue)
        .options(joinedload(Queue.service))
        .where(Queue.id == payload.queue_id)
    )
    if assigned_queue is None:
        raise HTTPException(status_code=404, detail="Queue not found.")
    assigned_branch = db.get(Branch, assigned_queue.service.branch_id)
    if assigned_branch is None:
        raise HTTPException(status_code=404, detail="Queue not found.")
    if user.role is UserRole.STAFF and assigned_branch.id != user.branch_id:
        raise HTTPException(
            status_code=403, detail="Queue is outside your assigned branch."
        )
    if user.role is UserRole.ADMIN and (
        user.organization_id is None
        or assigned_branch.organization_id != user.organization_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Queue not found.",
        )
    approved = QueueService(db).approve_queue_request(
        request_id, assigned_queue.id, user.id
    )
    realtime.publish_announcement_nowait(
        "staff",
        {"request_id": str(approved.id), "branch_id": str(approved.branch_id)},
        "QUEUE_REQUEST_UPDATED",
        organization_id=str(assigned_branch.organization_id),
    )
    return _response(_get_request(db, approved.id))


@router.post(
    "/queue-requests/{request_id}/reject",
    response_model=QueueRequestResponse,
)
def reject_queue_request(
    request_id: UUID,
    payload: QueueRequestRejection,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueueRequestResponse:
    if user.role not in (UserRole.ADMIN, UserRole.STAFF):
        raise HTTPException(status_code=403, detail="Staff or administrator access required.")
    item = _get_request(db, request_id)
    _require_reviewer_access(item, user, db)
    if item.status is not QueueRequestStatus.PENDING:
        raise HTTPException(status_code=409, detail="This queue request has already been reviewed.")
    item.status = QueueRequestStatus.REJECTED
    item.review_note = payload.review_note
    item.reviewed_by_user_id = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    branch = db.get(Branch, item.branch_id)
    if branch is not None:
        realtime.publish_announcement_nowait(
            "staff",
            {"request_id": str(item.id), "branch_id": str(branch.id)},
            "QUEUE_REQUEST_UPDATED",
            organization_id=str(branch.organization_id),
        )
    return _response(_get_request(db, item.id))
