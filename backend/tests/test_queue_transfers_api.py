import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import (
    AuditLog,
    Branch,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    QueueEvent,
    QueueTransfer,
    Service,
    User,
)
from app.models.entities import UserRole
from app.services.queue import QueueService


def make_user(name: str, role: UserRole, *, branch_id=None, organization_id=None):
    return User(
        full_name=name,
        email=f"{uuid.uuid4()}@example.test",
        password_hash=hash_password("queue-transfer-test-password"),
        role=role,
        branch_id=branch_id,
        organization_id=organization_id,
    )


def setup_transfer_client(db: Session):
    organization = Organization(
        name="Transfer Org", slug=f"transfer-{uuid.uuid4()}"
    )
    source_branch = Branch(name="Transfer Source", organization=organization)
    target_branch = Branch(name="Transfer Target", organization=organization)
    foreign_organization = Organization(
        name="Foreign Transfer Org", slug=f"foreign-transfer-{uuid.uuid4()}"
    )
    foreign_branch = Branch(name="Foreign Transfer Branch", organization=foreign_organization)
    source_service = Service(
        name="Source Service",
        code=f"S{uuid.uuid4().hex[:7]}",
        branch=source_branch,
    )
    target_service = Service(
        name="Target Service",
        code=f"T{uuid.uuid4().hex[:7]}",
        branch=source_branch,
    )
    other_branch_service = Service(
        name="Other Branch Service",
        code=f"B{uuid.uuid4().hex[:7]}",
        branch=target_branch,
    )
    foreign_service = Service(
        name="Foreign Service",
        code=f"F{uuid.uuid4().hex[:7]}",
        branch=foreign_branch,
    )
    source_queue = Queue(name="Source queue", prefix="S", service=source_service)
    target_queue = Queue(name="Target queue", prefix="T", service=target_service)
    other_branch_queue = Queue(
        name="Other branch queue", prefix="B", service=other_branch_service
    )
    foreign_queue = Queue(name="Foreign queue", prefix="F", service=foreign_service)
    customer = make_user("Transfer Customer", UserRole.CUSTOMER)
    staff = make_user("Transfer Staff", UserRole.STAFF)
    admin = make_user("Transfer Admin", UserRole.ADMIN)
    db.add_all(
        [
            organization,
            foreign_organization,
            source_queue,
            target_queue,
            other_branch_queue,
            foreign_queue,
            customer,
            staff,
            admin,
        ]
    )
    db.flush()
    staff.branch_id = source_branch.id
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
    return (
        source_queue,
        target_queue,
        other_branch_queue,
        foreign_queue,
        customer,
        staff,
        admin,
        TestClient(app),
    )


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def join(client: TestClient, queue: Queue, user: User):
    response = client.post(
        f"/api/v1/queues/{queue.id}/join",
        json={"customer_id": str(user.id)},
        headers=headers(user),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_staff_transfer_is_branch_scoped_and_keeps_auditable_tickets(
    db_session: Session,
) -> None:
    (
        source_queue,
        target_queue,
        other_branch_queue,
        foreign_queue,
        customer,
        staff,
        _,
        client,
    ) = setup_transfer_client(db_session)
    source_entry = join(client, source_queue, customer)

    cross_branch = client.post(
        f"/api/v1/queue-entries/{source_entry['id']}/transfer",
        json={"target_queue_id": str(other_branch_queue.id)},
        headers=headers(staff),
    )
    assert cross_branch.status_code == 404
    cross_tenant = client.post(
        f"/api/v1/queue-entries/{source_entry['id']}/transfer",
        json={"target_queue_id": str(foreign_queue.id)},
        headers=headers(staff),
    )
    assert cross_tenant.status_code == 404

    transferred = client.post(
        f"/api/v1/queue-entries/{source_entry['id']}/transfer",
        json={"target_queue_id": str(target_queue.id)},
        headers=headers(staff),
    )
    assert transferred.status_code == 200, transferred.text
    target_entry = transferred.json()
    assert target_entry["id"] != source_entry["id"]
    assert target_entry["queue_id"] == str(target_queue.id)
    assert target_entry["queue_number"] == 1

    original = client.get(
        f"/api/v1/customers/queue-entries/{source_entry['id']}",
        headers=headers(customer),
    )
    assert original.status_code == 200
    assert original.json()["status"] == "cancelled"
    assert original.json()["transferred_to_entry_id"] == target_entry["id"]
    assert db_session.scalar(
        select(func.count(QueueTransfer.id)).where(
            QueueTransfer.source_entry_id == uuid.UUID(source_entry["id"]),
            QueueTransfer.target_entry_id == uuid.UUID(target_entry["id"]),
        )
    ) == 1
    assert db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "queue_entry.transferred"
        )
    ) == 1
    assert db_session.scalar(
        select(func.count(QueueEvent.id)).where(
            QueueEvent.queue_id == target_queue.id,
            QueueEvent.event_type == "joined",
        )
    ) == 1
    assert db_session.get(QueueEntry, uuid.UUID(source_entry["id"])).status.value == "cancelled"
    app.dependency_overrides.clear()


def test_organization_admin_can_transfer_across_its_branches_but_not_tenants(
    db_session: Session,
) -> None:
    (
        source_queue,
        _,
        other_branch_queue,
        foreign_queue,
        customer,
        _,
        admin,
        client,
    ) = setup_transfer_client(db_session)
    source_entry = join(client, source_queue, customer)

    allowed = client.post(
        f"/api/v1/queue-entries/{source_entry['id']}/transfer",
        json={"target_queue_id": str(other_branch_queue.id)},
        headers=headers(admin),
    )
    assert allowed.status_code == 200, allowed.text

    next_entry = join(client, source_queue, customer)
    denied = client.post(
        f"/api/v1/queue-entries/{next_entry['id']}/transfer",
        json={"target_queue_id": str(foreign_queue.id)},
        headers=headers(admin),
    )
    assert denied.status_code == 404
    app.dependency_overrides.clear()
