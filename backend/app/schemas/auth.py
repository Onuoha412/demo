from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..models.entities import UserRole


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    organization_id: UUID | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class WebSocketTicketRequest(BaseModel):
    queue_id: UUID


class WebSocketTicketResponse(BaseModel):
    ticket: str
    expires_in: int = 30


class AuthUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: UserRole
    organization_id: UUID | None
    branch_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse
