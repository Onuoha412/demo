import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from ..api.auth_dependencies import can_access_queue, has_active_organization_admin_membership
from ..db.session import SessionLocal
from ..models import Branch, Queue, User
from ..models.entities import UserRole
from ..services.cache import cache
from ..services.realtime import realtime
from ..services.outbox import replay as replay_outbox
from ..services.queue import QueueService

router = APIRouter(tags=["realtime"])


def _initial_queue_state(queue_id: UUID, since: int | None) -> tuple[list[dict], dict | None]:
    with SessionLocal() as db:
        replayed: list[dict] = []
        replay_complete = False
        if since is not None:
            replayed, replay_complete = replay_outbox(
                db, queue_id=queue_id, after_sequence=since
            )
        snapshot = None
        if since is not None and not replay_complete:
            snapshot = QueueService(db).get_queue(queue_id, 1, 100)
        return replayed, snapshot


@router.websocket("/ws/queues/{queue_id}")
async def queue_socket(websocket: WebSocket, queue_id: UUID) -> None:
    user = None
    is_public = websocket.query_params.get("public") == "1"
    try:
        since = int(websocket.query_params["since"]) if "since" in websocket.query_params else None
    except ValueError:
        await websocket.close(code=4400)
        return
    if is_public:
        with SessionLocal() as db:
            if db.scalar(select(Queue.id).where(Queue.id == queue_id)) is None:
                await websocket.close(code=4404)
                return
        if not await realtime.allow_connection(queue_id):
            await websocket.close(code=4429)
            return
        replayed, snapshot = await asyncio.to_thread(_initial_queue_state, queue_id, since)
        await realtime.connect(queue_id, websocket)
        if snapshot is not None:
            await websocket.send_json(
                {
                    "event": "queue.snapshot",
                    "type": "queue.snapshot",
                    "queue_id": str(queue_id),
                    "data": jsonable_encoder(snapshot),
                }
            )
        for event in replayed:
            await websocket.send_json(event)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            realtime.disconnect(queue_id, websocket)
        return
    ticket = websocket.query_params.get("ticket")
    if ticket:
        ticket_data = await cache.consume_websocket_ticket(ticket)
        if ticket_data and ticket_data.get("queue_id") == str(queue_id):
            try:
                ticket_user_id = UUID(ticket_data["user_id"])
            except (KeyError, TypeError, ValueError):
                user = None
            else:
                with SessionLocal() as db:
                    user = db.get(User, ticket_user_id)
                    queue = db.scalar(select(Queue).where(Queue.id == queue_id))
                    if (
                        user is None
                        or not user.is_active
                        or queue is None
                        or not can_access_queue(db, user, queue)
                    ):
                        user = None

    if user is None:
        await websocket.close(code=4403)
        return

    if not await realtime.allow_connection(queue_id):
        await websocket.close(code=4429)
        return

    replayed, snapshot = await asyncio.to_thread(_initial_queue_state, queue_id, since)
    await realtime.connect(queue_id, websocket)
    if snapshot is not None:
        await websocket.send_json(
            {
                "event": "queue.snapshot",
                "type": "queue.snapshot",
                "queue_id": str(queue_id),
                "data": jsonable_encoder(snapshot),
            }
        )
    for event in replayed:
        await websocket.send_json(event)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect(queue_id, websocket)


@router.websocket("/ws/super-admin")
async def super_admin_socket(websocket: WebSocket) -> None:
    ticket = websocket.query_params.get("ticket")
    ticket_data = await cache.consume_websocket_ticket(ticket or "")
    if not ticket_data or ticket_data.get("queue_id") != "super_admin":
        await websocket.close(code=4401)
        return
    try:
        user_id = UUID(ticket_data["user_id"])
    except (KeyError, TypeError, ValueError):
        await websocket.close(code=4401)
        return

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if (
            user is None
            or not user.is_active
            or user.role is not UserRole.SUPER_ADMIN
        ):
            await websocket.close(code=4403)
            return

    if not await realtime.allow_super_admin_connection(user_id):
        await websocket.close(code=4429)
        return
    await realtime.connect_super_admin(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect_super_admin(websocket)


@router.websocket("/ws/app-updates")
async def app_updates_socket(websocket: WebSocket) -> None:
    ticket = websocket.query_params.get("ticket")
    ticket_data = await cache.consume_websocket_ticket(ticket or "")
    if not ticket_data or ticket_data.get("queue_id") != "app_updates":
        await websocket.close(code=4401)
        return
    try:
        user_id = UUID(ticket_data["user_id"])
    except (KeyError, TypeError, ValueError):
        await websocket.close(code=4401)
        return

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=4403)
            return

    if not await realtime.allow_app_updates_connection(user_id):
        await websocket.close(code=4429)
        return
    await realtime.connect_app_updates(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect_app_updates(websocket)


@router.websocket("/ws/announcements")
async def announcements_socket(websocket: WebSocket) -> None:
    ticket = websocket.query_params.get("ticket")
    ticket_data = await cache.consume_websocket_ticket(ticket or "")
    if not ticket_data or ticket_data.get("queue_id") != "announcements":
        await websocket.close(code=4401)
        return
    try:
        user_id = UUID(ticket_data["user_id"])
    except (KeyError, TypeError, ValueError):
        await websocket.close(code=4401)
        return
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=4403)
            return
        role = user.role.value
        organization_id = user.organization_id
        if organization_id is None and user.branch_id is not None:
            organization_id = db.scalar(
                select(Branch.organization_id).where(Branch.id == user.branch_id)
            )
    if not await realtime.allow_announcement_connection(user_id):
        await websocket.close(code=4429)
        return
    await realtime.connect_announcements(
        websocket,
        role,
        str(organization_id) if organization_id is not None else None,
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect_announcements(websocket)


@router.websocket("/ws/feedback")
async def feedback_socket(websocket: WebSocket) -> None:
    ticket = websocket.query_params.get("ticket")
    ticket_data = await cache.consume_websocket_ticket(ticket or "")
    if not ticket_data or ticket_data.get("queue_id") != "feedback":
        await websocket.close(code=4401)
        return
    try:
        user_id = UUID(ticket_data["user_id"])
    except (KeyError, TypeError, ValueError):
        await websocket.close(code=4401)
        return

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=4403)
            return
        organization_id = user.organization_id
        if organization_id is None and user.branch_id is not None:
            organization_id = db.scalar(
                select(Branch.organization_id).where(Branch.id == user.branch_id)
            )
        if (
            user.role is UserRole.ADMIN
            and user.organization_id is not None
            and not has_active_organization_admin_membership(db, user)
        ):
            await websocket.close(code=4403)
            return
        role = user.role.value

    if not await realtime.allow_feedback_connection(user_id):
        await websocket.close(code=4429)
        return
    await realtime.connect_feedback(websocket, user_id, organization_id, role)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect_feedback(websocket)
