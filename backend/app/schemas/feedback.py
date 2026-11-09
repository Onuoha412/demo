from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCategory(str, Enum):
    GENERAL = "general"
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    UI_ACCESSIBILITY = "ui_accessibility"
    QUEUE_ACCURACY = "queue_accuracy"
    PERFORMANCE_CONNECTION = "performance_connection"
    SECURITY_PRIVACY = "security_privacy"
    ACCOUNT_LOGIN = "account_login"
    STAFF_SERVICE = "staff_service"
    ORGANIZATION_SETUP_MIGRATION = "organization_setup_migration"
    NOTIFICATION = "notification"
    OTHER = "other"


class FeedbackStatus(str, Enum):
    NEW = "new"
    UNDER_REVIEW = "under_review"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_INFORMATION = "waiting_for_information"
    RESOLVED = "resolved"
    DECLINED = "declined"
    DUPLICATE = "duplicate"


class FeedbackSubmit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: FeedbackCategory
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    improvement_suggestion: str | None = Field(default=None, max_length=3000)
    rating: int | None = Field(default=None, ge=1, le=5)
    is_anonymous: bool = False
    page_identifier: str | None = Field(default=None, max_length=160)
    app_version: str | None = Field(default=None, max_length=40)
    queue_context_entry_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=64)


class FeedbackReplyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=5000)


class FeedbackNoteCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=5000)


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus
    note: str | None = Field(default=None, max_length=1000)
    resolution_summary: str | None = Field(default=None, max_length=3000)
    release_version: str | None = Field(default=None, max_length=40)
    duplicate_of_id: UUID | None = None


class FeedbackAssignmentUpdate(BaseModel):
    assigned_to_user_id: UUID | None = None


class FeedbackPriorityUpdate(BaseModel):
    priority: int = Field(ge=1, le=5)
    severity: str = Field(pattern="^(low|medium|high|critical)$")


class FeedbackResolutionConfirmation(BaseModel):
    helpful: bool


class FeedbackImprovementTaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=1, max_length=5000)
    acceptance_criteria: str | None = Field(default=None, max_length=3000)
    priority: int = Field(default=3, ge=1, le=5)
    impact: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    affected_features: str | None = Field(default=None, max_length=500)
    target_release: str | None = Field(default=None, max_length=40)


class FeedbackImprovementTaskUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(reviewed|prioritized|assigned|implemented|tested|released|measured|declined)$",
    )
    acceptance_criteria: str | None = Field(default=None, max_length=3000)
    assigned_to_user_id: UUID | None = None
    target_release: str | None = Field(default=None, max_length=40)
    release_version: str | None = Field(default=None, max_length=40)
    verification_notes: str | None = Field(default=None, max_length=3000)
    post_release_outcome: str | None = Field(default=None, max_length=3000)


class FeedbackVoteResponse(BaseModel):
    voted: bool
    votes: int


class FeatureRequestResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    votes: int
    voted_by_current_user: bool
    created_at: datetime


class FeatureRequestPageResponse(BaseModel):
    items: list[FeatureRequestResponse]
    total: int
    page: int
    page_size: int


class FeedbackReplyResponse(BaseModel):
    id: UUID
    author_user_id: UUID | None
    body: str
    is_internal: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackStatusEventResponse(BaseModel):
    previous_status: str | None
    new_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackReportResponse(BaseModel):
    id: UUID
    reporter_user_id: UUID | None
    reporter_role: str | None
    organization_id: UUID | None
    branch_id: UUID | None
    assigned_to_user_id: UUID | None
    duplicate_of_id: UUID | None
    category: str
    title: str
    description: str
    improvement_suggestion: str | None
    rating: int | None
    is_anonymous: bool
    page_identifier: str | None
    app_version: str | None
    status: str
    priority: int
    severity: str
    reviewed_at: datetime | None
    assigned_at: datetime | None
    resolved_at: datetime | None
    resolution_summary: str | None
    release_version: str | None
    resolution_helpful: bool | None
    resolution_confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    vote_count: int = 0
    replies: list[FeedbackReplyResponse] = Field(default_factory=list)
    status_history: list[FeedbackStatusEventResponse] = Field(default_factory=list)


class FeedbackPageResponse(BaseModel):
    items: list[FeedbackReportResponse]
    total: int
    page: int
    page_size: int


class FeedbackMetricsResponse(BaseModel):
    total: int
    new: int
    unresolved: int
    average_rating: float | None
    resolution_confirmation_rate: float | None
    average_time_to_first_review_hours: float | None
    average_resolution_time_hours: float | None
    by_category: dict[str, int]
    by_status: dict[str, int]
    by_role: dict[str, int]
    by_severity: dict[str, int]
    by_application_area: dict[str, int]
    by_organization: dict[str, int]
    by_branch: dict[str, int]
