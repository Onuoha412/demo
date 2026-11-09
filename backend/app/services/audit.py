from uuid import UUID

from sqlalchemy.orm import Session

from ..models import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    target_type: str,
    actor_user_id: UUID | None = None,
    target_id: UUID | str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details or {},
        )
    )
