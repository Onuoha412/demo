import uuid
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.api.auth_dependencies import get_db
from app.main import app
from app.models import (
    Branch,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    Service,
    User,
)
from app.models.entities import UserRole
from app.core.security import create_access_token, hash_password
from app.services.realtime import realtime


def websocket_fixture(db: Session, monkeypatch):
    organization = Organization(name="Socket QA", slug=f"socket-{uuid.uuid4()}")
    branch = Branch(name="Socket Branch", organization=organization)
    service = Service(name="Socket Service", code=str(uuid.uuid4())[:8], branch=branch)
    queue = Queue(name="Socket Queue", prefix="S", service=service)
    customer = User(
        full_name="Socket Customer",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
    )
    db.add_all([organization, queue, customer])
    db.commit()
    queue.current_number = 1
    db.add(QueueEntry(queue=queue, customer=customer, queue_number=1))
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr("app.websocket.routes.SessionLocal", factory)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return queue, customer, TestClient(app)


def test_websocket_rejects_unauthorized_and_invalid_queue(db_session: Session, monkeypatch) -> None:
    queue, _, client = websocket_fixture(db_session, monkeypatch)
    with client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/queues/{queue.id}"):
                pass
        try:
            with client.websocket_connect(f"/ws/queues/{uuid.uuid4()}?public=1"):
                pytest.fail("unknown queue should not connect")
        except WebSocketDisconnect as exc:
            assert exc.code == 4404
    app.dependency_overrides.clear()


