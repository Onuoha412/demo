from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session, joinedload

from ...api.auth_dependencies import require_admin
from ...core.security import hash_password
from ...db.session import get_db
from ...models import Branch, Counter, Organization, Queue, QueueEntry, Service, User
from ...models.entities import QueueEntryStatus, UserRole
from ...schemas.admin import (
    AdminUserPageResponse, AdminUserResponse, AnalyticsResponse, BranchCreate, BranchUpdate, CounterCreate, CounterUpdate,
    AdminQueueAuditResponse, OrganizationCreate, OrganizationUpdate, PageResponse, QueueCreate, QueueStatusUpdate,
    QueueUpdate, ServiceCreate, ServiceUpdate, UserCreate, UserUpdate,
)
from ...schemas.queue import PositionResponse
from ...services.queue import QueueService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _page(model, db: Session, page: int, page_size: int, *filters):
    query = select(model).where(*filters).order_by(model.created_at.desc())
    total = db.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    items = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    return PageResponse(items=jsonable_encoder(items),
                        total=total, page=page, page_size=page_size)


def _get(db: Session, model, item_id: UUID):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


def _save(db: Session, item):
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Resource conflicts with an existing record")
    return item


@router.get("/organizations", response_model=PageResponse)
def list_organizations(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db)):
    return _page(Organization, db, page, page_size)


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    return _save(db, Organization(**payload.model_dump()))


@router.get("/organizations/{item_id}")
def get_organization(item_id: UUID, db: Session = Depends(get_db)):
    return _get(db, Organization, item_id)


