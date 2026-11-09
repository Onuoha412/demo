from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from ...api.auth_dependencies import get_current_user, require_admin
from ...db.session import get_db
from ...models import Appointment, AppointmentSlot, Branch, Service, User
from ...models.entities import AppointmentStatus, UserRole
from ...schemas.appointments import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentSlotCreate,
    AppointmentSlotResponse,
)
from ...services.audit import record_audit
from ...services.time_engine import utc_now

customer_router = APIRouter(prefix="/customers", tags=["appointments"])
admin_router = APIRouter(prefix="/admin/appointment-slots", tags=["appointments"])


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _slot_response(slot: AppointmentSlot) -> AppointmentSlotResponse:
    return AppointmentSlotResponse(
        id=slot.id,
        service_id=slot.service_id,
        starts_at=_utc(slot.starts_at),
        ends_at=_utc(slot.ends_at),
        capacity=slot.capacity,
        booked_count=slot.booked_count,
        is_open=slot.is_open,
    )


def _appointment_response(appointment: Appointment) -> AppointmentResponse:
    return AppointmentResponse(
        id=appointment.id,
        slot_id=appointment.slot_id,
        service_id=appointment.slot.service_id,
        service_name=appointment.slot.service.name,
        starts_at=_utc(appointment.slot.starts_at),
        ends_at=_utc(appointment.slot.ends_at),
        status=appointment.status,
        checked_in_at=(
            _utc(appointment.checked_in_at)
            if appointment.checked_in_at is not None
            else None
        ),
        created_at=_utc(appointment.created_at),
    )


def _require_customer(user: User) -> None:
    if user.role is not UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Customer access required.")


