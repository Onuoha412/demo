import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuthSession, User

SESSION_COOKIE = settings.session_cookie_name


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session(user: User) -> tuple[AuthSession, str]:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    return (
        AuthSession(
            user=user,
            session_token_hash=hash_opaque_token(token),
            expires_at=now + timedelta(days=settings.session_expire_days),
            last_seen_at=now,
        ),
        token,
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.session_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def user_for_session(db: Session, token: str) -> User | None:
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.session_token_hash == hash_opaque_token(token),
            AuthSession.revoked_at.is_(None),
        )
    )
    if auth_session is None:
        return None
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return None
    return auth_session.user


def revoke_session(db: Session, token: str) -> None:
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.session_token_hash == hash_opaque_token(token),
            AuthSession.revoked_at.is_(None),
        )
    )
    if auth_session is not None:
        auth_session.revoked_at = datetime.now(timezone.utc)
        db.commit()
