from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...api.auth_dependencies import get_current_user
from ...db.session import get_db
from ...models import NotificationPreference, User
from ...schemas.notification import (
    NotificationListResponse,
    NotificationPreferences,
    NotificationResponse,
)
from ...services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return NotificationService(db).list_for_user(user.id, page, page_size)


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"count": NotificationService(db).unread_count(user.id)}


@router.post("/{notification_id}/read", status_code=204)
def mark_read(notification_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not NotificationService(db).mark_read(user.id, notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/read-all", status_code=204)
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    NotificationService(db).mark_read(user.id)


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    preferences = db.get(NotificationPreference, user.id)
    return preferences or NotificationPreferences()


@router.put("/preferences", response_model=NotificationPreferences)
def update_preferences(
    payload: NotificationPreferences,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    preferences = db.get(NotificationPreference, user.id)
    if preferences is None:
        preferences = NotificationPreference(user_id=user.id)
        db.add(preferences)
    for key, value in payload.model_dump().items():
        setattr(preferences, key, value)
    db.commit()
    return preferences
