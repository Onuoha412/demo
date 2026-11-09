from datetime import datetime
from uuid import UUID
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ...api.auth_dependencies import can_access_queue, get_current_user, require_admin
from ...db.session import get_db
from ...models import Organization, Queue, QueueEntry, User
from ...services.queue_position import QueuePositionService
from ...schemas.time import (
    QueueEstimateResponse,
    TimeHealthResponse,
    TimeNowResponse,
    TimeZoneResponse,
)
from ...services.time_engine import snapshot, utc_now

router = APIRouter(prefix="/time", tags=["time"])


@router.get("/now", response_model=TimeNowResponse)
def time_now(
    timezone_name: str = Query("UTC", alias="timezone"),
) -> TimeNowResponse:
    try:
        current = snapshot(timezone_name)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return TimeNowResponse(
        server_time=current.server_time,
        local_time=current.local_time,
        timezone=current.timezone,
    )


@router.get("/health", response_model=TimeHealthResponse)
def time_health() -> TimeHealthResponse:
    current = utc_now()
    return TimeHealthResponse(
        server_time=current,
        timezone_database="IANA/zoneinfo",
        clock_skew_seconds=0,
    )


@router.get("/zones", response_model=list[TimeZoneResponse])
def time_zones() -> list[TimeZoneResponse]:
    return [TimeZoneResponse(timezone=name) for name in sorted(available_timezones())]


@router.get("/organizations/{organization_id}", response_model=TimeNowResponse)
def organization_time(
    organization_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> TimeNowResponse:
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    current = snapshot(organization.timezone)
    return TimeNowResponse(
        server_time=current.server_time,
        local_time=current.local_time,
        timezone=current.timezone,
    )


@router.get("/queues/{queue_id}/estimated-wait", response_model=QueueEstimateResponse)
def queue_estimated_wait(
    queue_id: UUID,
    entry_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueueEstimateResponse:
    queue = db.scalar(
        select(Queue)
        .options(joinedload(Queue.service).joinedload(Queue.service.branch))
        .where(Queue.id == queue_id)
    )
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found.")
    if not can_access_queue(db, user, queue):
        raise HTTPException(status_code=404, detail="Queue not found.")
    entry = (
        db.scalar(select(QueueEntry).where(QueueEntry.id == entry_id, QueueEntry.queue_id == queue_id))
        if entry_id
        else None
    )
    if entry_id and entry is None:
        raise HTTPException(status_code=404, detail="Queue entry not found.")
    people_ahead = 0
    if entry is not None:
        people_ahead = QueuePositionService().people_ahead(db, entry)
    estimated_wait = (
        QueuePositionService().estimate(db, queue, entry)[1]
        if entry is not None
        else 0
    )
    calculated_at = utc_now()
    start = calculated_at
    completion = calculated_at
    if estimated_wait:
        from datetime import timedelta

        start = calculated_at + timedelta(minutes=estimated_wait)
        completion = start + timedelta(minutes=queue.service.average_service_minutes)
    return QueueEstimateResponse(
        queue_id=queue_id,
        people_ahead=people_ahead,
        estimated_wait_minutes=estimated_wait,
        estimated_start_at=start,
        estimated_completion_at=completion,
        calculated_at=calculated_at,
    )