@router.put("/organizations/{item_id}")
@router.patch("/organizations/{item_id}")
def update_organization(item_id: UUID, payload: OrganizationUpdate, db: Session = Depends(get_db)):
    item = _get(db, Organization, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    return _save(db, item)


@router.delete("/organizations/{item_id}")
def deactivate_organization(item_id: UUID, db: Session = Depends(get_db)):
    item = _get(db, Organization, item_id); item.is_active = False
    return _save(db, item)


@router.get("/branches", response_model=PageResponse)
def list_branches(organization_id: UUID | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    filters = (Branch.organization_id == organization_id,) if organization_id else ()
    return _page(Branch, db, page, page_size, *filters)


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def create_branch(payload: BranchCreate, db: Session = Depends(get_db)):
    _get(db, Organization, payload.organization_id)
    return _save(db, Branch(**payload.model_dump()))


@router.get("/branches/{item_id}")
def get_branch(item_id: UUID, db: Session = Depends(get_db)): return _get(db, Branch, item_id)


@router.put("/branches/{item_id}")
@router.patch("/branches/{item_id}")
def update_branch(item_id: UUID, payload: BranchUpdate, db: Session = Depends(get_db)):
    item = _get(db, Branch, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    return _save(db, item)


@router.delete("/branches/{item_id}")
def deactivate_branch(item_id: UUID, db: Session = Depends(get_db)):
    item = _get(db, Branch, item_id); item.is_active = False
    return _save(db, item)


@router.get("/services", response_model=PageResponse)
def list_services(branch_id: UUID | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    filters = (Service.branch_id == branch_id,) if branch_id else ()
    return _page(Service, db, page, page_size, *filters)


@router.post("/services", status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)):
    _get(db, Branch, payload.branch_id)
    return _save(db, Service(**payload.model_dump()))


@router.get("/services/{item_id}")
def get_service(item_id: UUID, db: Session = Depends(get_db)): return _get(db, Service, item_id)


@router.put("/services/{item_id}")
@router.patch("/services/{item_id}")
def update_service(item_id: UUID, payload: ServiceUpdate, db: Session = Depends(get_db)):
    item = _get(db, Service, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    return _save(db, item)


@router.delete("/services/{item_id}")
def deactivate_service(item_id: UUID, db: Session = Depends(get_db)):
    item = _get(db, Service, item_id); item.is_active = False
    return _save(db, item)


@router.get("/counters", response_model=PageResponse)
def list_counters(branch_id: UUID | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    filters = (Counter.branch_id == branch_id,) if branch_id else ()
    return _page(Counter, db, page, page_size, *filters)


@router.post("/counters", status_code=status.HTTP_201_CREATED)
def create_counter(payload: CounterCreate, db: Session = Depends(get_db)):
    _get(db, Branch, payload.branch_id)
    return _save(db, Counter(**payload.model_dump()))


@router.get("/counters/{item_id}")
def get_counter(item_id: UUID, db: Session = Depends(get_db)): return _get(db, Counter, item_id)


@router.put("/counters/{item_id}")
@router.patch("/counters/{item_id}")
def update_counter(item_id: UUID, payload: CounterUpdate, db: Session = Depends(get_db)):
    item = _get(db, Counter, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    return _save(db, item)


@router.delete("/counters/{item_id}")
def deactivate_counter(item_id: UUID, db: Session = Depends(get_db)):
    item = _get(db, Counter, item_id); item.is_active = False
    return _save(db, item)


@router.get("/queues", response_model=PageResponse)
def list_queues(service_id: UUID | None = None, page: int = Query(1, ge=1),
                page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    filters = (Queue.service_id == service_id,) if service_id else ()
    return _page(Queue, db, page, page_size, *filters)


@router.post("/queues", status_code=status.HTTP_201_CREATED)
def create_queue(payload: QueueCreate, db: Session = Depends(get_db)):
    _get(db, Service, payload.service_id)
    return _save(db, Queue(**payload.model_dump()))


@router.get("/queues/{item_id}")
def get_queue(item_id: UUID, db: Session = Depends(get_db)): return _get(db, Queue, item_id)


@router.get("/queues/{queue_id}/entries", response_model=AdminQueueAuditResponse)
def queue_entries(
    queue_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    queue = db.scalar(
        select(Queue)
        .options(joinedload(Queue.service))
        .where(Queue.id == queue_id)
    )
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")

    queue_data = QueueService(db).get_queue(queue_id, page, page_size)
    entry_ids = [entry["id"] for entry in queue_data["entries"]]
    customers_by_entry_id = {}
    if entry_ids:
        entries = db.scalars(
            select(QueueEntry)
            .options(joinedload(QueueEntry.customer))
            .where(QueueEntry.id.in_(entry_ids))
        )
        customers_by_entry_id = {
            entry.id: {
                "id": entry.customer.id,
                "full_name": entry.customer.full_name,
                "email": entry.customer.email,
            }
            for entry in entries
        }

    return {
        **queue_data,
        "service_id": queue.service_id,
        "service_name": queue.service.name,
        "branch_id": queue.service.branch_id,
        "entries": [
            {**entry, "customer": customers_by_entry_id[entry["id"]]}
            for entry in queue_data["entries"]
        ],
    }


@router.post("/queue-entries/{entry_id}/verify", response_model=PositionResponse)
def verify_queue_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return QueueService(db).verify_request(entry_id, admin.id)


@router.put("/queues/{item_id}")
@router.patch("/queues/{item_id}")
def update_queue(item_id: UUID, payload: QueueUpdate, db: Session = Depends(get_db)):
    item = _get(db, Queue, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    return _save(db, item)


@router.put("/queues/{item_id}/status")
@router.patch("/queues/{item_id}/status")
def update_queue_status(item_id: UUID, payload: QueueStatusUpdate, db: Session = Depends(get_db)):
    return QueueService(db).set_status(item_id, payload.status)


@router.delete("/queues/{item_id}")
def close_queue(item_id: UUID, db: Session = Depends(get_db)):
    item = _get(db, Queue, item_id)
    from ...models.entities import QueueStatus
    item.status = QueueStatus.CLOSED
    return _save(db, item)


@router.get("/users", response_model=AdminUserPageResponse)
def list_users(role: str | None = None, search: str | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    filters = []
    if role: filters.append(User.role == role)
    if search: filters.append(or_(User.email.ilike(f"%{search}%"), User.full_name.ilike(f"%{search}%")))
    return _page(User, db, page, page_size, *filters)


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    values = payload.model_dump(exclude={"password"})
    values["password_hash"] = hash_password(payload.password)
    if payload.branch_id is not None:
        branch = _get(db, Branch, payload.branch_id)
        if (
            payload.organization_id is not None
            and payload.organization_id != branch.organization_id
        ):
            raise HTTPException(
                status_code=422,
                detail="User organization must match the assigned branch",
            )
        values["organization_id"] = branch.organization_id
    return _save(db, User(**values))


@router.get("/users/{item_id}", response_model=AdminUserResponse)
def get_user(item_id: UUID, db: Session = Depends(get_db)): return _get(db, User, item_id)


@router.put("/users/{item_id}", response_model=AdminUserResponse)
@router.patch("/users/{item_id}", response_model=AdminUserResponse)
def update_user(item_id: UUID, payload: UserUpdate, db: Session = Depends(get_db)):
    item = _get(db, User, item_id)
    values = payload.model_dump(exclude_unset=True)
    role = values.get("role", item.role)
    branch_id = values.get("branch_id", item.branch_id)
    if role is UserRole.STAFF and branch_id is None:
        raise HTTPException(
            status_code=422,
            detail="Staff users must be assigned to a branch",
        )
    if branch_id is not None:
        branch = _get(db, Branch, branch_id)
        organization_id = values.get("organization_id", item.organization_id)
        if organization_id is not None and organization_id != branch.organization_id:
            if "organization_id" in values:
                raise HTTPException(
                    status_code=422,
                    detail="User organization must match the assigned branch",
                )
        values["organization_id"] = branch.organization_id
    if "password" in values:
        values["password_hash"] = hash_password(values.pop("password"))
    for key, value in values.items(): setattr(item, key, value)
    return _save(db, item)


@router.delete("/users/{item_id}", response_model=AdminUserResponse)
def deactivate_user(item_id: UUID, db: Session = Depends(get_db)):
    item = _get(db, User, item_id); item.is_active = False
    return _save(db, item)


@router.post("/{resource}/{item_id}/activate")
def activate(resource: str, item_id: UUID, db: Session = Depends(get_db)):
    model = {"organizations": Organization, "branches": Branch, "services": Service,
             "counters": Counter, "users": User}.get(resource)
    if model is None: raise HTTPException(status_code=404, detail="Resource not found")
    item = _get(db, model, item_id); item.is_active = True
    return _save(db, item)


@router.post("/{resource}/{item_id}/deactivate")
def deactivate(resource: str, item_id: UUID, db: Session = Depends(get_db)):
    model = {"organizations": Organization, "branches": Branch, "services": Service,
             "counters": Counter, "users": User}.get(resource)
    if model is None: raise HTTPException(status_code=404, detail="Resource not found")
    item = _get(db, model, item_id); item.is_active = False
    return _save(db, item)


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(start: datetime | None = None, end: datetime | None = None,
              _: User = Depends(require_admin), db: Session = Depends(get_db)):
    entry_filters = []
    if start: entry_filters.append(QueueEntry.joined_at >= start)
    if end: entry_filters.append(QueueEntry.joined_at <= end)
    def count(model, *filters): return db.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    entries = count(QueueEntry, *entry_filters)
    def ec(status_value): return count(QueueEntry, QueueEntry.status == status_value, *entry_filters)
    wait_avg = db.scalar(select(func.avg(func.extract("epoch", QueueEntry.called_at - QueueEntry.joined_at) / 60)).where(
        QueueEntry.called_at.is_not(None), *entry_filters)) or 0
    service_avg = db.scalar(select(func.avg(func.extract("epoch", QueueEntry.completed_at - QueueEntry.service_started_at) / 60)).where(
        QueueEntry.completed_at.is_not(None), QueueEntry.service_started_at.is_not(None), *entry_filters)) or 0
    completed = ec(QueueEntryStatus.COMPLETED)
    skipped = ec(QueueEntryStatus.SKIPPED)
    cancelled = ec(QueueEntryStatus.CANCELLED)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_filter = QueueEntry.completed_at >= today_start
    busiest_service = db.execute(
        select(Service.name, func.count(QueueEntry.id))
        .join(Queue, Queue.service_id == Service.id).join(QueueEntry, QueueEntry.queue_id == Queue.id)
        .where(QueueEntry.status == QueueEntryStatus.COMPLETED, today_filter)
        .group_by(Service.name).order_by(func.count(QueueEntry.id).desc()).limit(1)
    ).first()
    busiest_hour = db.execute(
        select(func.extract("hour", QueueEntry.completed_at), func.count(QueueEntry.id))
        .where(QueueEntry.status == QueueEntryStatus.COMPLETED, today_filter)
        .group_by(func.extract("hour", QueueEntry.completed_at)).order_by(func.count(QueueEntry.id).desc()).limit(1)
    ).first()
    return AnalyticsResponse(organizations=count(Organization), branches=count(Branch),
        services=count(Service), counters=count(Counter), queues=count(Queue), users=count(User),
        active_users=count(User, User.is_active.is_(True)), queue_entries=entries,
        waiting_entries=ec(QueueEntryStatus.WAITING), serving_entries=ec(QueueEntryStatus.SERVING),
        completed_entries=ec(QueueEntryStatus.COMPLETED), skipped_entries=ec(QueueEntryStatus.SKIPPED),
        cancelled_entries=cancelled, average_wait_minutes=round(float(wait_avg), 2),
        average_service_minutes=round(float(service_avg), 2), period_start=start, period_end=end,
        customers_served_today=count(QueueEntry, QueueEntry.status == QueueEntryStatus.COMPLETED, today_filter),
        customers_waiting=ec(QueueEntryStatus.WAITING),
        average_waiting_time=round(float(wait_avg), 2), average_service_time=round(float(service_avg), 2),
        completion_rate=round(completed / entries * 100, 2) if entries else 0,
        skip_rate=round(skipped / entries * 100, 2) if entries else 0,
        cancellation_rate=round(cancelled / entries * 100, 2) if entries else 0,
        busiest_service={"name": busiest_service[0], "count": busiest_service[1]} if busiest_service else None,
        busiest_hour={"hour": int(busiest_hour[0]), "count": busiest_hour[1]} if busiest_hour else None)
