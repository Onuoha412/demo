from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

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
    organization_name: str | None = Field(default=None, min_length=2, max_length=160)

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

    @field_validator("organization_name")
    @classmethod
    def clean_organization_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Organization must contain at least 2 characters")
        return value

    @model_validator(mode="after")
    def validate_organization_choice(self) -> "RegisterRequest":
        if self.organization_id is not None and self.organization_name is not None:
            raise ValueError("Choose an organization ID or organization name, not both")
        return self


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


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Full name must contain at least 2 characters")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


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
    avatar_url: str | None = None
    auth_provider: str = "local"
    email_verified: bool = False
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: AuthUserResponse
    session_token: str


class PendingOrganizationApprovalResponse(BaseModel):
    status: str = "pending_approval"
    email: str
    organization_name: str
    message: str


class ResetTokenStatus(BaseModel):
    valid: bool
    reason: str | None = None
