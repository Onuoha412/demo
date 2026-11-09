import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...api.auth_dependencies import (
    get_current_user,
    get_optional_current_user,
    require_admin,
    require_admin_write_reauth,
)
from ...auth.rate_limit import enforce_rate_limit
from ...db.session import get_db
from ...models import (
    Branch,
    FeedbackImprovementTask,
    FeedbackReply,
    FeedbackReport,
    FeedbackStatusHistory,
    FeedbackTaskLink,
    FeedbackVote,
    OrganizationMembership,
    QueueEntry,
    User,
)
from ...models.entities import UserRole
from ...schemas.feedback import (
    FeedbackAssignmentUpdate,
    FeatureRequestPageResponse,
    FeedbackImprovementTaskCreate,
    FeedbackImprovementTaskUpdate,
    FeedbackMetricsResponse,
    FeedbackNoteCreate,
    FeedbackPageResponse,
    FeedbackPriorityUpdate,
    FeedbackReplyCreate,
    FeedbackReportResponse,
    FeedbackResolutionConfirmation,
    FeedbackStatus,
    FeedbackStatusUpdate,
    FeedbackSubmit,
    FeedbackVoteResponse,
)
from ...services.audit import record_audit
from ...services.cache import cache
from ...services.realtime import realtime

router = APIRouter(prefix="/feedback", tags=["feedback"])

_TRANSITIONS: dict[str, set[str]] = {
    "new": {"under_review", "declined", "duplicate"},
    "under_review": {
        "planned",
        "in_progress",
        "waiting_for_information",
        "resolved",
        "declined",
        "duplicate",
    },
    "planned": {"in_progress", "declined", "duplicate"},
    "in_progress": {"waiting_for_information", "resolved", "declined", "duplicate"},
    "waiting_for_information": {
        "under_review",
        "in_progress",
        "resolved",
        "declined",
        "duplicate",
    },
    "resolved": {"under_review"},
    "declined": {"under_review"},
    "duplicate": {"under_review"},
}
_TASK_TRANSITIONS: dict[str, set[str]] = {
    "reviewed": {"prioritized", "declined"},
    "prioritized": {"assigned", "declined"},
    "assigned": {"implemented", "declined"},
    "implemented": {"tested"},
    "tested": {"released", "implemented"},
    "released": {"measured"},
    "measured": set(),
    "declined": {"reviewed"},
}


def _is_admin(user: User) -> bool:
    return user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)


def _visible(report: FeedbackReport, user: User) -> bool:
    if report.reporter_user_id == user.id:
        return True
    if user.role is UserRole.SUPER_ADMIN:
        return True
    if report.category == "security_privacy":
        return False
    if report.assigned_to_user_id == user.id:
        return True
    if user.role is UserRole.ADMIN:
        return (
            user.organization_id is not None
            and report.organization_id == user.organization_id
        )
    return False


def _get_visible_report(db: Session, report_id: UUID, user: User) -> FeedbackReport:
    report = db.get(FeedbackReport, report_id)
    if report is None or not _visible(report, user):
        raise HTTPException(status_code=404, detail="Feedback report not found.")
    return report


def _response(
    db: Session,
    report: FeedbackReport,
    *,
    include_internal: bool,
) -> FeedbackReportResponse:
    replies = list(
        db.scalars(
            select(FeedbackReply)
            .where(
                FeedbackReply.report_id == report.id,
            )
            .order_by(FeedbackReply.created_at)
        )
    )
    if not include_internal:
        replies = [reply for reply in replies if not reply.is_internal]
    history = list(
        db.scalars(
            select(FeedbackStatusHistory)
            .where(FeedbackStatusHistory.report_id == report.id)
            .order_by(FeedbackStatusHistory.created_at)
        )
    )
    return FeedbackReportResponse(
        id=report.id,
        reporter_user_id=report.reporter_user_id,
        reporter_role=report.reporter_role,
        organization_id=report.organization_id,
        branch_id=report.branch_id,
        assigned_to_user_id=report.assigned_to_user_id,
        duplicate_of_id=report.duplicate_of_id,
        category=report.category,
        title=report.title,
        description=report.description,
        improvement_suggestion=report.improvement_suggestion,
        rating=report.rating,
        is_anonymous=report.is_anonymous,
        page_identifier=report.page_identifier,
        app_version=report.app_version,
        status=report.status,
        priority=report.priority,
        severity=report.severity,
        reviewed_at=report.reviewed_at,
        assigned_at=report.assigned_at,
        resolved_at=report.resolved_at,
        resolution_summary=report.resolution_summary,
        release_version=report.release_version,
        resolution_helpful=report.resolution_helpful,
        resolution_confirmed_at=report.resolution_confirmed_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        vote_count=(
            db.scalar(
                select(func.count(FeedbackVote.user_id)).where(
                    FeedbackVote.report_id == report.id
                )
            )
            or 0
        ),
        replies=replies,
        status_history=history,
    )


