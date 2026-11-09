from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import ScheduledJob, ScheduledJobExecution
from ..models.entities import ScheduledJobStatus
from .time_engine import as_utc, utc_now


def schedule_job(
    session: Session,
    *,
    task_type: str,
    payload: dict,
    scheduled_at,
    timezone: str,
    idempotency_key: str,
    organization_id: UUID | None,
    created_by_user_id: UUID | None,
    max_attempts: int = 8,
) -> ScheduledJob:
    existing = session.scalar(
        select(ScheduledJob).where(ScheduledJob.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    job = ScheduledJob(
        task_type=task_type,
        payload=payload,
        scheduled_at=as_utc(scheduled_at),
        timezone=timezone,
        idempotency_key=idempotency_key,
        organization_id=organization_id,
        created_by_user_id=created_by_user_id,
        max_attempts=max_attempts,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def claim_due_job(
    session: Session,
    job_id: UUID | None = None,
    *,
    lease_seconds: int = 60,
    worker_id: str | None = None,
) -> ScheduledJob | None:
    now = utc_now()
    worker_id = worker_id or str(uuid4())
    filters = [
        (
            ScheduledJob.status.in_(
                [ScheduledJobStatus.PENDING, ScheduledJobStatus.RETRYING]
            )
            | (
                (ScheduledJob.status == ScheduledJobStatus.RUNNING)
                & (ScheduledJob.lease_until < now)
            )
        ),
        ScheduledJob.scheduled_at <= now,
    ]
    if job_id is not None:
        filters.append(ScheduledJob.id == job_id)
    job = session.scalar(
        select(ScheduledJob).where(*filters).order_by(ScheduledJob.scheduled_at).limit(1)
    )
    if job is None:
        return None
    changed = session.execute(
        update(ScheduledJob)
        .where(
            ScheduledJob.id == job.id,
            (
                ScheduledJob.status.in_(
                    [ScheduledJobStatus.PENDING, ScheduledJobStatus.RETRYING]
                )
                | (
                    (ScheduledJob.status == ScheduledJobStatus.RUNNING)
                    & (ScheduledJob.lease_until < now)
                )
            ),
        )
        .values(
            status=ScheduledJobStatus.RUNNING,
            last_execution_at=now,
            lease_until=now + timedelta(seconds=lease_seconds),
            worker_id=worker_id,
        )
    )
    if changed.rowcount != 1:
        session.rollback()
        return None
    session.add(
        ScheduledJobExecution(
            job_id=job.id,
            started_at=now,
            status=ScheduledJobStatus.RUNNING.value,
        )
    )
    session.commit()
    session.refresh(job)
    return job


def mark_job_complete(session: Session, job_id: UUID, worker_id: str) -> None:
    job = session.scalar(
        select(ScheduledJob).where(
            ScheduledJob.id == job_id,
            ScheduledJob.status == ScheduledJobStatus.RUNNING,
            ScheduledJob.worker_id == worker_id,
        )
    )
    if job is None:
        return
    now = utc_now()
    job.status = ScheduledJobStatus.COMPLETED
    job.lease_until = None
    job.worker_id = None
    _finish_execution(session, job.id, now, ScheduledJobStatus.COMPLETED.value)
    session.commit()


def mark_job_failed(session: Session, job: ScheduledJob, error: str) -> None:
    now = utc_now()
    job.retry_count += 1
    job.status = (
        ScheduledJobStatus.RETRYING
        if job.retry_count < job.max_attempts
        else ScheduledJobStatus.FAILED
    )
    job.error_details = error[:2000]
    job.lease_until = None
    job.worker_id = None
    job.scheduled_at = utc_now() + timedelta(
        seconds=min(300, 2 ** min(job.retry_count, 8))
    )
    execution = session.scalar(
        select(ScheduledJobExecution)
        .where(
            ScheduledJobExecution.job_id == job.id,
            ScheduledJobExecution.status == ScheduledJobStatus.RUNNING.value,
        )
        .order_by(ScheduledJobExecution.started_at.desc())
        .limit(1)
    )
    if execution is not None:
        execution.status = ScheduledJobStatus.FAILED.value
        execution.finished_at = now
        execution.error_details = error[:2000]
    session.commit()


def _finish_execution(
    session: Session,
    job_id: UUID,
    finished_at,
    status: str,
    error: str | None = None,
) -> None:
    execution = session.scalar(
        select(ScheduledJobExecution)
        .where(
            ScheduledJobExecution.job_id == job_id,
            ScheduledJobExecution.status == ScheduledJobStatus.RUNNING.value,
        )
        .order_by(ScheduledJobExecution.started_at.desc())
        .limit(1)
    )
    if execution is not None:
        execution.status = status
        execution.finished_at = finished_at
        execution.error_details = error
