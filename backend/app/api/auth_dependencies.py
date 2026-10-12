from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException
from jose import JWTError
from sqlalchemy.orm import Session

from ..auth.sessions import user_for_session
from ..config import settings
from ..core.security import decode_access_token
from ..db.session import get_db
from ..models import User
from ..models.entities import UserRole


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> User:
    user: User | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
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


def require_staff(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role is not UserRole.STAFF:
        raise HTTPException(status_code=403, detail="Staff access required")
    if user.branch_id is None:
        raise HTTPException(status_code=403, detail="Staff member has no assigned branch")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Require an active platform administrator."""
    if user.role is not UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
