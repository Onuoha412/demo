from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..models.entities import UserRole


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(
        min_length=5,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=8, max_length=128)
    organization_id: UUID | None = None

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=8, max_length=128)

class WebSocketTicketRequest(BaseModel):
    queue_id: UUID


class WebSocketTicketResponse(BaseModel):
    ticket: str
    expires_in: int = 30


class GoogleSignInChallenge(BaseModel):
    client_id: str
    nonce: str


class GoogleCredentialRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)
    nonce: str = Field(min_length=32, max_length=128)


class AuthUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: UserRole
    organization_id: UUID | None
    branch_id: UUID | None
    created_at: datetime
    avatar_url: str | None = None
    auth_provider: str = "local"
    email_verified: bool = False
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: AuthUserResponse
    session_token: str


class ResetTokenStatus(BaseModel):
    valid: bool
    reason: str | None = None
