from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import uuid4

from ..config import settings
from ..db.session import SessionLocal
from ..models import ScheduledJob
from .scheduler import claim_due_job, mark_job_complete, mark_job_failed

logger = logging.getLogger(__name__)
JobHandler = Callable[[dict], None]
_handlers: dict[str, JobHandler] = {}


def register_handler(task_type: str, handler: JobHandler) -> None:
    if not task_type.strip():
        raise ValueError("A job handler requires a task type.")
    _handlers[task_type] = handler


def _run_once(worker_id: str) -> bool:
    with SessionLocal() as session:
        job = claim_due_job(session, worker_id=worker_id)
        if job is None:
            return False
        job_id = job.id
        task_type = job.task_type
        payload = dict(job.payload)
        max_attempts = job.max_attempts

    handler = _handlers.get(task_type)
    if handler is None:
        error = f"No handler registered for scheduled job type {task_type!r}."
        with SessionLocal() as session:
            current = session.get(ScheduledJob, job_id)
            if current is not None:
                current.max_attempts = min(current.max_attempts, max_attempts)
                mark_job_failed(session, current, error)
        return True

    try:
        handler(payload)
    except Exception as error:
        logger.exception("Scheduled QueueLess job failed", extra={"task_type": task_type})
        with SessionLocal() as session:
            current = session.get(ScheduledJob, job_id)
            if current is not None:
                mark_job_failed(session, current, str(error))
    else:
        with SessionLocal() as session:
            mark_job_complete(session, job_id, worker_id)
    return True


async def worker_loop() -> None:
    worker_id = f"api-{uuid4()}"
    while True:
        try:
            claimed = await asyncio.to_thread(_run_once, worker_id)
            if not claimed:
                await asyncio.sleep(settings.scheduled_job_poll_interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled QueueLess worker failed")
            await asyncio.sleep(settings.scheduled_job_poll_interval_seconds)
