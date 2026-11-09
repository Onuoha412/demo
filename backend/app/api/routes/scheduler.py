from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...api.auth_dependencies import require_admin
from ...db.session import get_db
from ...models import ScheduledJob, User
from ...models.entities import ScheduledJobStatus
from ...schemas.scheduler import ScheduledJobCreate, ScheduledJobResponse
from ...services.scheduler import schedule_job
from ...services.time_engine import utc_now

router = APIRouter(prefix="/scheduler/jobs", tags=["scheduler"])


@router.post("", response_model=ScheduledJobResponse, status_code=201)
def create_job(
    request: ScheduledJobCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ScheduledJob:
    return schedule_job(
        db,
        task_type=request.task_type,
        payload=request.payload,
        scheduled_at=request.scheduled_at,
        timezone=request.timezone,
        idempotency_key=request.idempotency_key,
        organization_id=(
            None if admin.role.value == "super_admin" else admin.organization_id
        ),
        created_by_user_id=admin.id,
        max_attempts=request.max_attempts,
    )


@router.get("", response_model=list[ScheduledJobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[ScheduledJob]:
    query = select(ScheduledJob).order_by(ScheduledJob.scheduled_at).limit(100)
    if admin.organization_id is not None and admin.role.value != "super_admin":
        query = query.where(ScheduledJob.organization_id == admin.organization_id)
    return list(db.scalars(query))


@router.get("/{job_id}", response_model=ScheduledJobResponse)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ScheduledJob:
    job = db.get(ScheduledJob, job_id)
    if job is None or (
        admin.role.value != "super_admin"
        and job.organization_id != admin.organization_id
    ):
        raise HTTPException(status_code=404, detail="Scheduled job not found.")
    return job


@router.post("/{job_id}/retry", response_model=ScheduledJobResponse)
def retry_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ScheduledJob:
    job = get_job(job_id, db, admin)
    if job.status not in {ScheduledJobStatus.FAILED, ScheduledJobStatus.RETRYING}:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried.")
    job.status = ScheduledJobStatus.RETRYING
    job.retry_count += 1
    job.scheduled_at = utc_now()
    job.error_details = None
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/cancel", response_model=ScheduledJobResponse)
def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ScheduledJob:
    job = get_job(job_id, db, admin)
    if job.status not in {ScheduledJobStatus.PENDING, ScheduledJobStatus.RETRYING}:
        raise HTTPException(status_code=409, detail="Only pending jobs can be cancelled.")
    job.status = ScheduledJobStatus.CANCELLED
    db.commit()
    db.refresh(job)
    return job