def test_authenticated_websocket_ticket_is_one_time(db_session: Session, monkeypatch) -> None:
    queue, customer, client = websocket_fixture(db_session, monkeypatch)
    token = create_access_token(customer.id)
    with client:
        response = client.post(
            "/api/v1/auth/ws-ticket",
            json={"queue_id": str(queue.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        ticket = response.json()["ticket"]
        with client.websocket_connect(f"/ws/queues/{queue.id}?ticket={ticket}"):
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/ws/queues/{queue.id}?ticket={ticket}"):
                    pass
    app.dependency_overrides.clear()


def test_multiple_clients_receive_queue_updates_and_reconnect(db_session: Session, monkeypatch) -> None:
    queue, _, client = websocket_fixture(db_session, monkeypatch)
    with client:
        with ExitStack() as sockets:
            first = sockets.enter_context(client.websocket_connect(f"/ws/queues/{queue.id}?public=1"))
            second = sockets.enter_context(client.websocket_connect(f"/ws/queues/{queue.id}?public=1"))
            realtime.publish_nowait(queue.id, "QUEUE_UPDATED", {"status": "paused"})
            assert first.receive_json()["event"] == "QUEUE_UPDATED"
            assert second.receive_json()["data"]["status"] == "paused"
        with client.websocket_connect(f"/ws/queues/{queue.id}?public=1") as reconnected:
            realtime.publish_nowait(queue.id, "CUSTOMER_JOINED", {"queue_number": 1})
            assert reconnected.receive_json()["event"] == "CUSTOMER_JOINED"


def test_public_websocket_rejects_invalid_replay_cursor(
    db_session: Session, monkeypatch
) -> None:
    queue, _, client = websocket_fixture(db_session, monkeypatch)
    with client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(
                f"/ws/queues/{queue.id}?public=1&since=not-a-number"
            ):
                pass
        assert error.value.code == 4400


def test_join_broadcast_reaches_customer_staff_and_display(
    db_session: Session, monkeypatch
) -> None:
    queue, customer, client = websocket_fixture(db_session, monkeypatch)
    staff = User(
        full_name="Queue Staff",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.STAFF,
        branch_id=queue.service.branch_id,
    )
    joining_customer = User(
        full_name="Joining Customer",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
    )
    db_session.add_all([staff, joining_customer])
    db_session.commit()

    def websocket_ticket(user: User) -> str:
        response = client.post(
            "/api/v1/auth/ws-ticket",
            json={"queue_id": str(queue.id)},
            headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
        )
        assert response.status_code == 200
        return response.json()["ticket"]

    customer_ticket = websocket_ticket(customer)
    staff_ticket = websocket_ticket(staff)

    with client:
        with ExitStack() as sockets:
            customer_socket = sockets.enter_context(
                client.websocket_connect(
                    f"/ws/queues/{queue.id}?ticket={customer_ticket}"
                )
            )
            staff_socket = sockets.enter_context(
                client.websocket_connect(f"/ws/queues/{queue.id}?ticket={staff_ticket}")
            )
            display_socket = sockets.enter_context(
                client.websocket_connect(f"/ws/queues/{queue.id}?public=1")
            )

            joined = client.post(
                f"/api/v1/queues/{queue.id}/join",
                json={"customer_id": str(joining_customer.id)},
                headers={
                    "Authorization": f"Bearer {create_access_token(joining_customer.id)}"
                },
            )

            assert joined.status_code == 201
            for socket in (customer_socket, staff_socket, display_socket):
                approaching = socket.receive_json()
                assert approaching["event"] == "QUEUE_APPROACHING"
                message = socket.receive_json()
                assert message["event"] == "CUSTOMER_JOINED"
                assert message["data"]["queue_number"] == 2


def test_queue_websocket_tickets_are_tenant_scoped_and_super_admin_global(
    db_session: Session, monkeypatch
) -> None:
    queue, _, client = websocket_fixture(db_session, monkeypatch)
    organization = queue.service.branch.organization
    organization_admin = User(
        full_name="Queue Organization Admin",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.ADMIN,
        organization_id=organization.id,
    )
    db_session.add(organization_admin)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            user_id=organization_admin.id,
            organization_id=organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    other_organization = Organization(
        name="Other Socket Org", slug=f"other-socket-{uuid.uuid4()}"
    )
    other_admin = User(
        full_name="Other Organization Admin",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.ADMIN,
        organization=other_organization,
    )
    branch_staff = User(
        full_name="Assigned Branch Staff",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.STAFF,
        branch_id=queue.service.branch_id,
    )
    other_branch = Branch(name="Other Branch", organization=other_organization)
    other_branch_staff = User(
        full_name="Other Branch Staff",
        email=f"{uuid.uuid4()}@example.com",
        password_hash=hash_password("test-password-123"),
        role=UserRole.STAFF,
        branch=other_branch,
    )
    super_admin = db_session.scalar(
        select(User).where(User.role == UserRole.SUPER_ADMIN)
    )
    if super_admin is None:
        super_admin = User(
            full_name="Platform Owner",
            email=f"{uuid.uuid4()}@example.com",
            password_hash=hash_password("test-password-123"),
            role=UserRole.SUPER_ADMIN,
        )
        db_session.add(super_admin)
    db_session.add_all([other_admin, branch_staff, other_branch_staff])
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            user_id=other_admin.id,
            organization_id=other_organization.id,
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    db_session.commit()

    def issue_queue_ticket(user: User):
        return client.post(
            "/api/v1/auth/ws-ticket",
            json={"queue_id": str(queue.id)},
            headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
        )

    assert issue_queue_ticket(organization_admin).status_code == 200
    assert issue_queue_ticket(other_admin).status_code == 403
    assert issue_queue_ticket(branch_staff).status_code == 200
    assert issue_queue_ticket(other_branch_staff).status_code == 403
    assert client.post(
        "/api/v1/super-admin/ws-ticket",
        headers={"Authorization": f"Bearer {create_access_token(organization_admin.id)}"},
    ).status_code == 403

    super_admin_ticket = issue_queue_ticket(super_admin)
    assert super_admin_ticket.status_code == 200
    with client:
        with client.websocket_connect(
            f"/ws/queues/{queue.id}?ticket={super_admin_ticket.json()['ticket']}"
        ) as socket:
            realtime.publish_nowait(queue.id, "QUEUE_UPDATED", {"status": "paused"})
            assert socket.receive_json()["data"]["status"] == "paused"

    app.dependency_overrides.clear()


def test_super_admin_platform_socket_receives_queue_events(
    db_session: Session, monkeypatch
) -> None:
    queue, _, client = websocket_fixture(db_session, monkeypatch)
    super_admin = db_session.scalar(
        select(User).where(User.role == UserRole.SUPER_ADMIN)
    )
    if super_admin is None:
        super_admin = User(
            full_name="Platform Owner",
            email=f"{uuid.uuid4()}@example.com",
            password_hash=hash_password("test-password-123"),
            role=UserRole.SUPER_ADMIN,
        )
        db_session.add(super_admin)
        db_session.commit()

    response = client.post(
        "/api/v1/super-admin/ws-ticket",
        headers={"Authorization": f"Bearer {create_access_token(super_admin.id)}"},
    )
    assert response.status_code == 200
    with client:
        with client.websocket_connect(
            f"/ws/super-admin?ticket={response.json()['ticket']}"
        ) as socket:
            realtime.publish_nowait(queue.id, "CUSTOMER_JOINED", {"queue_number": 2})
            message = socket.receive_json()
            assert message == {
                "event": "CUSTOMER_JOINED",
                "type": "CUSTOMER_JOINED",
                "queue_id": str(queue.id),
                "data": {"queue_number": 2},
            }

    app.dependency_overrides.clear()
