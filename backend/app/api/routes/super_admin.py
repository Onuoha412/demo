from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ...api.auth_dependencies import require_recent_super_admin, require_super_admin
from ...config import settings
from ...db.session import get_db
from ...models import (
    Announcement,
    AuditLog,
    AuthSession,
    Branch,
    Counter,
    Organization,
    PlatformSettings,
    Queue,
    QueueEntry,
    Service,
    User,
)
from ...models.entities import QueueEntryStatus, UserRole
from ...schemas.admin import AdminUserPageResponse, AdminUserResponse
from ...schemas.super_admin import (
    AuditLogPageResponse,
    AuditLogResponse,
    DatabaseBackupResponse,
    SuperAdminInitialSetupRequest,
    SuperAdminInitialSetupResponse,
    SuperAdminDashboardResponse,
    SuperAdminRoleUpdate,
)
from ...schemas.auth import WebSocketTicketResponse
from ...schemas.platform_operations import (
    AnnouncementCreate,
    AnnouncementResponse,
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
)
from ...services.audit import record_audit
from ...services.cache import cache
from ...services.database_backup import (
    create_database_backup,
    list_database_backups,
)
from ...services.realtime import realtime

router = APIRouter(
    prefix="/super-admin",
    tags=["super-admin"],
    dependencies=[Depends(require_super_admin)],
)


@router.post("/ws-ticket", response_model=WebSocketTicketResponse)
async def create_super_admin_websocket_ticket(
    admin: User = Depends(require_super_admin),
) -> WebSocketTicketResponse:
    ticket = await cache.issue_websocket_ticket(str(admin.id), "super_admin")
    return WebSocketTicketResponse(ticket=ticket)


def _audit_response(db: Session, entry: AuditLog) -> AuditLogResponse:
    actor_email = None
    if entry.actor_user_id is not None:
        actor_email = db.scalar(
            select(User.email).where(User.id == entry.actor_user_id)
        )
    return AuditLogResponse(
        id=entry.id,
        actor_user_id=entry.actor_user_id,
        actor_email=actor_email,
        action=entry.action,
        target_type=entry.target_type,
        target_id=entry.target_id,
        details=entry.details,
        created_at=entry.created_at,
    )


@router.get("/announcements", response_model=list[AnnouncementResponse])
def list_platform_announcements(
    db: Session = Depends(get_db),
) -> list[AnnouncementResponse]:
    return list(
        db.scalars(
            select(Announcement).order_by(
                Announcement.created_at.desc(), Announcement.id
            )
        )
    )