def _page(
    db: Session,
    reports: list[FeedbackReport],
    total: int,
    page: int,
    page_size: int,
    *,
    include_internal: bool,
) -> FeedbackPageResponse:
    return FeedbackPageResponse(
        items=[
            _response(db, report, include_internal=include_internal)
            for report in reports
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _publish_report(report: FeedbackReport, event: str) -> None:
    realtime.publish_feedback_nowait(
        report_id=report.id,
        reporter_user_id=report.reporter_user_id,
        assigned_user_id=report.assigned_to_user_id,
        organization_id=report.organization_id,
        category=report.category,
        event=event,
        status=report.status,
    )


def _managed_scope(user: User):
    if user.role is UserRole.SUPER_ADMIN:
        return True
    if user.role is not UserRole.ADMIN or user.organization_id is None:
        return False
    return (
        FeedbackReport.organization_id == user.organization_id,
        FeedbackReport.category != "security_privacy",
    )


def _authorized_assignee(db: Session, user: User, assignee_id: UUID) -> User:
    assignee = db.get(User, assignee_id)
    if assignee is None or not assignee.is_active or assignee.role not in (
        UserRole.STAFF,
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    ):
        raise HTTPException(status_code=422, detail="Choose an active team member.")
    if user.role is UserRole.SUPER_ADMIN:
        return assignee
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="No organization is assigned to you.")
    same_org = assignee.organization_id == user.organization_id
    if assignee.branch_id is not None:
        branch_org = db.scalar(
            select(Branch.organization_id).where(Branch.id == assignee.branch_id)
        )
        same_org = same_org or branch_org == user.organization_id
    membership = db.get(
        OrganizationMembership, (assignee.id, user.organization_id)
    )
    same_org = same_org or bool(membership and membership.is_active)
    if not same_org:
        raise HTTPException(
            status_code=403,
            detail="The assignee must belong to your organization.",
        )
    return assignee


def _apply_report_filters(
    query,
    *,
    category: str | None,
    report_status: str | None,
    priority: int | None,
    branch_id: UUID | None,
    search: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
):
    if category:
        query = query.where(FeedbackReport.category == category)
    if report_status:
        query = query.where(FeedbackReport.status == report_status)
    if priority is not None:
        query = query.where(FeedbackReport.priority == priority)
    if branch_id is not None:
        query = query.where(FeedbackReport.branch_id == branch_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            FeedbackReport.title.ilike(term) | FeedbackReport.description.ilike(term)
        )
    if start_date is not None:
        query = query.where(FeedbackReport.created_at >= start_date)
    if end_date is not None:
        query = query.where(FeedbackReport.created_at < end_date)
    return query


def _elapsed_hours(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0.0, (end - start).total_seconds() / 3600)


@router.post("", response_model=FeedbackReportResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackSubmit,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> FeedbackReportResponse:
    client_key = request.client.host if request.client else "unknown"
    ip_allowed = enforce_rate_limit(db, "feedback.submit.ip", client_key, 20, 600)
    user_allowed = user is None or enforce_rate_limit(
        db, "feedback.submit.user", str(user.id), 5, 600
    )
    if not ip_allowed or not user_allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many feedback submissions. Please try again later.",
            headers={"Retry-After": "600"},
        )
    if payload.idempotency_key:
        existing = db.scalar(
            select(FeedbackReport).where(
                FeedbackReport.idempotency_key == payload.idempotency_key
            )
        )
        if existing is not None:
            existing_owner = existing.reporter_user_id
            if existing_owner == (user.id if user and not payload.is_anonymous else None):
                return _response(
                    db,
                    existing,
                    include_internal=bool(user and _is_admin(user)),
                )
            raise HTTPException(status_code=409, detail="This submission key was already used.")

    contextual_branch_id = None
    contextual_organization_id = None
    if payload.queue_context_entry_id is not None:
        if user is None or payload.is_anonymous or user.role is not UserRole.CUSTOMER:
            raise HTTPException(
                status_code=422,
                detail="Queue context requires a signed-in customer and cannot be anonymous.",
            )
        entry = db.scalar(
            select(QueueEntry).where(
                QueueEntry.id == payload.queue_context_entry_id,
                QueueEntry.customer_id == user.id,
            )
        )
        if entry is None:
            raise HTTPException(status_code=404, detail="Queue context not found.")
        contextual_branch_id = entry.queue.service.branch_id
        contextual_organization_id = entry.queue.service.branch.organization_id

    if payload.is_anonymous or user is None:
        reporter_user_id = None
        reporter_role = None
        organization_id = None
        branch_id = None
    else:
        reporter_user_id = user.id
        reporter_role = user.role.value
        organization_id = contextual_organization_id or user.organization_id
        branch_id = contextual_branch_id or user.branch_id

    now = datetime.now(timezone.utc)
    report = FeedbackReport(
        reporter_user_id=reporter_user_id,
        reporter_role=reporter_role,
        organization_id=organization_id,
        branch_id=branch_id,
        category=payload.category.value,
        title=payload.title.strip(),
        description=payload.description.strip(),
        improvement_suggestion=(
            payload.improvement_suggestion.strip()
            if payload.improvement_suggestion
            else None
        ),
        rating=payload.rating,
        is_anonymous=payload.is_anonymous or user is None,
        page_identifier=payload.page_identifier,
        app_version=payload.app_version,
        idempotency_key=payload.idempotency_key,
        severity="high" if payload.category.value == "security_privacy" else "low",
        priority=1 if payload.category.value == "security_privacy" else 3,
    )
    db.add(report)
    db.flush()
    db.add(
        FeedbackStatusHistory(
            report_id=report.id,
            actor_user_id=reporter_user_id,
            previous_status=None,
            new_status="new",
            created_at=now,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if payload.idempotency_key is None:
            raise
        existing = db.scalar(
            select(FeedbackReport).where(
                FeedbackReport.idempotency_key == payload.idempotency_key
            )
        )
        if existing is None:
            raise
        existing_owner = existing.reporter_user_id
        if existing_owner != (
            user.id if user is not None and not payload.is_anonymous else None
        ):
            raise HTTPException(
                status_code=409,
                detail="This submission key was already used.",
            ) from None
        return _response(
            db,
            existing,
            include_internal=bool(user and _is_admin(user)),
        )
    db.refresh(report)
    _publish_report(report, "feedback.created")
    return _response(
        db,
        report,
        include_internal=bool(user and _is_admin(user)),
    )


@router.post("/ws-ticket")
async def create_feedback_websocket_ticket(
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    return {
        "ticket": await cache.issue_websocket_ticket(str(user.id), "feedback")
    }


@router.get("/mine", response_model=FeedbackPageResponse)
def my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackPageResponse:
    query = select(FeedbackReport).where(FeedbackReport.reporter_user_id == user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    reports = list(
        db.scalars(
            query.order_by(FeedbackReport.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return _page(db, reports, total, page, page_size, include_internal=False)


@router.get("/features", response_model=FeatureRequestPageResponse)
def feature_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
) -> FeatureRequestPageResponse:
    eligible = (
        FeedbackReport.category == "feature_request",
        FeedbackReport.status.in_(("planned", "in_progress")),
    )
    total = db.scalar(
        select(func.count(FeedbackReport.id)).where(*eligible)
    ) or 0
    vote_counts = (
        select(
            FeedbackVote.report_id,
            func.count(FeedbackVote.user_id).label("votes"),
        )
        .group_by(FeedbackVote.report_id)
        .subquery()
    )
    rows = list(
        db.execute(
            select(FeedbackReport, func.coalesce(vote_counts.c.votes, 0))
            .outerjoin(vote_counts, vote_counts.c.report_id == FeedbackReport.id)
            .where(*eligible)
            .order_by(
                func.coalesce(vote_counts.c.votes, 0).desc(),
                FeedbackReport.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    voted_ids: set[UUID] = set()
    if user is not None and rows:
        voted_ids = set(
            db.scalars(
                select(FeedbackVote.report_id).where(
                    FeedbackVote.user_id == user.id,
                    FeedbackVote.report_id.in_([report.id for report, _ in rows]),
                )
            )
        )
    return FeatureRequestPageResponse(
        items=[
            {
                "id": report.id,
                "title": report.title,
                "description": report.description,
                "status": report.status,
                "votes": vote_count,
                "voted_by_current_user": report.id in voted_ids,
                "created_at": report.created_at,
            }
            for report, vote_count in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/managed", response_model=FeedbackPageResponse)
def managed_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(default="newest", pattern="^(newest|priority|votes)$"),
    category: str | None = None,
    report_status: FeedbackStatus | None = Query(default=None, alias="status"),
    priority: int | None = Query(default=None, ge=1, le=5),
    branch_id: UUID | None = None,
    search: str | None = Query(default=None, max_length=100),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> FeedbackPageResponse:
    if category and category not in {
        "general",
        "bug",
        "feature_request",
        "ui_accessibility",
        "queue_accuracy",
        "performance_connection",
        "security_privacy",
        "account_login",
        "staff_service",
        "organization_setup_migration",
        "notification",
        "other",
    }:
        raise HTTPException(status_code=422, detail="Unknown feedback category.")
    if start_date and end_date and start_date >= end_date:
        raise HTTPException(status_code=422, detail="Date range must have start before end.")
    query = select(FeedbackReport)
    scope = _managed_scope(user)
    if scope is not True:
        if scope is False:
            query = query.where(False)
        else:
            query = query.where(*scope)
    query = _apply_report_filters(
        query,
        category=category,
        report_status=report_status.value if report_status else None,
        priority=priority,
        branch_id=branch_id,
        search=search,
        start_date=start_date,
        end_date=end_date,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    if sort_by == "priority":
        query = query.order_by(
            FeedbackReport.priority.asc(), FeedbackReport.created_at.desc()
        )
    elif sort_by == "votes":
        vote_counts = (
            select(
                FeedbackVote.report_id,
                func.count(FeedbackVote.user_id).label("vote_count"),
            )
            .group_by(FeedbackVote.report_id)
            .subquery()
        )
        query = (
            query.outerjoin(vote_counts, vote_counts.c.report_id == FeedbackReport.id)
            .order_by(
                func.coalesce(vote_counts.c.vote_count, 0).desc(),
                FeedbackReport.created_at.desc(),
            )
        )
    else:
        query = query.order_by(FeedbackReport.created_at.desc())
    reports = list(
        db.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        )
    )
    return _page(db, reports, total, page, page_size, include_internal=True)


@router.get("/metrics", response_model=FeedbackMetricsResponse)
def feedback_metrics(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> FeedbackMetricsResponse:
    if start_date and end_date and start_date >= end_date:
        raise HTTPException(status_code=422, detail="Date range must have start before end.")
    query = select(
        FeedbackReport.category,
        FeedbackReport.status,
        FeedbackReport.reporter_role,
        FeedbackReport.rating,
        FeedbackReport.resolution_helpful,
        FeedbackReport.severity,
        FeedbackReport.page_identifier,
        FeedbackReport.organization_id,
        FeedbackReport.branch_id,
        FeedbackReport.created_at,
        FeedbackReport.reviewed_at,
        FeedbackReport.resolved_at,
    )
    scope = _managed_scope(user)
    if scope is not True:
        if scope is False:
            query = query.where(False)
        else:
            query = query.where(*scope)
    query = _apply_report_filters(
        query,
        category=None,
        report_status=None,
        priority=None,
        branch_id=None,
        search=None,
        start_date=start_date,
        end_date=end_date,
    )
    rows = list(db.execute(query))
    category_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    application_counts: dict[str, int] = {}
    organization_counts: dict[str, int] = {}
    branch_counts: dict[str, int] = {}
    ratings: list[int] = []
    confirmations: list[bool] = []
    review_durations: list[float] = []
    resolution_durations: list[float] = []
    new_count = 0
    unresolved_count = 0
    for (
        category,
        report_status,
        reporter_role,
        rating,
        resolution_helpful,
        severity,
        page_identifier,
        organization_id,
        branch_id,
        created_at,
        reviewed_at,
        resolved_at,
    ) in rows:
        category_counts[category] = category_counts.get(category, 0) + 1
        status_counts[report_status] = status_counts.get(report_status, 0) + 1
        role = reporter_role or "anonymous"
        role_counts[role] = role_counts.get(role, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        area = page_identifier or "not_recorded"
        application_counts[area] = application_counts.get(area, 0) + 1
        organization = str(organization_id) if organization_id else "not_recorded"
        organization_counts[organization] = organization_counts.get(organization, 0) + 1
        branch = str(branch_id) if branch_id else "not_recorded"
        branch_counts[branch] = branch_counts.get(branch, 0) + 1
        if rating is not None:
            ratings.append(rating)
        if resolution_helpful is not None:
            confirmations.append(resolution_helpful)
        if reviewed_at is not None:
            review_durations.append(_elapsed_hours(created_at, reviewed_at))
        if resolved_at is not None:
            resolution_durations.append(_elapsed_hours(created_at, resolved_at))
        new_count += report_status == "new"
        unresolved_count += report_status not in {"resolved", "declined", "duplicate"}
    return FeedbackMetricsResponse(
        total=len(rows),
        new=new_count,
        unresolved=unresolved_count,
        average_rating=(
            round(sum(ratings) / len(ratings), 2) if ratings else None
        ),
        resolution_confirmation_rate=(
            round(
                sum(helpful is True for helpful in confirmations)
                / len(confirmations)
                * 100,
                2,
            )
            if confirmations
            else None
        ),
        average_time_to_first_review_hours=(
            round(sum(review_durations) / len(review_durations), 2)
            if review_durations
            else None
        ),
        average_resolution_time_hours=(
            round(sum(resolution_durations) / len(resolution_durations), 2)
            if resolution_durations
            else None
        ),
        by_category=category_counts,
        by_status=status_counts,
        by_role=role_counts,
        by_severity=severity_counts,
        by_application_area=application_counts,
        by_organization=organization_counts,
        by_branch=branch_counts,
    )


@router.get("/reviewers")
def list_feedback_reviewers(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> list[dict[str, object]]:
    query = select(User).where(
        User.is_active.is_(True),
        User.role.in_([UserRole.STAFF, UserRole.ADMIN, UserRole.SUPER_ADMIN]),
    )
    if user.role is not UserRole.SUPER_ADMIN:
        if user.organization_id is None:
            return []
        organization_branches = select(Branch.id).where(
            Branch.organization_id == user.organization_id
        )
        organization_members = select(OrganizationMembership.user_id).where(
            OrganizationMembership.organization_id == user.organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        query = query.where(
            or_(
                User.organization_id == user.organization_id,
                User.branch_id.in_(organization_branches),
                User.id.in_(organization_members),
            )
        )
    return [
        {"id": member.id, "full_name": member.full_name, "role": member.role.value}
        for member in db.scalars(query.order_by(User.full_name))
    ]


@router.get("/branches")
def list_feedback_branches(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> list[dict[str, object]]:
    query = select(Branch)
    if user.role is not UserRole.SUPER_ADMIN:
        if user.organization_id is None:
            return []
        query = query.where(Branch.organization_id == user.organization_id)
    return [
        {"id": branch.id, "name": branch.name}
        for branch in db.scalars(query.order_by(Branch.name))
    ]


@router.get("/export.csv")
def export_feedback(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    query = select(FeedbackReport)
    scope = _managed_scope(user)
    if scope is not True:
        if scope is False:
            query = query.where(False)
        else:
            query = query.where(*scope)
    reports = list(db.scalars(query.order_by(FeedbackReport.created_at.desc())))
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        ["id", "category", "title", "description", "role", "status", "priority", "created_at"]
    )
    for report in reports:
        cells = [
            str(report.id),
            report.category,
            report.title,
            report.description,
            report.reporter_role or "anonymous",
            report.status,
            str(report.priority),
            report.created_at.isoformat(),
        ]
        writer.writerow(
            [
                f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value
                for value in cells
            ]
        )
    record_audit(
        db,
        actor_user_id=user.id,
        action="feedback.exported",
        target_type="feedback_reports",
        details={"count": len(reports)},
    )
    db.commit()
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="feedback.csv"'},
    )


@router.get("/{report_id:uuid}", response_model=FeedbackReportResponse)
def get_feedback(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackReportResponse:
    report = _get_visible_report(db, report_id, user)
    return _response(db, report, include_internal=_is_admin(user))


@router.post("/{report_id:uuid}/replies", response_model=FeedbackReportResponse)
def add_reply(
    report_id: UUID,
    payload: FeedbackReplyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackReportResponse:
    report = _get_visible_report(db, report_id, user)
    db.add(
        FeedbackReply(
            report_id=report.id,
            author_user_id=user.id,
            body=payload.body.strip(),
            is_internal=False,
        )
    )
    db.commit()
    db.refresh(report)
    _publish_report(report, "feedback.reply_added")
    return _response(db, report, include_internal=_is_admin(user))


@router.post("/{report_id:uuid}/notes", response_model=FeedbackReportResponse)
def add_internal_note(
    report_id: UUID,
    payload: FeedbackNoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_write_reauth),
) -> FeedbackReportResponse:
    report = _get_visible_report(db, report_id, user)
    db.add(
        FeedbackReply(
            report_id=report.id,
            author_user_id=user.id,
            body=payload.body.strip(),
            is_internal=True,
        )
    )
    record_audit(
        db,
        actor_user_id=user.id,
        action="feedback.internal_note_added",
        target_type="feedback_report",
        target_id=report.id,
    )
    db.commit()
    db.refresh(report)
    return _response(db, report, include_internal=True)


@router.patch("/{report_id:uuid}/status", response_model=FeedbackReportResponse)
def update_feedback_status(
    report_id: UUID,
    payload: FeedbackStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_write_reauth),
) -> FeedbackReportResponse:
    report = _get_visible_report(db, report_id, user)
    next_status = payload.status.value
    if next_status != report.status and next_status not in _TRANSITIONS[report.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Feedback cannot move from {report.status} to {next_status}.",
        )
    if next_status == "resolved" and not (
        payload.resolution_summary and payload.resolution_summary.strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="A resolution summary is required before resolving feedback.",
        )
    if next_status == "duplicate":
        if payload.duplicate_of_id is None or payload.duplicate_of_id == report.id:
            raise HTTPException(
                status_code=422,
                detail="Choose a different report to mark as the duplicate of.",
            )
        duplicate_target = _get_visible_report(db, payload.duplicate_of_id, user)
        if duplicate_target.status == "duplicate":
            raise HTTPException(
                status_code=422,
                detail="A duplicate cannot point to another duplicate report.",
            )
        report.duplicate_of_id = duplicate_target.id
    previous_status = report.status
    now = datetime.now(timezone.utc)
    if next_status != previous_status:
        report.status = next_status
        db.add(
            FeedbackStatusHistory(
                report_id=report.id,
                actor_user_id=user.id,
                previous_status=previous_status,
                new_status=next_status,
                note=payload.note,
                created_at=now,
            )
        )
    if next_status == "under_review" and report.reviewed_at is None:
        report.reviewed_at = now
    if next_status == "resolved":
        report.resolved_at = now
        report.resolution_summary = payload.resolution_summary.strip()
        report.release_version = payload.release_version
    elif previous_status == "resolved" and next_status != "resolved":
        report.resolved_at = None
        report.resolution_summary = None
        report.release_version = None
        report.resolution_helpful = None
        report.resolution_confirmed_at = None
    record_audit(
        db,
        actor_user_id=user.id,
        action="feedback.status_changed",
        target_type="feedback_report",
        target_id=report.id,
        details={"from": previous_status, "to": next_status},
    )
    db.commit()
    db.refresh(report)
    _publish_report(report, "feedback.status_changed")
    return _response(db, report, include_internal=True)


@router.patch("/{report_id:uuid}/assignment", response_model=FeedbackReportResponse)
def assign_feedback(
    report_id: UUID,
    payload: FeedbackAssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_write_reauth),
) -> FeedbackReportResponse:
    report = _get_visible_report(db, report_id, user)
    assignee = (
        _authorized_assignee(db, user, payload.assigned_to_user_id)
        if payload.assigned_to_user_id is not None
        else None
    )
    if (
        report.category == "security_privacy"
        and assignee is not None
        and assignee.role is not UserRole.SUPER_ADMIN
    ):
        raise HTTPException(
            status_code=422,
            detail="Security and privacy reports can only be assigned to Super Admin reviewers.",
        )
    report.assigned_to_user_id = assignee.id if assignee else None
    report.assigned_at = datetime.now(timezone.utc) if assignee else None
    record_audit(
        db,
        actor_user_id=user.id,
        action="feedback.assigned",
        target_type="feedback_report",
        target_id=report.id,
        details={"assigned_to_user_id": str(assignee.id) if assignee else None},
    )
    db.commit()
    db.refresh(report)
    _publish_report(report, "feedback.assigned")
    return _response(db, report, include_internal=True)


@router.patch("/{report_id:uuid}/priority", response_model=FeedbackReportResponse)
def update_feedback_priority(
    report_id: UUID,
    payload: FeedbackPriorityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_write_reauth),
) -> FeedbackReportResponse:
    report = _get_visible_report(db, report_id, user)
    report.priority = payload.priority
    report.severity = payload.severity
    record_audit(
        db,
        actor_user_id=user.id,
        action="feedback.priority_changed",
        target_type="feedback_report",
        target_id=report.id,
        details={"priority": payload.priority, "severity": payload.severity},
    )
    db.commit()
    db.refresh(report)
    _publish_report(report, "feedback.updated")
    return _response(db, report, include_internal=True)


@router.post("/{report_id:uuid}/confirm", response_model=FeedbackReportResponse)
def confirm_resolution(
    report_id: UUID,
    payload: FeedbackResolutionConfirmation,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackReportResponse:
    report = _get_visible_report(db, report_id, user)
    if report.reporter_user_id != user.id:
        raise HTTPException(status_code=404, detail="Feedback report not found.")
    if report.status != "resolved":
        raise HTTPException(status_code=409, detail="Only resolved reports can be confirmed.")
    report.resolution_helpful = payload.helpful
    report.resolution_confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    _publish_report(report, "feedback.resolution_confirmed")
    return _response(db, report, include_internal=False)


@router.post("/{report_id:uuid}/votes", response_model=FeedbackVoteResponse)
def vote_for_feature(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackVoteResponse:
    report = db.get(FeedbackReport, report_id)
    if report is None or report.category != "feature_request" or report.status not in {
        "planned",
        "in_progress",
    }:
        raise HTTPException(status_code=404, detail="Eligible feature request not found.")
    existing = db.get(FeedbackVote, (report.id, user.id))
    if existing is None:
        db.add(FeedbackVote(report_id=report.id, user_id=user.id))
        db.commit()
    count = db.scalar(
        select(func.count(FeedbackVote.user_id)).where(FeedbackVote.report_id == report.id)
    ) or 0
    return FeedbackVoteResponse(voted=True, votes=count)


@router.delete("/{report_id:uuid}/votes", response_model=FeedbackVoteResponse)
def remove_feature_vote(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackVoteResponse:
    report = db.get(FeedbackReport, report_id)
    if report is None or report.category != "feature_request":
        raise HTTPException(status_code=404, detail="Feature request not found.")
    vote = db.get(FeedbackVote, (report.id, user.id))
    if vote is not None:
        db.delete(vote)
        db.commit()
    count = db.scalar(
        select(func.count(FeedbackVote.user_id)).where(FeedbackVote.report_id == report.id)
    ) or 0
    return FeedbackVoteResponse(voted=False, votes=count)


@router.get("/tasks")
def list_improvement_tasks(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    query = select(FeedbackImprovementTask).order_by(
        FeedbackImprovementTask.created_at.desc()
    )
    if user.role is not UserRole.SUPER_ADMIN:
        query = query.where(
            FeedbackImprovementTask.id.in_(
                select(FeedbackTaskLink.task_id)
                .join(
                    FeedbackReport,
                    FeedbackReport.id == FeedbackTaskLink.report_id,
                )
                .where(FeedbackReport.organization_id == user.organization_id)
            )
        )
    tasks = list(db.scalars(query))
    return [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "acceptance_criteria": task.acceptance_criteria,
            "priority": task.priority,
            "impact": task.impact,
            "affected_features": task.affected_features,
            "assigned_to_user_id": task.assigned_to_user_id,
            "target_release": task.target_release,
            "release_version": task.release_version,
            "verification_notes": task.verification_notes,
            "post_release_outcome": task.post_release_outcome,
            "status": task.status,
            "created_at": task.created_at,
            "feedback_report_ids": [
                link.report_id
                for link in db.scalars(
                    select(FeedbackTaskLink).where(FeedbackTaskLink.task_id == task.id)
                )
            ],
        }
        for task in tasks
    ]


@router.post("/{report_id:uuid}/tasks", status_code=status.HTTP_201_CREATED)
def create_improvement_task(
    report_id: UUID,
    payload: FeedbackImprovementTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_write_reauth),
):
    report = _get_visible_report(db, report_id, user)
    task = FeedbackImprovementTask(
        title=payload.title.strip(),
        description=payload.description.strip(),
        acceptance_criteria=payload.acceptance_criteria,
        priority=payload.priority,
        impact=payload.impact,
        affected_features=payload.affected_features,
        target_release=payload.target_release,
    )
    db.add(task)
    db.flush()
    db.add(FeedbackTaskLink(report_id=report.id, task_id=task.id))
    record_audit(
        db,
        actor_user_id=user.id,
        action="feedback.improvement_task_created",
        target_type="feedback_improvement_task",
        target_id=task.id,
        details={"feedback_report_id": str(report.id)},
    )
    db.commit()
    db.refresh(task)
    return {"id": task.id, "title": task.title, "status": task.status}


@router.patch("/tasks/{task_id}")
def update_improvement_task(
    task_id: UUID,
    payload: FeedbackImprovementTaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_write_reauth),
):
    task = db.get(FeedbackImprovementTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Improvement task not found.")
    links = list(
        db.scalars(
            select(FeedbackTaskLink).where(FeedbackTaskLink.task_id == task.id)
        )
    )
    reports = [db.get(FeedbackReport, link.report_id) for link in links]
    if user.role is not UserRole.SUPER_ADMIN and not any(
        report is not None and _visible(report, user) and report.organization_id == user.organization_id
        for report in reports
    ):
        raise HTTPException(status_code=404, detail="Improvement task not found.")
    changes = payload.model_dump(exclude_unset=True)
    next_status = changes.get("status")
    assignee_id = changes.get("assigned_to_user_id", task.assigned_to_user_id)
    if next_status == "assigned" and assignee_id is None:
        raise HTTPException(status_code=422, detail="Assign an owner before advancing this task.")
    if next_status == "tested" and not (
        changes.get("verification_notes") or task.verification_notes
    ):
        raise HTTPException(
            status_code=422,
            detail="Add test evidence before marking this task as tested.",
        )
    if next_status == "released" and not (
        changes.get("release_version") or task.release_version
    ):
        raise HTTPException(
            status_code=422,
            detail="Add a release version before marking this task as released.",
        )
    if next_status == "measured" and not (
        changes.get("post_release_outcome") or task.post_release_outcome
    ):
        raise HTTPException(
            status_code=422,
            detail="Add a post-release outcome before marking this task as measured.",
        )
    if changes.get("assigned_to_user_id") is not None:
        _authorized_assignee(db, user, changes["assigned_to_user_id"])
    if next_status is not None:
        if next_status not in _TASK_TRANSITIONS or next_status not in _TASK_TRANSITIONS[task.status]:
            raise HTTPException(status_code=409, detail="Invalid improvement task transition.")
        task.status = next_status
    for field in (
        "acceptance_criteria",
        "assigned_to_user_id",
        "target_release",
        "release_version",
        "verification_notes",
        "post_release_outcome",
    ):
        if field in changes:
            setattr(task, field, changes[field])
    record_audit(
        db,
        actor_user_id=user.id,
        action="feedback.improvement_task_updated",
        target_type="feedback_improvement_task",
        target_id=task.id,
        details={"status": task.status},
    )
    db.commit()
    db.refresh(task)
    return {"id": task.id, "title": task.title, "status": task.status}
