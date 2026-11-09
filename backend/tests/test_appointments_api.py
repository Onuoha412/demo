import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import (
    Branch,
    Organization,
    OrganizationMembership,
    Service,
    User,
)
from app.models.entities import AppointmentStatus, UserRole


def make_user(name: str, role: UserRole, organization_id=None) -> User:
    return User(
        full_name=name,
        email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("appointment-test-password"),
        role=role,
        organization_id=organization_id,
    )


def appointment_fixture(db: Session):
    organization = Organization(
        name="Appointment Org", slug=f"appointment-{uuid.uuid4()}"
    )
    branch = Branch(name="Appointment Branch", organization=organization)
    service = Service(
        branch=branch,
        name="Consultation",
        code=f"A{uuid.uuid4().hex[:7]}",
        average_service_minutes=20,
    )
    admin = make_user("Appointment Admin", UserRole.ADMIN, organization.id)
    customer = make_user("Appointment Customer", UserRole.CUSTOMER)
    other_customer = make_user("Other Appointment Customer", UserRole.CUSTOMER)
    db.add_all([organization, service, admin, customer, other_customer])
    db.flush()
    admin.organization_id = organization.id
    db.add(
        OrganizationMembership(
            user_id=admin.id,
            organization_id=organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return service, admin, customer, other_customer, TestClient(app)


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def create_slot(client: TestClient, admin: User, service: Service, *, start, capacity=1):
    response = client.post(
        "/api/v1/admin/appointment-slots",
        json={
            "service_id": str(service.id),
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(minutes=30)).isoformat(),
            "capacity": capacity,
        },
        headers=auth(admin),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_appointment_booking_capacity_cancellation_and_owner_scope(
    db_session: Session,
) -> None:
    service, admin, customer, other_customer, client = appointment_fixture(db_session)
    slot = create_slot(
        client,
        admin,
        service,
        start=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    booked = client.post(
        "/api/v1/customers/appointments",
        json={"slot_id": slot["id"]},
        headers=auth(customer),
    )
    assert booked.status_code == 201, booked.text
    appointment_id = booked.json()["id"]
    duplicate = client.post(
        "/api/v1/customers/appointments",
        json={"slot_id": slot["id"]},
        headers=auth(customer),
    )
    assert duplicate.status_code == 409

    full = client.post(
        "/api/v1/customers/appointments",
        json={"slot_id": slot["id"]},
        headers=auth(other_customer),
    )
    assert full.status_code == 409
    hidden = client.post(
        f"/api/v1/customers/appointments/{appointment_id}/cancel",
        headers=auth(other_customer),
    )
    assert hidden.status_code == 404

    cancelled = client.post(
        f"/api/v1/customers/appointments/{appointment_id}/cancel",
        headers=auth(customer),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == AppointmentStatus.CANCELLED.value
    available = client.get(
        f"/api/v1/customers/appointment-slots?service_id={service.id}",
        headers=auth(other_customer),
    )
    assert available.status_code == 200
    assert available.json()[0]["booked_count"] == 0

    rebooked = client.post(
        "/api/v1/customers/appointments",
        json={"slot_id": slot["id"]},
        headers=auth(other_customer),
    )
    assert rebooked.status_code == 201
    app.dependency_overrides.clear()


def test_appointment_checkin_window_and_customer_history_are_scoped(
    db_session: Session,
) -> None:
    service, admin, customer, other_customer, client = appointment_fixture(db_session)
    slot = create_slot(
        client,
        admin,
        service,
        start=datetime.now(timezone.utc) + timedelta(minutes=5),
        capacity=2,
    )
    booked = client.post(
        "/api/v1/customers/appointments",
        json={"slot_id": slot["id"]},
        headers=auth(customer),
    )
    appointment_id = booked.json()["id"]

    checked_in = client.post(
        f"/api/v1/customers/appointments/{appointment_id}/check-in",
        headers=auth(customer),
    )
    assert checked_in.status_code == 200, checked_in.text
    assert checked_in.json()["status"] == AppointmentStatus.CHECKED_IN.value
    assert checked_in.json()["checked_in_at"] is not None
    assert client.post(
        f"/api/v1/customers/appointments/{appointment_id}/cancel",
        headers=auth(customer),
    ).status_code == 409

    other_history = client.get(
        "/api/v1/customers/appointments", headers=auth(other_customer)
    )
    assert other_history.status_code == 200
    assert other_history.json() == []
    app.dependency_overrides.clear()


def test_appointment_slot_admin_enforces_organization_scope_and_timezone(
    db_session: Session,
) -> None:
    service, _, _, _, client = appointment_fixture(db_session)
    other_organization = Organization(
        name="Foreign Appointment Org", slug=f"foreign-{uuid.uuid4()}"
    )
    foreign_admin = make_user(
        "Foreign Appointment Admin", UserRole.ADMIN, other_organization.id
    )
    db_session.add_all([other_organization, foreign_admin])
    db_session.flush()
    foreign_admin.organization_id = other_organization.id
    db_session.add(
        OrganizationMembership(
            user_id=foreign_admin.id,
            organization_id=other_organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db_session.commit()
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    payload = {
        "service_id": str(service.id),
        "starts_at": future.isoformat(),
        "ends_at": (future + timedelta(minutes=30)).isoformat(),
    }
    forbidden = client.post(
        "/api/v1/admin/appointment-slots", json=payload, headers=auth(foreign_admin)
    )
    assert forbidden.status_code == 404
    invalid_timezone = client.post(
        "/api/v1/admin/appointment-slots",
        json={
            **payload,
            "starts_at": future.replace(tzinfo=None).isoformat(),
        },
        headers=auth(foreign_admin),
    )
    assert invalid_timezone.status_code == 422
    app.dependency_overrides.clear()
