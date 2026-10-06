from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Queue


class QueueNumberService:
    """Allocates queue numbers while holding a row-level lock on the queue."""

    def next_number(self, session: Session, queue: Queue) -> int:
        locked_queue = session.scalar(
            select(Queue).where(Queue.id == queue.id).with_for_update()
        )
        if locked_queue is None:
            raise ValueError("Queue not found")
        locked_queue.current_number += 1
        session.flush()
        return locked_queue.current_number

    @staticmethod
    def reset_policy() -> str:
        return (
            "Numbers are monotonically increasing for the lifetime of a queue. "
            "A reset requires creating a new queue; automatic daily resets are "
            "intentionally not enabled until an explicit operating policy exists."
        )