@customer_router.get("/appointment-slots", response_model=list[AppointmentSlotResponse])
def list_available_slots(
    service_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_customer(user)
    service = db.scalar(
        select(Service).where(Service.id == service_id, Service.is_active.is_(True))
    )
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found.")
    slots = db.scalars(
        select(AppointmentSlot)
        .where(
            AppointmentSlot.service_id == service_id,
            AppointmentSlot.starts_at > utc_now(),
            AppointmentSlot.is_open.is_(True),
            AppointmentSlot.booked_count < AppointmentSlot.capacity,
        )
        .order_by(AppointmentSlot.starts_at)
        .limit(100)
        .execution_options(populate_existing=True)
    )
    return [_slot_response(slot) for slot in slots]


@customer_router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def book_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_customer(user)
    slot = db.scalar(
        select(AppointmentSlot)
        .options(joinedload(AppointmentSlot.service))
        .where(AppointmentSlot.id == payload.slot_id)
    )
    if slot is None or not slot.service.is_active:
        raise HTTPException(status_code=404, detail="Appointment slot not found.")
    now = utc_now()
    if not slot.is_open or _utc(slot.starts_at) <= now:
        raise HTTPException(status_code=409, detail="This appointment slot is no longer open.")
    existing = db.scalar(
        select(Appointment.id).where(
            Appointment.slot_id == slot.id,
            Appointment.customer_id == user.id,
            Appointment.status.in_(
                [AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN]
            ),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="You already have an active booking for this slot."
        )

    reserved = db.execute(
        update(AppointmentSlot)
        .where(
            AppointmentSlot.id == slot.id,
            AppointmentSlot.is_open.is_(True),
            AppointmentSlot.starts_at > now,
            AppointmentSlot.booked_count < AppointmentSlot.capacity,
        )
        .values(booked_count=AppointmentSlot.booked_count + 1)
        .execution_options(synchronize_session=False)
    )
    if reserved.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This appointment slot is full.")

    appointment = Appointment(slot_id=slot.id, customer_id=user.id)
    db.add(appointment)
    try:
        db.commit()
        db.refresh(appointment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="You already have an active booking for this slot."
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="The appointment could not be booked."
        ) from None
    return _appointment_response(appointment)


@customer_router.get("/appointments", response_model=list[AppointmentResponse])
def list_customer_appointments(
    include_past: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_customer(user)
    query = (
        select(Appointment)
        .options(joinedload(Appointment.slot).joinedload(AppointmentSlot.service))
        .where(Appointment.customer_id == user.id)
        .order_by(Appointment.created_at.desc())
        .limit(100)
    )
    if not include_past:
        query = query.where(
            AppointmentSlot.starts_at > utc_now()
        ).join(AppointmentSlot)
    return [_appointment_response(item) for item in db.scalars(query)]


@customer_router.post(
    "/appointments/{appointment_id}/cancel", response_model=AppointmentResponse
)
def cancel_appointment(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_customer(user)
    appointment = db.scalar(
        select(Appointment)
        .options(joinedload(Appointment.slot).joinedload(AppointmentSlot.service))
        .where(Appointment.id == appointment_id)
    )
    if appointment is None or appointment.customer_id != user.id:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appointment.status is not AppointmentStatus.BOOKED:
        raise HTTPException(
            status_code=409, detail="Only booked appointments can be cancelled."
        )

    now = utc_now()
    if _utc(appointment.slot.starts_at) <= now:
        raise HTTPException(
            status_code=409, detail="Appointments can only be cancelled before they start."
        )
    changed = db.execute(
        update(Appointment)
        .where(
            Appointment.id == appointment.id,
            Appointment.status == AppointmentStatus.BOOKED,
        )
        .values(status=AppointmentStatus.CANCELLED)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="This appointment has already changed."
        )
    db.execute(
        update(AppointmentSlot)
        .where(
            AppointmentSlot.id == appointment.slot_id,
            AppointmentSlot.booked_count > 0,
        )
        .values(booked_count=AppointmentSlot.booked_count - 1)
        .execution_options(synchronize_session=False)
    )
    appointment.slot.booked_count -= 1
    try:
        db.commit()
        db.refresh(appointment)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="The appointment could not be cancelled."
        ) from None
    return _appointment_response(appointment)


@customer_router.post(
    "/appointments/{appointment_id}/check-in", response_model=AppointmentResponse
)
def check_in_appointment(
    appointment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_customer(user)
    appointment = db.scalar(
        select(Appointment)
        .options(joinedload(Appointment.slot).joinedload(AppointmentSlot.service))
        .where(Appointment.id == appointment_id)
    )
    if appointment is None or appointment.customer_id != user.id:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appointment.status is not AppointmentStatus.BOOKED:
        raise HTTPException(
            status_code=409, detail="This appointment is not awaiting check-in."
        )

    now = utc_now()
    starts_at = _utc(appointment.slot.starts_at)
    ends_at = _utc(appointment.slot.ends_at)
    if now < starts_at - timedelta(minutes=15) or now > ends_at:
        raise HTTPException(
            status_code=409,
            detail="Check-in is available from 15 minutes before the appointment until its end.",
        )
    changed = db.execute(
        update(Appointment)
        .where(
            Appointment.id == appointment.id,
            Appointment.status == AppointmentStatus.BOOKED,
        )
        .values(status=AppointmentStatus.CHECKED_IN, checked_in_at=now)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="This appointment has already changed."
        )
    try:
        db.commit()
        db.refresh(appointment)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Check-in could not be completed.") from None
    return _appointment_response(appointment)


@admin_router.post("", response_model=AppointmentSlotResponse, status_code=201)
def create_appointment_slot(
    payload: AppointmentSlotCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    service = db.scalar(
        select(Service)
        .join(Branch, Service.branch_id == Branch.id)
        .where(Service.id == payload.service_id, Service.is_active.is_(True))
    )
    if service is None or (
        admin.role is UserRole.ADMIN
        and (
            admin.organization_id is None
            or service.branch.organization_id != admin.organization_id
        )
    ):
        raise HTTPException(status_code=404, detail="Service not found.")
    starts_at = _utc(payload.starts_at)
    ends_at = _utc(payload.ends_at)
    if starts_at <= utc_now():
        raise HTTPException(status_code=422, detail="Appointment slots must be in the future.")
    slot = AppointmentSlot(
        service_id=service.id,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=payload.capacity,
    )
    db.add(slot)
    record_audit(
        db,
        actor_user_id=admin.id,
        action="appointment_slot.created",
        target_type="appointment_slot",
        target_id=slot.id,
        details={"service_id": str(service.id), "capacity": payload.capacity},
    )
    try:
        db.commit()
        db.refresh(slot)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An appointment slot already exists at that time."
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="The appointment slot could not be created."
        ) from None
    return _slot_response(slot)


@admin_router.get("", response_model=list[AppointmentSlotResponse])
def list_service_appointment_slots(
    service_id: UUID = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = (
        select(AppointmentSlot)
        .join(Service, AppointmentSlot.service_id == Service.id)
        .join(Branch, Service.branch_id == Branch.id)
        .where(Service.id == service_id)
        .order_by(AppointmentSlot.starts_at)
        .limit(200)
    )
    if admin.role is UserRole.ADMIN:
        if admin.organization_id is None:
            raise HTTPException(status_code=404, detail="Service not found.")
        query = query.where(Branch.organization_id == admin.organization_id)
    return [_slot_response(slot) for slot in db.scalars(query)]
