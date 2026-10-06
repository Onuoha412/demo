from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...api.auth_dependencies import get_current_user
from ...core.security import create_access_token, hash_password, verify_password
from ...db.session import get_db
from ...models import Queue, QueueEntry, User
from ...models.entities import UserRole
from ...services.cache import cache
from ...schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    WebSocketTicketRequest,
    WebSocketTicketResponse,
)
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        organization_id=payload.organization_id,
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=AuthUserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(
        access_token=create_access_token(user.id),
        user=AuthUserResponse.model_validate(user),
    )


@router.get("/me", response_model=AuthUserResponse)
def me(user: User = Depends(get_current_user)) -> AuthUserResponse:
    return AuthUserResponse.model_validate(user)


@router.post("/ws-ticket", response_model=WebSocketTicketResponse)
async def create_websocket_ticket(
    payload: WebSocketTicketRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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
