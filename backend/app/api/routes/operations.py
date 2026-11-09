from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ...api.auth_dependencies import get_current_user
from ...db.session import get_db
from ...models import Announcement, Branch, PlatformSettings, User
from ...schemas.platform_operations import (
    AnnouncementResponse,
    PlatformSettingsResponse,
)

router = APIRouter(tags=["platform-operations"])


@router.get("/announcements", response_model=list[AnnouncementResponse])
def list_announcements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AnnouncementResponse]:
    now = datetime.now(timezone.utc)
    global_audiences = ["all"]
    if user.role.value in {"customer", "staff"}:
        global_audiences.append(user.role.value)
    elif user.role.value == "super_admin":
        global_audiences.extend(("customer", "staff"))
    organization_id = user.organization_id
    if organization_id is None and user.branch_id is not None:
        organization_id = db.scalar(
            select(Branch.organization_id).where(Branch.id == user.branch_id)
        )
    audience_filters = [
        and_(
            Announcement.organization_id.is_(None),
            Announcement.audience.in_(global_audiences),
        )
    ]
    if organization_id is not None and user.role.value in {"staff", "admin"}:
        audience_filters.append(
            and_(
                Announcement.organization_id == organization_id,
                Announcement.audience == "staff",
            )
        )
    return list(
        db.scalars(
            select(Announcement)
            .where(
                Announcement.published_at.is_not(None),
                or_(*audience_filters),
                or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
            )
            .order_by(Announcement.published_at.desc(), Announcement.created_at.desc())
            .limit(20)
        )
    )


@router.get("/system-status", response_model=PlatformSettingsResponse)
def system_status(db: Session = Depends(get_db)) -> PlatformSettingsResponse:
    settings = db.get(PlatformSettings, 1)
    if settings is None:
        return PlatformSettingsResponse(
            maintenance_mode=False,
            maintenance_message=(
                "QueueLess is temporarily unavailable for scheduled maintenance."
            ),
        )
    return PlatformSettingsResponse.model_validate(
        {
            "maintenance_mode": settings.maintenance_mode,
            "maintenance_message": settings.maintenance_message,
            "updated_at": settings.updated_at,
        }
    )