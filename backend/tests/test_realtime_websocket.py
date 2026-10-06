import uuid
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.api.auth_dependencies import get_db
from app.db.session import SessionLocal
from app.main import app
from app.models import Branch, Organization, Queue, QueueEntry, Service, User
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
    with ExitStack() as sockets:
        first = sockets.enter_context(client.websocket_connect(f"/ws/queues/{queue.id}?public=1"))
        second = sockets.enter_context(client.websocket_connect(f"/ws/queues/{queue.id}?public=1"))
        realtime.publish_nowait(queue.id, "QUEUE_UPDATED", {"status": "paused"})
        assert first.receive_json()["event"] == "QUEUE_UPDATED"
        assert second.receive_json()["data"]["status"] == "paused"
    with client.websocket_connect(f"/ws/queues/{queue.id}?public=1") as reconnected:
        realtime.publish_nowait(queue.id, "CUSTOMER_JOINED", {"queue_number": 1})
        assert reconnected.receive_json()["event"] == "CUSTOMER_JOINED"
