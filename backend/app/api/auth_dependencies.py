from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.sessions import hash_opaque_token, user_for_session
from ..config import settings
from ..core.security import decode_access_token
from ..db.session import get_db
from ..models import (
    AuthSession,
    Branch,
    OrganizationMembership,
    Queue,
    QueueEntry,
    Service,
    User,
)
from ..models.entities import UserRole


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return value.strip()


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> User:
    user: User | None = None
    if authorization is not None:
        token = _bearer_token(authorization)
        assert token is not None
        user = user_for_session(db, token)
        if user is not None:
            if not user.is_active:
                raise HTTPException(status_code=401, detail="This account has been disabled.")
            return user
        try:
            user_id = decode_access_token(token)
        except (JWTError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid or expired token") from None
        user = db.get(User, user_id)
    elif session_cookie:
        user = user_for_session(db, session_cookie)
        if user is None:
            raise HTTPException(status_code=401, detail="Your session has expired.")
    else:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="This account has been disabled.")
    return user


def get_optional_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[
        str | None, Cookie(alias=settings.session_cookie_name)
    ] = None,
) -> User | None:
    """Resolve an optional session without treating invalid credentials as anonymous."""
    if authorization is None and session_cookie is None:
        return None
    if authorization is not None:
        token = _bearer_token(authorization)
        assert token is not None
        user = user_for_session(db, token)
        if user is None:
            try:
                user_id = decode_access_token(token)
            except (JWTError, ValueError):
                raise HTTPException(
                    status_code=401, detail="Invalid or expired token"
                ) from None
            user = db.get(User, user_id)
    else:
        user = user_for_session(db, session_cookie or "")
        if user is None:
            raise HTTPException(status_code=401, detail="Your session has expired.")
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="This account has been disabled.")
    return user


def require_staff(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role is not UserRole.STAFF:
        raise HTTPException(status_code=403, detail="Staff access required")
    if user.branch_id is None:
        raise HTTPException(status_code=403, detail="Staff member has no assigned branch")
    return user


def require_admin(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Require an active administrator or super administrator."""
    if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Admin access required")
    if (
        user.role is UserRole.ADMIN
        and user.organization_id is not None
        and not has_active_organization_admin_membership(db, user)
    ):
        raise HTTPException(
            status_code=403,
            detail="This administrator has no active membership in the organization.",
        )
    return user


def has_active_organization_admin_membership(
    db: Session,
    user: User,
) -> bool:
    if user.role is not UserRole.ADMIN or user.organization_id is None:
        return False
    membership = db.get(OrganizationMembership, (user.id, user.organization_id))
    return bool(
        membership is not None
        and membership.is_active
        and membership.role == UserRole.ADMIN.value
    )


def can_access_queue(db: Session, user: User, queue: Queue) -> bool:
    if user.role is UserRole.SUPER_ADMIN:
        return True
    if user.role is UserRole.STAFF:
        return user.branch_id is not None and queue.service.branch_id == user.branch_id
    if user.role is UserRole.ADMIN:
        if (
            user.organization_id is None
            or not has_active_organization_admin_membership(db, user)
        ):
            return False
        queue_organization_id = db.scalar(
            select(Branch.organization_id)
            .join(Service, Service.branch_id == Branch.id)
            .where(Service.id == queue.service_id)
        )
        return queue_organization_id == user.organization_id
    if user.role is UserRole.CUSTOMER:
        return (
            db.scalar(
                select(QueueEntry.id).where(
                    QueueEntry.queue_id == queue.id,
                    QueueEntry.customer_id == user.id,
                )
            )
            is not None
        )
    return False


def require_super_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role is not UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user


def require_recent_super_admin(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_super_admin)],
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[
        str | None, Cookie(alias=settings.session_cookie_name)
    ] = None,
) -> User:
    return _require_recent_session(db, user, authorization, session_cookie)


def require_admin_write_reauth(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[
        str | None, Cookie(alias=settings.session_cookie_name)
    ] = None,
) -> User:
    if request.method in {"GET", "HEAD", "OPTIONS"} or user.role is UserRole.ADMIN:
        return user
    return _require_recent_session(db, user, authorization, session_cookie)


def _require_recent_session(
    db: Session,
    user: User,
    authorization: str | None,
    session_cookie: str | None,
) -> User:
    token = (
        _bearer_token(authorization)
        if authorization is not None
        else session_cookie
    )
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.session_token_hash == hash_opaque_token(token),
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
    )
    if auth_session is None:
        raise HTTPException(status_code=401, detail="Your session has expired.")
    created_at = auth_session.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > timedelta(minutes=5):
        raise HTTPException(
            status_code=403,
            detail="Sign in again before performing this sensitive action.",
        )
    return user