@router.post(
    "/announcements",
    response_model=AnnouncementResponse,
    status_code=201,
)
def create_platform_announcement(
    payload: AnnouncementCreate,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = Announcement(
        title=payload.title,
        body=payload.body,
        audience=payload.audience,
        expires_at=payload.expires_at,
        created_by_user_id=admin.id,
    )
    db.add(announcement)
    db.flush()
    record_audit(
        db,
        actor_user_id=admin.id,
        action="announcement.created",
        target_type="announcement",
        target_id=announcement.id,
        details={"audience": announcement.audience},
    )
    db.commit()
    db.refresh(announcement)
    return announcement


@router.put(
    "/announcements/{announcement_id}",
    response_model=AnnouncementResponse,
)
def update_platform_announcement(
    announcement_id: UUID,
    payload: AnnouncementCreate,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = db.get(Announcement, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    was_published = announcement.published_at is not None
    announcement.title = payload.title
    announcement.body = payload.body
    announcement.audience = payload.audience
    announcement.expires_at = payload.expires_at
    record_audit(
        db,
        actor_user_id=admin.id,
        action="announcement.updated",
        target_type="announcement",
        target_id=announcement.id,
        details={"audience": announcement.audience},
    )
    db.commit()
    db.refresh(announcement)
    if was_published:
        realtime.publish_announcement_nowait(
            announcement.audience,
            {
                "id": str(announcement.id),
                "title": announcement.title,
                "body": announcement.body,
                "audience": announcement.audience,
                "published_at": announcement.published_at,
            },
            "ANNOUNCEMENT_UPDATED",
        )
    return announcement


@router.post(
    "/announcements/{announcement_id}/publish",
    response_model=AnnouncementResponse,
)
def publish_platform_announcement(
    announcement_id: UUID,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = db.get(Announcement, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    if announcement.expires_at is not None:
        expires_at = announcement.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=409,
                detail="An expired announcement cannot be published.",
            )
    announcement.published_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor_user_id=admin.id,
        action="announcement.published",
        target_type="announcement",
        target_id=announcement.id,
        details={"audience": announcement.audience},
    )
    db.commit()
    db.refresh(announcement)
    realtime.publish_announcement_nowait(
        announcement.audience,
        {
            "id": str(announcement.id),
            "title": announcement.title,
            "body": announcement.body,
            "audience": announcement.audience,
            "published_at": announcement.published_at,
        },
        "ANNOUNCEMENT_PUBLISHED",
    )
    return announcement


@router.post(
    "/announcements/{announcement_id}/unpublish",
    response_model=AnnouncementResponse,
)
def unpublish_platform_announcement(
    announcement_id: UUID,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = db.get(Announcement, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    announcement.published_at = None
    record_audit(
        db,
        actor_user_id=admin.id,
        action="announcement.unpublished",
        target_type="announcement",
        target_id=announcement.id,
        details={"audience": announcement.audience},
    )
    db.commit()
    db.refresh(announcement)
    realtime.publish_announcement_nowait(
        announcement.audience,
        {"id": str(announcement.id)},
        "ANNOUNCEMENT_UNPUBLISHED",
    )
    return announcement


@router.get("/platform-settings", response_model=PlatformSettingsResponse)
def get_platform_settings(
    db: Session = Depends(get_db),
) -> PlatformSettingsResponse:
    platform_settings = db.get(PlatformSettings, 1)
    if platform_settings is None:
        return PlatformSettingsResponse(
            maintenance_mode=False,
            maintenance_message=(
                "QueueLess is temporarily unavailable for scheduled maintenance."
            ),
        )
    return PlatformSettingsResponse.model_validate(platform_settings)


@router.put("/platform-settings", response_model=PlatformSettingsResponse)
def update_platform_settings(
    payload: PlatformSettingsUpdate,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> PlatformSettings:
    platform_settings = db.get(PlatformSettings, 1)
    if platform_settings is None:
        platform_settings = PlatformSettings(id=1)
        db.add(platform_settings)
    old_mode = platform_settings.maintenance_mode
    platform_settings.maintenance_mode = payload.maintenance_mode
    platform_settings.maintenance_message = payload.maintenance_message
    platform_settings.updated_by_user_id = admin.id
    record_audit(
        db,
        actor_user_id=admin.id,
        action="platform_settings.updated",
        target_type="platform_settings",
        target_id="1",
        details={
            "maintenance_mode_from": old_mode,
            "maintenance_mode_to": payload.maintenance_mode,
        },
    )
    db.commit()
    db.refresh(platform_settings)
    return platform_settings


@router.get("/dashboard", response_model=SuperAdminDashboardResponse)
def dashboard(db: Session = Depends(get_db)) -> SuperAdminDashboardResponse:
    users = {
        role.value: (
            db.scalar(select(func.count(User.id)).where(User.role == role)) or 0
        )
        for role in UserRole
    }
    queue_counts = {
        "waiting": QueueEntryStatus.WAITING,
        "serving": QueueEntryStatus.SERVING,
        "completed": QueueEntryStatus.COMPLETED,
        "skipped": QueueEntryStatus.SKIPPED,
        "cancelled": QueueEntryStatus.CANCELLED,
    }
    events = list(
        db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10))
    )
    return SuperAdminDashboardResponse(
        users=users,
        organizations=db.scalar(select(func.count(Organization.id))) or 0,
        branches=db.scalar(select(func.count(Branch.id))) or 0,
        services=db.scalar(select(func.count(Service.id))) or 0,
        counters=db.scalar(select(func.count(Counter.id))) or 0,
        queues={
            label: (
                db.scalar(
                    select(func.count(QueueEntry.id)).where(
                        QueueEntry.status == entry_status
                    )
                )
                or 0
            )
            for label, entry_status in queue_counts.items()
        },
        recent_events=[_audit_response(db, entry) for entry in events],
    )


@router.post(
    "/initial-setup",
    response_model=SuperAdminInitialSetupResponse,
    status_code=201,
)
def create_initial_setup(
    payload: SuperAdminInitialSetupRequest,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> SuperAdminInitialSetupResponse:
    if db.scalar(select(Organization.id).limit(1)) is not None:
        raise HTTPException(
            status_code=409,
            detail="Initial setup is already complete. Manage records from the dashboard.",
        )

    organization = Organization(
        name=payload.organization_name.strip(),
        slug=payload.organization_slug.strip().lower(),
    )
    branch = Branch(
        organization=organization,
        name=payload.branch_name.strip(),
        address=payload.branch_address.strip() if payload.branch_address else None,
        timezone=payload.timezone.strip(),
    )
    service = Service(
        branch=branch,
        name=payload.service_name.strip(),
        code=payload.service_code.strip().upper(),
        average_service_minutes=payload.average_service_minutes,
    )
    queue = Queue(
        service=service,
        name=payload.queue_name.strip(),
        prefix=payload.queue_prefix.strip().upper(),
    )
    db.add(organization)
    try:
        db.flush()
        record_audit(
            db,
            action="initial_setup.completed",
            target_type="organization",
            actor_user_id=admin.id,
            target_id=organization.id,
            details={
                "branch_id": str(branch.id),
                "service_id": str(service.id),
                "queue_id": str(queue.id),
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Setup conflicts with an existing organization, service code, "
                "or queue name. Review the details and try again."
            ),
        ) from None

    return SuperAdminInitialSetupResponse(
        organization_id=organization.id,
        branch_id=branch.id,
        service_id=service.id,
        queue_id=queue.id,
    )


@router.get("/users", response_model=AdminUserPageResponse)
def list_users(
    search: str | None = Query(default=None, max_length=100),
    role: UserRole | None = None,
    active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminUserPageResponse:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if active is not None:
        filters.append(User.is_active.is_(active))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        filters.append(
            User.email.ilike(pattern) | User.full_name.ilike(pattern)
        )
    total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
    items = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return AdminUserPageResponse(
        items=[AdminUserResponse.model_validate(user) for user in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
def change_user_role(
    user_id: UUID,
    payload: SuperAdminRoleUpdate,
    request: Request,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    if payload.role is UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Additional Super Admins can only be designated through the protected bootstrap process.",
        )
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role is UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=409,
            detail="The configured Super Admin cannot be changed through user management.",
        )
    if user.id == admin.id:
        raise HTTPException(status_code=409, detail="You cannot change your own role.")
    if payload.role is UserRole.STAFF and payload.branch_id is None:
        raise HTTPException(
            status_code=422,
            detail="Staff users must be assigned to a branch.",
        )

    organization_id = payload.organization_id
    if payload.branch_id is not None:
        branch = db.get(Branch, payload.branch_id)
        if branch is None:
            raise HTTPException(status_code=404, detail="Branch not found.")
        if organization_id is not None and organization_id != branch.organization_id:
            raise HTTPException(
                status_code=422,
                detail="The organization must match the assigned branch.",
            )
        organization_id = branch.organization_id
    if organization_id is not None:
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found.")
        if not organization.is_active or not organization.is_approved:
            raise HTTPException(
                status_code=409,
                detail="The selected organization is not active and approved.",
            )

    old_role = user.role
    user.role = payload.role
    user.branch_id = payload.branch_id
    user.organization_id = organization_id
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    record_audit(
        db,
        actor_user_id=admin.id,
        action="user.role_changed",
        target_type="user",
        target_id=user.id,
        details={
            "from": old_role.value,
            "to": payload.role.value,
            "branch_id": str(payload.branch_id) if payload.branch_id else None,
            "organization_id": str(organization_id) if organization_id else None,
            "request_path": request.url.path,
        },
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The user role change conflicts with existing account data.",
        ) from None
    db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserResponse)
def deactivate_user(
    user_id: UUID,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role is UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=409,
            detail="The configured Super Admin cannot be deactivated.",
        )
    if user.id == admin.id:
        raise HTTPException(
            status_code=409,
            detail="You cannot deactivate your own account.",
        )
    user.is_active = False
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    record_audit(
        db,
        actor_user_id=admin.id,
        action="user.deactivated",
        target_type="user",
        target_id=user.id,
        details={"role": user.role.value},
    )
    db.commit()
    db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/activate", response_model=AdminUserResponse)
def activate_user(
    user_id: UUID,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.approval_pending or (
        user.organization is not None and not user.organization.is_approved
    ):
        raise HTTPException(
            status_code=409,
            detail="Approve this user's organization before activating the account.",
        )
    user.is_active = True
    record_audit(
        db,
        actor_user_id=admin.id,
        action="user.activated",
        target_type="user",
        target_id=user.id,
        details={"role": user.role.value},
    )
    db.commit()
    db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/revoke-sessions")
def revoke_user_sessions(
    user_id: UUID,
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    revoked_count = result.rowcount or 0
    record_audit(
        db,
        actor_user_id=admin.id,
        action="user.sessions_revoked",
        target_type="user",
        target_id=user.id,
        details={"revoked_count": revoked_count},
    )
    db.commit()
    return {"revoked_sessions": revoked_count}


@router.get("/audit-logs", response_model=AuditLogPageResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    action: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
) -> AuditLogPageResponse:
    filters = [AuditLog.action == action] if action else []
    total = db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
    entries = list(
        db.scalars(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return AuditLogPageResponse(
        items=[_audit_response(db, entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/system-health")
def system_health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        backups = list_database_backups(settings.database_backup_dir, limit=1)
        backup_status = "available" if backups else "no snapshots"
    except OSError:
        backup_status = "unavailable"
    try:
        db.execute(select(1)).scalar_one()
    except SQLAlchemyError:
        return {
            "api": "ok",
            "database": "unavailable",
            "backup_monitoring": backup_status,
        }
    return {
        "api": "ok",
        "database": "connected",
        "backup_monitoring": backup_status,
    }


@router.get("/backups", response_model=list[DatabaseBackupResponse])
def database_backups() -> list[DatabaseBackupResponse]:
    return [
        DatabaseBackupResponse(**backup)
        for backup in list_database_backups(settings.database_backup_dir)
    ]


@router.post("/backups", response_model=DatabaseBackupResponse, status_code=201)
async def create_database_backup_snapshot(
    admin: User = Depends(require_recent_super_admin),
    db: Session = Depends(get_db),
) -> DatabaseBackupResponse:
    allowed = await cache.increment_with_limit(
        f"queueless:database-backups:{admin.id}",
        limit=3,
        window_seconds=3600,
    )
    if not allowed:
        raise HTTPException(
            status_code=429, detail="Backup creation limit reached. Try again later."
        )
    try:
        path = create_database_backup(
            settings.database_url, settings.database_backup_dir
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    record_audit(
        db,
        actor_user_id=admin.id,
        action="database.backup_created",
        target_type="database_backup",
        target_id=path.name,
        details={"size_bytes": path.stat().st_size},
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="The backup file was written, but its audit record could not be saved.",
        ) from None
    return DatabaseBackupResponse(
        filename=path.name,
        size_bytes=path.stat().st_size,
        created_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc),
    )