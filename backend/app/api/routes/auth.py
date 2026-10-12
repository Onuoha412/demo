import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...api.auth_dependencies import get_current_user
from ...auth.google import GoogleOAuthError, verify_google_credential
from ...auth.rate_limit import enforce_rate_limit
from ...auth.sessions import (
    clear_session_cookie,
    hash_opaque_token,
    new_session,
    revoke_session,
    set_session_cookie,
)
from ...config import settings
from ...core.security import hash_password, verify_password
from ...db.session import begin_write, get_db
from ...models import (
    AuthSession,
    PasswordResetToken,
    Queue,
    QueueEntry,
    User,
)
from ...models.entities import UserRole
from ...schemas.auth import (
    AuthResponse,
    AuthUserResponse,
    ForgotPasswordRequest,
    GoogleCredentialRequest,
    GoogleSignInChallenge,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetTokenStatus,
    WebSocketTicketRequest,
    WebSocketTicketResponse,
)
from ...services.cache import cache
from ...services.email import EmailDeliveryError, send_password_reset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_RESET_TOKEN_TTL = timedelta(minutes=30)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _limit(
    request: Request,
    db: Session,
    scope: str,
    limit: int,
    window_seconds: int = 60,
) -> None:
    if not enforce_rate_limit(db, scope, _client_key(request), limit, window_seconds):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a moment and try again.",
            headers={"Retry-After": str(window_seconds)},
        )


def _new_auth_response(db: Session, user: User, response: Response) -> AuthResponse:
    now = datetime.now(timezone.utc)
    user.last_login_at = now
    auth_session, raw_token = new_session(user)
    db.add(auth_session)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, raw_token)
    return AuthResponse(
        user=AuthUserResponse.model_validate(user),
        session_token=raw_token,
    )


def _reset_url(token: str) -> str:
    parts = urlsplit(settings.reset_password_url)
    separator = "&" if parts.query else ""
    query = f"{parts.query}{separator}{urlencode({'token': token})}"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    _limit(request, db, "register", settings.auth_rate_limit_register, 60)
    begin_write(db)
    exists = db.scalar(select(User.id).where(func.lower(User.email) == payload.email))
    if exists:
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        organization_id=payload.organization_id,
        role=UserRole.CUSTOMER,
        auth_provider="local",
    )
    now = datetime.now(timezone.utc)
    user.last_login_at = now
    auth_session, raw_token = new_session(user)
    db.add_all([user, auth_session])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.scalar(select(User.id).where(func.lower(User.email) == payload.email)):
            raise HTTPException(
                status_code=409, detail="Email is already registered"
            ) from None
        raise
    db.refresh(user)
    set_session_cookie(response, raw_token)
    return AuthResponse(
        user=AuthUserResponse.model_validate(user),
        session_token=raw_token,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    _limit(request, db, "login", settings.auth_rate_limit_login)
    user = db.scalar(
        select(User).where(func.lower(User.email) == payload.email)
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account has been disabled. Please contact support.",
        )
    return _new_auth_response(db, user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    token = (
        authorization.removeprefix("Bearer ").strip()
        if authorization and authorization.startswith("Bearer ")
        else request.cookies.get(settings.session_cookie_name)
    )
    if token:
        revoke_session(db, token)
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthUserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> AuthUserResponse:
    return AuthUserResponse.model_validate(user)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=dict[str, str],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    _limit(
        request,
        db,
        "forgot-password",
        settings.auth_rate_limit_reset,
        300,
    )
    user = db.scalar(
        select(User).where(func.lower(User.email) == payload.email)
    )
    if user is not None:
        now = datetime.now(timezone.utc)
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        raw_token = secrets.token_urlsafe(48)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=now + _RESET_TOKEN_TTL,
        )
        db.add(reset_token)
        db.commit()
        try:
            send_password_reset(payload.email, _reset_url(raw_token))
        except EmailDeliveryError:
            db.delete(reset_token)
            db.commit()
            logger.exception("QueueLess password reset email delivery failed")
    return {
        "message": "If an account exists for that email, password reset instructions have been sent."
    }


@router.get("/verify-reset-token", response_model=ResetTokenStatus)
def verify_reset_token(
    token: Annotated[str, Query(min_length=32, max_length=256)],
    db: Annotated[Session, Depends(get_db)],
) -> ResetTokenStatus:
    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_opaque_token(token)
        )
    )
    if reset_token is None:
        return ResetTokenStatus(valid=False, reason="invalid")
    if reset_token.used_at is not None:
        return ResetTokenStatus(valid=False, reason="used")
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return ResetTokenStatus(valid=False, reason="expired")
    return ResetTokenStatus(valid=True)


