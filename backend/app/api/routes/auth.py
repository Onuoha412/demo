import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...api.auth_dependencies import (
    _bearer_token,
    can_access_queue,
    get_current_user,
)
from ...auth.rate_limit import enforce_rate_limit
from ...auth.sessions import (
    clear_session_cookie,
    hash_opaque_token,
    new_session,
    set_session_cookie,
)
from ...config import settings
from ...core.security import hash_password, verify_password
from ...db.session import get_db
from ...models import (
    AuthSession,
    Organization,
    PasswordResetToken,
    Queue,
    User,
)
from ...models.entities import UserRole
from ...schemas.auth import (
    AuthResponse,
    AuthUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    ChangePasswordRequest,
    PendingOrganizationApprovalResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResetTokenStatus,
    WebSocketTicketRequest,
    WebSocketTicketResponse,
)
from ...services.cache import cache
from ...services.audit import record_audit
from ...services.email import EmailDeliveryError, send_password_reset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_RESET_TOKEN_TTL = timedelta(minutes=30)
_PENDING_ORGANIZATION_MESSAGE = (
    "Your organization request and account are awaiting administrator approval. "
    "You can sign in after the organization is approved."
)


def _organization_slug(name: str) -> str:
    slug = re.sub(r"[^\w]+", "-", name.casefold(), flags=re.UNICODE).strip("-")
    if not slug:
        raise HTTPException(
            status_code=422,
            detail="Enter an organization name containing letters or numbers.",
        )
    return slug[:160].rstrip("-")


def _requires_organization_approval(user: User) -> bool:
    return user.approval_pending or (
        user.organization is not None and not user.organization.is_approved
    )


def _inactive_account_detail(user: User) -> str:
    if _requires_organization_approval(user):
        return _PENDING_ORGANIZATION_MESSAGE
    return "This account has been disabled. Please contact support."


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
    db.flush()
    auth_session, raw_token = new_session(user)
    db.add(auth_session)
    record_audit(
        db,
        actor_user_id=user.id,
        action="auth.login_succeeded",
        target_type="user",
        target_id=user.id,
        details={"provider": user.auth_provider},
    )
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


@router.post(
    "/register",
    response_model=AuthResponse | PendingOrganizationApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse | PendingOrganizationApprovalResponse:
    _limit(request, db, "register", settings.auth_rate_limit_register, 60)
    exists = db.scalar(select(User.id).where(func.lower(User.email) == payload.email))
    if exists:
        raise HTTPException(status_code=409, detail="Email is already registered")
    organization: Organization | None = None
    approval_pending = False
    if payload.organization_id is not None:
        organization = db.get(Organization, payload.organization_id)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found.")
        if not organization.is_active or not organization.is_approved:
            raise HTTPException(
                status_code=403,
                detail="This organization is not accepting registrations.",
            )
    elif payload.organization_name is not None:
        slug = _organization_slug(payload.organization_name)
        organization = db.scalar(
            select(Organization).where(
                (Organization.name == payload.organization_name)
                | (
                    func.lower(Organization.name)
                    == payload.organization_name.casefold()
                )
            )
        )
        if organization is None:
            slug_owner = db.scalar(
                select(Organization).where(Organization.slug == slug)
            )
            if slug_owner is not None:
                if slug_owner.name.casefold() == payload.organization_name.casefold():
                    organization = slug_owner
                else:
                    raise HTTPException(
                        status_code=409,
                        detail="An organization with a similar name already exists. Select its exact name.",
                    )
        if organization is not None:
            if not organization.is_approved or not organization.is_active:
                approval_pending = not organization.is_approved
                if not approval_pending:
                    raise HTTPException(
                        status_code=403,
                        detail="This organization is not accepting registrations.",
                    )
        else:
            organization = Organization(
                name=payload.organization_name,
                slug=slug,
                is_active=False,
                is_approved=False,
            )
            db.add(organization)
            db.flush()
            approval_pending = True

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        organization_id=organization.id if organization else None,
        role=UserRole.CUSTOMER,
        auth_provider="local",
        is_active=not approval_pending,
        approval_pending=approval_pending,
    )
    db.add(user)
    try:
        if approval_pending:
            db.commit()
            response.status_code = status.HTTP_202_ACCEPTED
            return PendingOrganizationApprovalResponse(
                email=user.email,
                organization_name=organization.name if organization else "",
                message=_PENDING_ORGANIZATION_MESSAGE,
            )

        now = datetime.now(timezone.utc)
        user.last_login_at = now
        db.flush()
        auth_session, raw_token = new_session(user)
        db.add(auth_session)
        record_audit(
            db,
            actor_user_id=user.id,
            action="auth.account_registered",
            target_type="user",
            target_id=user.id,
            details={"provider": user.auth_provider},
        )
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
        record_audit(
            db,
            action="auth.login_failed",
            target_type="auth_attempt",
            target_id=hash_opaque_token(payload.email),
            details={"reason": "invalid_credentials"},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active or _requires_organization_approval(user):
        record_audit(
            db,
            actor_user_id=user.id,
            action="auth.login_denied",
            target_type="user",
            target_id=user.id,
            details={"reason": "account_unavailable"},
        )
        db.commit()
        raise HTTPException(
            status_code=403,
            detail=_inactive_account_detail(user),
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
        _bearer_token(authorization)
        if authorization is not None
        else request.cookies.get(settings.session_cookie_name)
    )
    if token:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.session_token_hash == hash_opaque_token(token),
                AuthSession.revoked_at.is_(None),
            )
        )
        if session is not None:
            session.revoked_at = datetime.now(timezone.utc)
            record_audit(
                db,
                actor_user_id=session.user_id,
                action="auth.logout",
                target_type="user",
                target_id=session.user_id,
            )
            db.commit()
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthUserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> AuthUserResponse:
    return AuthUserResponse.model_validate(user)


