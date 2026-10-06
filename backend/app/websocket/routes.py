from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from ..db.session import SessionLocal
from ..models import Queue, QueueEntry, User
from ..models.entities import UserRole
from ..services.cache import cache
from ..services.realtime import realtime

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/queues/{queue_id}")
async def queue_socket(websocket: WebSocket, queue_id: UUID) -> None:
    user = None
    is_public = websocket.query_params.get("public") == "1"
    if is_public:
        with SessionLocal() as db:
            if db.scalar(select(Queue.id).where(Queue.id == queue_id)) is None:
                await websocket.close(code=4404)
                return
        if not await realtime.allow_connection(queue_id):
            await websocket.close(code=4429)
            return
        await realtime.connect(queue_id, websocket)
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
            with SessionLocal() as db:
                user = db.get(User, ticket_data["user_id"])
                queue = db.scalar(select(Queue).where(Queue.id == queue_id))
                if user is None or not user.is_active or queue is None:
                    user = None
                elif user.role is UserRole.STAFF and queue.service.branch_id != user.branch_id:
                    user = None
                elif user.role not in (UserRole.CUSTOMER, UserRole.STAFF, UserRole.ADMIN):
                    user = None
                elif user.role is UserRole.CUSTOMER:
                    has_entry = db.scalar(
                        select(QueueEntry.id).where(
                            QueueEntry.queue_id == queue_id,
                            QueueEntry.customer_id == user.id,
                        )
                    )
                    if has_entry is None:
                        user = None

    if user is None:
        await websocket.close(code=4403)
        return

    if not await realtime.allow_connection(queue_id):
        await websocket.close(code=4429)
        return

    await realtime.connect(queue_id, websocket)
    try:
        while True:
            # Keeping the socket open also lets clients send ping/text frames.
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime.disconnect(queue_id, websocket)
