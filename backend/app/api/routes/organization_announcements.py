from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...api.auth_dependencies import require_admin, require_admin_write_reauth
from ...db.session import get_db
from ...models import Announcement, User
from ...models.entities import UserRole
from ...schemas.platform_operations import (
    AnnouncementCreate,
    AnnouncementResponse,
)
from ...services.audit import record_audit
from ...services.realtime import realtime

router = APIRouter(
    prefix="/admin/announcements",
    tags=["organization-announcements"],
)


def _organization_id(admin: User) -> UUID:
    if admin.role is not UserRole.ADMIN or admin.organization_id is None:
        raise HTTPException(
            status_code=403,
            detail="Organization administrator access is required.",
        )
    return admin.organization_id


def _send_announcement_event(announcement: Announcement, event: str) -> None:
    realtime.publish_announcement_nowait(
        announcement.audience,
        {
            "id": str(announcement.id),
            "title": announcement.title,
            "body": announcement.body,
            "audience": announcement.audience,
            "organization_id": str(announcement.organization_id),
            "published_at": announcement.published_at,
        },
        event,
        organization_id=str(announcement.organization_id),
    )


@router.get("", response_model=list[AnnouncementResponse])
def list_organization_announcements(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[Announcement]:
    organization_id = _organization_id(admin)
    return list(
        db.scalars(
            select(Announcement)
            .where(Announcement.organization_id == organization_id)
            .order_by(Announcement.created_at.desc())
        )
    )


@router.post("", response_model=AnnouncementResponse, status_code=201)
def create_organization_announcement(
    payload: AnnouncementCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_write_reauth),
) -> Announcement:
    organization_id = _organization_id(admin)
    if payload.audience != "staff":
        raise HTTPException(
            status_code=422,
            detail="Organization announcements are restricted to assigned staff.",
        )
    announcement = Announcement(
        organization_id=organization_id,
        title=payload.title,
        body=payload.body,
        audience="staff",
        expires_at=payload.expires_at,
        created_by_user_id=admin.id,
    )
    db.add(announcement)
    db.flush()
    record_audit(
        db,
        actor_user_id=admin.id,
        action="org_announcement.created",
        target_type="announcement",
        target_id=announcement.id,
        details={"organization_id": str(organization_id)},
    )
    db.commit()
    db.refresh(announcement)
    return announcement


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
def update_organization_announcement(
    announcement_id: UUID,
    payload: AnnouncementCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_write_reauth),
) -> Announcement:
    organization_id = _organization_id(admin)
    if payload.audience != "staff":
        raise HTTPException(
            status_code=422,
            detail="Organization announcements are restricted to assigned staff.",
        )
    announcement = db.scalar(
        select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.organization_id == organization_id,
        )
    )
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    announcement.title = payload.title
    announcement.body = payload.body
    announcement.expires_at = payload.expires_at
    record_audit(
        db,
        actor_user_id=admin.id,
        action="org_announcement.updated",
        target_type="announcement",
        target_id=announcement.id,
        details={"organization_id": str(organization_id)},
    )
    db.commit()
    db.refresh(announcement)
    if announcement.is_published:
        _send_announcement_event(announcement, "ANNOUNCEMENT_UPDATED")
    return announcement


@router.post(
    "/{announcement_id}/publish",
    response_model=AnnouncementResponse,
)
def publish_organization_announcement(
    announcement_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_write_reauth),
) -> Announcement:
    organization_id = _organization_id(admin)
    announcement = db.scalar(
        select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.organization_id == organization_id,
        )
    )
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
    announcement.is_published = True
    announcement.published_at = datetime.now(timezone.utc)
    record_audit(
        db,
        actor_user_id=admin.id,
        action="org_announcement.published",
        target_type="announcement",
        target_id=announcement.id,
        details={"organization_id": str(organization_id)},
    )
    db.commit()
    db.refresh(announcement)
    _send_announcement_event(announcement, "ANNOUNCEMENT_PUBLISHED")
    return announcement


@router.post(
    "/{announcement_id}/unpublish",
    response_model=AnnouncementResponse,
)
def unpublish_organization_announcement(
    announcement_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_write_reauth),
) -> Announcement:
    organization_id = _organization_id(admin)
    announcement = db.scalar(
        select(Announcement).where(
            Announcement.id == announcement_id,
            Announcement.organization_id == organization_id,
        )
    )
    if announcement is None:
        raise HTTPException(status_code=404, detail="Announcement not found.")
    announcement.is_published = False
    announcement.published_at = None
    record_audit(
        db,
        actor_user_id=admin.id,
        action="org_announcement.unpublished",
        target_type="announcement",
        target_id=announcement.id,
        details={"organization_id": str(organization_id)},
    )
    db.commit()
    db.refresh(announcement)
    _send_announcement_event(announcement, "ANNOUNCEMENT_UNPUBLISHED")
    return announcement