@router.patch("/me", response_model=AuthUserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthUserResponse:
    user.full_name = payload.full_name
    record_audit(
        db,
        actor_user_id=user.id,
        action="auth.profile_updated",
        target_type="user",
        target_id=user.id,
        details={"fields": ["full_name"]},
    )
    db.commit()
    db.refresh(user)
    return AuthUserResponse.model_validate(user)


@router.post("/change-password", response_model=dict[str, str])
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    _limit(request, db, "change-password", settings.auth_rate_limit_reset, 300)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    raw_token = (
        _bearer_token(authorization)
        if authorization is not None
        else request.cookies.get(settings.session_cookie_name)
    )
    if not raw_token:
        raise HTTPException(status_code=401, detail="Sign in again to change your password.")
    current_session = db.scalar(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.session_token_hash == hash_opaque_token(raw_token),
            AuthSession.revoked_at.is_(None),
        )
    )
    if current_session is None:
        raise HTTPException(status_code=401, detail="Your session has expired.")

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.id != current_session.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    record_audit(
        db,
        actor_user_id=user.id,
        action="auth.password_changed",
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    return {"message": "Password changed. Other active sessions have been signed out."}


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
        record_audit(
            db,
            actor_user_id=user.id,
            action="auth.password_reset_requested",
            target_type="user",
            target_id=user.id,
        )
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
    if db.get_bind().dialect.name == "sqlite":
        db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.token_hash == hash_opaque_token(payload.token))
            .values(used_at=PasswordResetToken.used_at)
        )
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
    record_audit(
        db,
        actor_user_id=user.id,
        action="auth.password_reset_completed",
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    return {"message": "Your password has been reset successfully."}


@router.post("/ws-ticket", response_model=WebSocketTicketResponse)
async def create_websocket_ticket(
    payload: WebSocketTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> WebSocketTicketResponse:
    queue = db.scalar(select(Queue).where(Queue.id == payload.queue_id))
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")
    if not can_access_queue(db, user, queue):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to receive updates for this queue.",
        )
    ticket = await cache.issue_websocket_ticket(str(user.id), str(queue.id))
    return WebSocketTicketResponse(ticket=ticket)


@router.post("/announcements-ws-ticket", response_model=WebSocketTicketResponse)
async def create_announcements_websocket_ticket(
    user: Annotated[User, Depends(get_current_user)],
) -> WebSocketTicketResponse:
    ticket = await cache.issue_websocket_ticket(str(user.id), "announcements")
    return WebSocketTicketResponse(ticket=ticket)
