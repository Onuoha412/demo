import uuid
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user, get_db
from app.core.security import hash_password
from app.main import app
from app.models import (
    Branch,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    QueueRequest,
    Service,
    User,
)
from app.models.entities import QueueEntryStatus, QueueRequestStatus, UserRole


def make_branch_queue(db: Session, branch_name: str) -> tuple[Branch, Queue]:
    organization = Organization(
        name=f"{branch_name} Organization",
        slug=f"{branch_name.casefold()}-{uuid.uuid4()}",
    )
    branch = Branch(name=branch_name, organization=organization)
    service = Service(
        name=f"{branch_name} Service",
        code=f"{uuid.uuid4().hex[:8]}",
        branch=branch,
    )
    queue = Queue(name=f"{branch_name} Queue", prefix="R", service=service)
    db.add(queue)
    db.flush()
    return branch, queue


def make_user(role: UserRole, branch: Branch | None = None) -> User:
    return User(
        full_name=role.value.title(),
        email=f"{role.value}-{uuid.uuid4()}@example.test",
        password_hash=hash_password("request-test-password"),
        role=role,
        branch=branch,
    )


def test_customer_request_is_assigned_approved_and_shown_as_queue_ticket(
    db_session: Session,
) -> None:
    branch, queue = make_branch_queue(db_session, "Request Branch")
    other_branch, other_queue = make_branch_queue(db_session, "Other Branch")
    customer = make_user(UserRole.CUSTOMER)
    staff = make_user(UserRole.STAFF, branch)
    admin = make_user(UserRole.ADMIN)
    admin.organization = branch.organization
    other_staff = make_user(UserRole.STAFF, other_branch)
    db_session.add_all([customer, staff, admin, other_staff])
    db_session.commit()
    db_session.add(
        OrganizationMembership(
            user_id=admin.id,
            organization_id=branch.organization_id,
            role=UserRole.ADMIN.value,
        )
    )
    db_session.commit()

    actor = {"user": customer}

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: actor["user"]
    client = TestClient(app)
    submitted = client.post(
        "/api/v1/customers/queue-requests",
        json={
            "branch_id": str(branch.id),
            "request_text": "I need help replacing a lost access card.",
        },
    )
    assert submitted.status_code == 201
    request_id = submitted.json()["id"]
    assert submitted.json()["status"] == QueueRequestStatus.PENDING.value
    assert submitted.json()["queue_entry_id"] is None
    assert (
        db_session.scalar(
            select(QueueEntry.id).where(QueueEntry.customer_id == customer.id)
        )
        is None
    )

    actor["user"] = staff
    staff_list = client.get("/api/v1/queue-requests/review")
    assert staff_list.status_code == 200
    assert [item["id"] for item in staff_list.json()["items"]] == [request_id]
    cross_branch_assignment = client.post(
        f"/api/v1/queue-requests/{request_id}/approve",
        json={"queue_id": str(other_queue.id)},
    )
    assert cross_branch_assignment.status_code == 403

    actor["user"] = other_staff
    cross_branch_review = client.post(
        f"/api/v1/queue-requests/{request_id}/approve",
        json={"queue_id": str(other_queue.id)},
    )
    assert cross_branch_review.status_code == 403

    actor["user"] = admin
    mismatch = client.post(
        f"/api/v1/queue-requests/{request_id}/approve",
        json={"queue_id": str(other_queue.id)},
    )
    assert mismatch.status_code == 404

    actor["user"] = staff
    approved = client.post(
        f"/api/v1/queue-requests/{request_id}/approve",
        json={"queue_id": str(queue.id)},
    )
    assert approved.status_code == 200
    ticket_id = approved.json()["queue_entry_id"]
    assert approved.json()["status"] == QueueRequestStatus.APPROVED.value
    assert approved.json()["queue_number"] == 1
    assert approved.json()["assigned_queue_name"] == queue.name
    entry = db_session.get(QueueEntry, UUID(ticket_id))
    assert entry is not None
    assert entry.status is QueueEntryStatus.WAITING
    assert entry.request_note == "I need help replacing a lost access card."

    actor["user"] = customer
    customer_requests = client.get("/api/v1/customers/queue-requests")
    assert customer_requests.status_code == 200
    assert customer_requests.json()[0]["status"] == QueueRequestStatus.APPROVED.value
    assert customer_requests.json()[0]["queue_entry_id"] == ticket_id
    ticket = client.get(f"/api/v1/customers/queue-entries/{ticket_id}")
    assert ticket.status_code == 200
    assert ticket.json()["request_note"] == "I need help replacing a lost access card."

    actor["user"] = staff
    duplicate_approval = client.post(
        f"/api/v1/queue-requests/{request_id}/approve",
        json={"queue_id": str(queue.id)},
    )
    assert duplicate_approval.status_code == 409


def test_customer_can_only_view_own_requests_and_reviewer_can_decline(
    db_session: Session,
) -> None:
    branch, _queue = make_branch_queue(db_session, "Decline Branch")
    customer = make_user(UserRole.CUSTOMER)
    other_customer = make_user(UserRole.CUSTOMER)
    admin = make_user(UserRole.ADMIN)
    admin.organization = branch.organization
    db_session.add_all([customer, other_customer, admin])
    db_session.commit()
    db_session.add(
        OrganizationMembership(
            user_id=admin.id,
            organization_id=branch.organization_id,
            role=UserRole.ADMIN.value,
        )
    )
    db_session.commit()

    actor = {"user": customer}

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: actor["user"]
    client = TestClient(app)
    response = client.post(
        "/api/v1/customers/queue-requests",
        json={"branch_id": str(branch.id), "request_text": "Help with a payment."},
    )
    assert response.status_code == 201
    request_id = response.json()["id"]

    actor["user"] = other_customer
    assert client.get("/api/v1/customers/queue-requests").json() == []

    actor["user"] = admin
    declined = client.post(
        f"/api/v1/queue-requests/{request_id}/reject",
        json={"review_note": "Please contact the branch first."},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == QueueRequestStatus.REJECTED.value
    assert declined.json()["review_note"] == "Please contact the branch first."
    item = db_session.get(QueueRequest, UUID(request_id))
    assert item is not None and item.reviewed_by_user_id == admin.id