@router.post("/reset-password", response_model=dict[str, str])
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    _limit(request, db, "reset-password", settings.auth_rate_limit_reset, 300)
    begin_write(db)
    reset_token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_opaque_token(payload.token))
        .with_for_update()
    )
    if reset_token is None:
        raise HTTPException(status_code=400, detail="This password reset link is invalid.")
    if reset_token.used_at is not None:
        raise HTTPException(
            status_code=400, detail="This password reset link has already been used."
        )
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400, detail="Password reset link has expired."
        )

    now = datetime.now(timezone.utc)
    user = db.get(User, reset_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="This password reset link is invalid.")
    user.password_hash = hash_password(payload.password)
    reset_token.used_at = now
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != reset_token.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()
    return {"message": "Your password has been reset successfully."}


@router.post("/google/challenge", response_model=GoogleSignInChallenge)
async def google_sign_in_challenge(
    request: Request, db: Annotated[Session, Depends(get_db)]
) -> GoogleSignInChallenge:
    _limit(request, db, "google-login", settings.auth_rate_limit_login)
    client_id = settings.google_client_id
    if not client_id:
        raise HTTPException(status_code=503, detail="Google Sign-In is not configured.")
    nonce = secrets.token_urlsafe(32)
    await cache.issue_google_nonce(nonce)
    return GoogleSignInChallenge(client_id=client_id, nonce=nonce)


@router.post("/google/credential", response_model=AuthResponse)
async def google_credential(
    payload: GoogleCredentialRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    _limit(request, db, "google-login", settings.auth_rate_limit_login)
    if not await cache.consume_google_nonce(payload.nonce):
        raise HTTPException(status_code=401, detail="Google sign-in expired. Please try again.")
    try:
        claims = await verify_google_credential(payload.credential, payload.nonce)
    except GoogleOAuthError as oauth_error:
        logger.info("Google authentication was rejected: %s", oauth_error)
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified.") from oauth_error
    email = str(claims["email"]).strip().lower()
    google_id = str(claims["sub"])
    user = db.scalar(select(User).where(User.google_id == google_id))
    if user is None:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None and not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account has been disabled. Please contact support.",
        )
    if user is None:
        user = User(
            full_name=str(claims.get("name") or email.split("@", maxsplit=1)[0])[:160],
            email=email,
            password_hash="",
            google_id=google_id,
            avatar_url=_verified_avatar_url(claims.get("picture")),
            auth_provider="google",
            email_verified=True,
            role=UserRole.CUSTOMER,
        )
        db.add(user)
    else:
        if user.google_id not in (None, google_id):
            raise HTTPException(
                status_code=409,
                detail="This email is already linked to another Google account.",
            )
        user.google_id = google_id
        user.auth_provider = "google"
        user.email_verified = True
        user.avatar_url = _verified_avatar_url(claims.get("picture")) or user.avatar_url
    try:
        return _new_auth_response(db, user, response)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This Google account could not be linked. Please contact support.",
        ) from None


def _verified_avatar_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
        return value[:2048]
    return None


@router.post("/ws-ticket", response_model=WebSocketTicketResponse)
async def create_websocket_ticket(
    payload: WebSocketTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WebSocketTicketResponse:
    queue = db.scalar(select(Queue).where(Queue.id == payload.queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")
    if user.role is UserRole.CUSTOMER:
        joined = db.scalar(
            select(QueueEntry.id).where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.customer_id == user.id,
            )
        )
        if joined is None:
            raise HTTPException(status_code=403, detail="You are not a customer in this queue")
    elif user.role is UserRole.STAFF and queue.service.branch_id != user.branch_id:
        raise HTTPException(status_code=403, detail="Queue is outside your assigned branch")
    ticket = await cache.issue_websocket_ticket(str(user.id), str(queue.id))
    return WebSocketTicketResponse(ticket=ticket)
