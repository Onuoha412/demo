from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.events import validate_event
from app.models import ScheduledJob, ScheduledJobExecution
from app.models.entities import ScheduledJobStatus
from app.services.scheduler import (
    claim_due_job,
    mark_job_complete,
    mark_job_failed,
    schedule_job,
)
from app.services.jobs import _run_once, register_handler


def test_event_contract_rejects_unknown_types() -> None:
    validate_event(
        "ticket.called",
        {"queue_id": str(uuid4()), "ticket_id": str(uuid4())},
        1,
    )
    try:
        validate_event("not-a-queueless-event", {}, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown event types must not enter the outbox")


def test_job_idempotency_and_completion(db_session) -> None:
    scheduled_at = datetime.now(timezone.utc)
    first = schedule_job(
        db_session,
        task_type="test.handler",
        payload={"value": 1},
        scheduled_at=scheduled_at,
        timezone="UTC",
        idempotency_key="test-job-once",
        organization_id=None,
        created_by_user_id=None,
    )
    repeated = schedule_job(
        db_session,
        task_type="test.handler",
        payload={"value": 2},
        scheduled_at=scheduled_at,
        timezone="UTC",
        idempotency_key="test-job-once",
        organization_id=None,
        created_by_user_id=None,
    )
    assert repeated.id == first.id

    claimed = claim_due_job(db_session, worker_id="worker-a")
    assert claimed is not None
    mark_job_complete(db_session, claimed.id, "worker-a")
    assert db_session.get(ScheduledJob, claimed.id).status is ScheduledJobStatus.COMPLETED


def test_expired_lease_is_reclaimed_and_failed_jobs_retry(db_session) -> None:
    job = ScheduledJob(
        task_type="test.retry",
        payload={},
        scheduled_at=datetime.now(timezone.utc),
        timezone="UTC",
        idempotency_key="test-job-recovery",
        max_attempts=2,
        status=ScheduledJobStatus.RUNNING,
        lease_until=datetime.now(timezone.utc) - timedelta(seconds=1),
        worker_id="dead-worker",
    )
    db_session.add(job)
    db_session.commit()

    reclaimed = claim_due_job(db_session, worker_id="worker-b")
    assert reclaimed is not None
    assert reclaimed.worker_id == "worker-b"
    mark_job_failed(db_session, reclaimed, "temporary failure")
    db_session.refresh(reclaimed)
    assert reclaimed.status is ScheduledJobStatus.RETRYING
    assert reclaimed.retry_count == 1

    reclaimed.scheduled_at = datetime.now(timezone.utc)
    db_session.commit()
    reclaimed = claim_due_job(db_session, worker_id="worker-c")
    assert reclaimed is not None
    mark_job_failed(db_session, reclaimed, "permanent failure")
    db_session.refresh(reclaimed)
    assert reclaimed.status is ScheduledJobStatus.FAILED
    assert db_session.scalar(
        select(ScheduledJobExecution).where(
            ScheduledJobExecution.job_id == reclaimed.id,
            ScheduledJobExecution.status == ScheduledJobStatus.FAILED.value,
        )
    ) is not None


def test_worker_executes_registered_handler(db_session) -> None:
    received: list[dict] = []
    register_handler("test.worker", received.append)
    schedule_job(
        db_session,
        task_type="test.worker",
        payload={"job": "value"},
        scheduled_at=datetime.now(timezone.utc),
        timezone="UTC",
        idempotency_key="test-worker-handler",
        organization_id=None,
        created_by_user_id=None,
    )

    assert _run_once("worker-handler") is True
    assert received == [{"job": "value"}]
