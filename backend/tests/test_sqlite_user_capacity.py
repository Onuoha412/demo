import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def test_sqlite_stores_and_retrieves_750_users(db_session: Session) -> None:
    run_id = uuid.uuid4().hex
    users = [
        User(
            full_name=f"Capacity User {index}",
            email=f"capacity-{run_id}-{index}@example.invalid",
            password_hash="capacity-test-hash",
        )
        for index in range(750)
    ]
    db_session.add_all(users)
    db_session.commit()

    total = db_session.scalar(
        select(func.count(User.id)).where(User.email.like(f"capacity-{run_id}-%"))
    )
    assert total == 750

    retrieved: list[str] = []
    for offset in range(0, 750, 100):
        retrieved.extend(
            db_session.scalars(
                select(User.email)
                .where(User.email.like(f"capacity-{run_id}-%"))
                .order_by(User.email)
                .offset(offset)
                .limit(100)
            )
        )

    assert len(retrieved) == 750
    assert len(set(retrieved)) == 750
