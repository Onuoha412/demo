import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, false, func, inspect as sqlalchemy_inspect, select, or_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from ...api.auth_dependencies import require_admin, require_admin_write_reauth
from ...core.security import hash_password
from ...db.session import get_db
from ...models import (
    AuthSession,
    Branch,
    Counter,
    Organization,
    OrganizationMembership,
    Queue,
    QueueEntry,
    QueueRequest,
    Service,
    User,
)
from ...models.entities import QueueEntryStatus, UserRole
from ...schemas.admin import (
    AdminUserPageResponse, AdminUserResponse, AnalyticsResponse, BranchCreate, BranchUpdate, CounterCreate, CounterUpdate,
    AdminQueueAuditResponse, OrganizationCreate, OrganizationUpdate, PageResponse, QueueCreate, QueueStatusUpdate,
    QueueUpdate, ServiceCreate, ServiceUpdate, UserCreate, UserUpdate,
)
from ...schemas.queue import PositionResponse
from ...services.queue import QueueService
from ...services.audit import record_audit

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_write_reauth)],
)


def _organization_filter(model, admin: User):
    if admin.role is UserRole.SUPER_ADMIN:
        return None
    organization_id = admin.organization_id
    if organization_id is None:
        return false()
    if model is Organization:
        return Organization.id == organization_id
    if model is Branch:
        return Branch.organization_id == organization_id
    if model is Service:
        return Service.branch.has(Branch.organization_id == organization_id)
    if model is Counter:
        return Counter.branch.has(Branch.organization_id == organization_id)
    if model is Queue:
        return Queue.service.has(
            Service.branch.has(Branch.organization_id == organization_id)
        )
    if model is QueueEntry:
        return QueueEntry.queue.has(
            Queue.service.has(Service.branch.has(Branch.organization_id == organization_id))
        )
    if model is QueueRequest:
        return QueueRequest.branch_id.in_(
            select(Branch.id).where(Branch.organization_id == organization_id)
        )
    if model is User:
        organization_branches = select(Branch.id).where(
            Branch.organization_id == organization_id
        )
        customers_in_organization = (
            select(QueueEntry.customer_id)
            .join(Queue, QueueEntry.queue_id == Queue.id)
            .join(Service, Queue.service_id == Service.id)
            .join(Branch, Service.branch_id == Branch.id)
            .where(Branch.organization_id == organization_id)
        )
        return or_(
            User.organization_id == organization_id,
            User.branch_id.in_(organization_branches),
            User.id.in_(customers_in_organization),
        )
    raise ValueError(f"No organization scope defined for {model.__name__}")


def _page(
    model,
    db: Session,
    page: int,
    page_size: int,
    *filters,
    admin: User,
):
    scope = _organization_filter(model, admin)
    if scope is not None:
        filters = (*filters, scope)
    query = select(model).where(*filters).order_by(model.created_at.desc())
    total = db.scalar(select(func.count()).select_from(model).where(*filters)) or 0
    entities = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    items = [
        {
            column.key: getattr(entity, column.key)
            for column in sqlalchemy_inspect(type(entity)).column_attrs
        }
        for entity in entities
    ]
    return PageResponse(items=jsonable_encoder(items),
                        total=total, page=page, page_size=page_size)


def _get(db: Session, model, item_id: UUID, admin: User | None = None):
    statement = select(model).where(model.id == item_id)
    if admin is not None:
        scope = _organization_filter(model, admin)
        if scope is not None:
            statement = statement.where(scope)
    item = db.scalar(statement)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


def _sync_organization_membership(
    db: Session,
    user: User,
    actor_user_id: UUID | None,
) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.STAFF) or user.organization_id is None:
        memberships = list(
            db.scalars(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.is_active.is_(True),
                )
            )
        )
        for membership in memberships:
            membership.is_active = False
        return

    membership = db.get(
        OrganizationMembership,
        (user.id, user.organization_id),
    )
    if membership is None:
        db.add(
            OrganizationMembership(
                user_id=user.id,
                organization_id=user.organization_id,
                role=user.role.value,
                is_active=user.is_active,
                assigned_by_user_id=actor_user_id,
            )
        )
    else:
        membership.role = user.role.value
        membership.is_active = user.is_active
        membership.assigned_by_user_id = actor_user_id


def _save(
    db: Session,
    item,
    *,
    admin: User | None = None,
    action: str | None = None,
    details: dict[str, object] | None = None,
):
    db.add(item)
    try:
        db.flush()
        if admin is not None and action is not None:
            record_audit(
                db,
                actor_user_id=admin.id,
                action=action,
                target_type=item.__class__.__name__.lower(),
                target_id=item.id,
                details=details,
            )
        db.commit()
        db.refresh(item)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Resource conflicts with an existing record")
    return item


@router.get("/organizations", response_model=PageResponse)
def list_organizations(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db),
                       admin: User = Depends(require_admin)):
    return _page(Organization, db, page, page_size, admin=admin)


@router.post("/organizations/{item_id}/approve")
def approve_organization(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if admin.role is not UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only a Super Admin can approve organizations.")
    organization = _get(db, Organization, item_id, admin)
    organization.is_approved = True
    organization.is_active = True
    pending_users = list(
        db.scalars(
            select(User).where(
                User.organization_id == organization.id,
                User.approval_pending.is_(True),
            )
        )
    )
    for user in pending_users:
        user.approval_pending = False
        user.is_active = True
        _sync_organization_membership(db, user, admin.id)
    db.add(organization)
    db.add_all(pending_users)
    record_audit(
        db,
        actor_user_id=admin.id,
        action="organization.approved",
        target_type="organization",
        target_id=organization.id,
        details={"approved_accounts": len(pending_users)},
    )
    try:
        db.commit()
        db.refresh(organization)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Organization approval could not be completed.",
        ) from None
    return {
        "organization": organization,
        "approved_accounts": len(pending_users),
    }


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if admin.role is UserRole.ADMIN and admin.organization_id is not None:
        raise HTTPException(
            status_code=403,
            detail="Organization administrators cannot create additional organizations.",
        )
    organization = Organization(**payload.model_dump())
    if admin.role is UserRole.ADMIN:
        db.add(organization)
        try:
            db.flush()
            admin.organization_id = organization.id
            _sync_organization_membership(db, admin, admin.id)
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Organization could not be created.",
            ) from None
    return _save(
        db,
        organization,
        admin=admin,
        action="organization.created",
    )


@router.get("/organizations/{item_id}")
def get_organization(item_id: UUID, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    return _get(db, Organization, item_id, admin)


@router.put("/organizations/{item_id}")
@router.patch("/organizations/{item_id}")
def update_organization(
    item_id: UUID,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Organization, item_id, admin)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    return _save(
        db,
        item,
        admin=admin,
        action="organization.updated",
        details={"changed_fields": list(values)},
    )


@router.delete("/organizations/{item_id}")
def deactivate_organization(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if admin.role is not UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only a Super Admin can deactivate organizations.")
    item = _get(db, Organization, item_id, admin)
    item.is_active = False
    return _save(db, item, admin=admin, action="organization.deactivated")


@router.get("/branches", response_model=PageResponse)
def list_branches(organization_id: UUID | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    filters = (Branch.organization_id == organization_id,) if organization_id else ()
    return _page(Branch, db, page, page_size, *filters, admin=admin)


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def create_branch(
    payload: BranchCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _get(db, Organization, payload.organization_id, admin)
    return _save(
        db,
        Branch(**payload.model_dump()),
        admin=admin,
        action="branch.created",
    )


@router.get("/branches/{item_id}")
def get_branch(item_id: UUID, db: Session = Depends(get_db),
               admin: User = Depends(require_admin)):
    return _get(db, Branch, item_id, admin)


@router.put("/branches/{item_id}")
@router.patch("/branches/{item_id}")
def update_branch(
    item_id: UUID,
    payload: BranchUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Branch, item_id, admin)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    return _save(
        db,
        item,
        admin=admin,
        action="branch.updated",
        details={"changed_fields": list(values)},
    )


@router.delete("/branches/{item_id}")
def deactivate_branch(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Branch, item_id, admin)
    item.is_active = False
    return _save(db, item, admin=admin, action="branch.deactivated")


@router.get("/services", response_model=PageResponse)
def list_services(branch_id: UUID | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    filters = (Service.branch_id == branch_id,) if branch_id else ()
    return _page(Service, db, page, page_size, *filters, admin=admin)


@router.post("/services", status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _get(db, Branch, payload.branch_id, admin)
    return _save(
        db,
        Service(**payload.model_dump()),
        admin=admin,
        action="service.created",
    )


@router.get("/services/{item_id}")
def get_service(item_id: UUID, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    return _get(db, Service, item_id, admin)


@router.put("/services/{item_id}")
@router.patch("/services/{item_id}")
def update_service(
    item_id: UUID,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Service, item_id, admin)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    return _save(
        db,
        item,
        admin=admin,
        action="service.updated",
        details={"changed_fields": list(values)},
    )


@router.delete("/services/{item_id}")
def deactivate_service(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Service, item_id, admin)
    item.is_active = False
    return _save(db, item, admin=admin, action="service.deactivated")


@router.get("/counters", response_model=PageResponse)
def list_counters(branch_id: UUID | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    filters = (Counter.branch_id == branch_id,) if branch_id else ()
    return _page(Counter, db, page, page_size, *filters, admin=admin)


@router.post("/counters", status_code=status.HTTP_201_CREATED)
def create_counter(
    payload: CounterCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _get(db, Branch, payload.branch_id, admin)
    return _save(
        db,
        Counter(**payload.model_dump()),
        admin=admin,
        action="counter.created",
    )


@router.get("/counters/{item_id}")
def get_counter(item_id: UUID, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    return _get(db, Counter, item_id, admin)


@router.put("/counters/{item_id}")
@router.patch("/counters/{item_id}")
def update_counter(
    item_id: UUID,
    payload: CounterUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Counter, item_id, admin)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    return _save(
        db,
        item,
        admin=admin,
        action="counter.updated",
        details={"changed_fields": list(values)},
    )


@router.delete("/counters/{item_id}")
def deactivate_counter(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Counter, item_id, admin)
    item.is_active = False
    return _save(db, item, admin=admin, action="counter.deactivated")


@router.get("/queues", response_model=PageResponse)
def list_queues(service_id: UUID | None = None, page: int = Query(1, ge=1),
                page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    filters = (Queue.service_id == service_id,) if service_id else ()
    return _page(Queue, db, page, page_size, *filters, admin=admin)


@router.post("/queues", status_code=status.HTTP_201_CREATED)
def create_queue(
    payload: QueueCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _get(db, Service, payload.service_id, admin)
    return _save(
        db,
        Queue(**payload.model_dump()),
        admin=admin,
        action="queue.created",
    )


@router.get("/queues/{item_id}")
def get_queue(item_id: UUID, db: Session = Depends(get_db),
              admin: User = Depends(require_admin)):
    return _get(db, Queue, item_id, admin)


@router.get("/queues/{queue_id}/entries", response_model=AdminQueueAuditResponse)
def queue_entries(
    queue_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    statement = (
        select(Queue)
        .options(joinedload(Queue.service))
        .where(Queue.id == queue_id)
    )
    scope = _organization_filter(Queue, admin)
    if scope is not None:
        statement = statement.where(scope)
    queue = db.scalar(statement)
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
    entry = _get(db, QueueEntry, entry_id, admin)
    return QueueService(db).verify_request(entry.id, admin.id)


@router.put("/queues/{item_id}")
@router.patch("/queues/{item_id}")
def update_queue(
    item_id: UUID,
    payload: QueueUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Queue, item_id, admin)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(item, key, value)
    return _save(
        db,
        item,
        admin=admin,
        action="queue.updated",
        details={"changed_fields": list(values)},
    )


@router.put("/queues/{item_id}/status")
@router.patch("/queues/{item_id}/status")
def update_queue_status(
    item_id: UUID,
    payload: QueueStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _get(db, Queue, item_id, admin)
    result = QueueService(db).set_status(item_id, payload.status)
    record_audit(
        db,
        actor_user_id=admin.id,
        action="queue.status_changed",
        target_type="queue",
        target_id=item_id,
        details={"status": payload.status.value},
    )
    db.commit()
    return result


@router.delete("/queues/{item_id}")
def close_queue(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, Queue, item_id, admin)
    from ...models.entities import QueueStatus
    item.status = QueueStatus.CLOSED
    return _save(db, item, admin=admin, action="queue.closed")


@router.get("/users", response_model=AdminUserPageResponse)
def list_users(
    role: UserRole | None = None,
    search: str | None = Query(default=None, max_length=100),
    active: bool | None = None,
    auth_provider: str | None = Query(default=None, pattern="^local$"),
    organization_id: UUID | None = None,
    branch_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    filters = []
    if role: filters.append(User.role == role)
    if active is not None: filters.append(User.is_active.is_(active))
    if auth_provider: filters.append(User.auth_provider == auth_provider)
    if organization_id: filters.append(User.organization_id == organization_id)
    if branch_id: filters.append(User.branch_id == branch_id)
    normalized_search = search.strip() if search else ""
    if normalized_search:
        search_pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern),
                cast(User.id, String).ilike(search_pattern),
            )
        )
    result = _page(User, db, page, page_size, *filters, admin=admin)
    organization_ids: set[UUID] = set()
    user_organization_ids: dict[str, UUID] = {}
    for item in result.items:
        organization_id = item["organization_id"]
        if organization_id is None:
            continue
        try:
            normalized_id = (
                organization_id
                if isinstance(organization_id, UUID)
                else UUID(str(organization_id))
            )
        except (TypeError, ValueError):
            continue
        organization_ids.add(normalized_id)
        user_organization_ids[str(organization_id)] = normalized_id
    organization_status = (
        dict(
            db.execute(
                select(Organization.id, Organization.is_approved).where(
                    Organization.id.in_(organization_ids)
                )
            ).all()
        )
        if organization_ids
        else {}
    )
    for item in result.items:
        organization_id = user_organization_ids.get(
            str(item["organization_id"])
        )
        item["organization_approved"] = (
            organization_status.get(organization_id)
            if organization_id is not None
            else None
        )
    return result


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if payload.role is UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Super Admin access can only be assigned through the protected bootstrap command.",
        )
    values = payload.model_dump(exclude={"password"})
    if admin.role is UserRole.ADMIN:
        if payload.organization_id not in (None, admin.organization_id):
            raise HTTPException(
                status_code=404,
                detail="Organization not found.",
            )
        values["organization_id"] = admin.organization_id
    elif payload.role is UserRole.ADMIN and payload.organization_id is None:
        raise HTTPException(
            status_code=422,
            detail="Organization administrators must be assigned to an organization.",
        )
    values["password_hash"] = hash_password(payload.password)
    if payload.branch_id is not None:
        branch = _get(db, Branch, payload.branch_id, admin)
        if (
            payload.organization_id is not None
            and payload.organization_id != branch.organization_id
        ):
            raise HTTPException(
                status_code=422,
                detail="User organization must match the assigned branch",
            )
        values["organization_id"] = branch.organization_id
    if values["organization_id"] is not None:
        organization = _get(db, Organization, values["organization_id"], admin)
        if not organization.is_approved:
            raise HTTPException(
                status_code=409,
                detail="Approve the organization before creating accounts for it.",
            )
    user = User(**values)
    db.add(user)
    db.flush()
    _sync_organization_membership(db, user, admin.id)
    record_audit(
        db,
        actor_user_id=admin.id,
        action="user.created",
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "role": user.role.value},
    )
    return _save(db, user)


@router.post("/users/{item_id}/approve", response_model=AdminUserResponse)
def approve_user_registration(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, User, item_id, admin)
    if item.role not in (UserRole.STAFF, UserRole.ADMIN):
        raise HTTPException(
            status_code=409,
            detail="Only staff or administrator registration requests can be approved.",
        )
    if not item.approval_pending:
        raise HTTPException(
            status_code=409,
            detail="This account does not have a pending registration request.",
        )
    if item.role is UserRole.ADMIN and admin.role is not UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only a Super Admin can approve organization administrator requests.",
        )
    organization = (
        db.get(Organization, item.organization_id)
        if item.organization_id is not None
        else None
    )
    if organization is None or not organization.is_active or not organization.is_approved:
        raise HTTPException(
            status_code=409,
            detail="Approve and activate the organization before approving this account.",
        )
    if item.role is UserRole.STAFF and (
        item.branch_id is None
        or item.branch is None
        or not item.branch.is_active
        or item.branch.organization_id != organization.id
    ):
        raise HTTPException(
            status_code=409,
            detail="Assign this staff account to an active branch before approval.",
        )

    item.approval_pending = False
    item.is_active = True
    _sync_organization_membership(db, item, admin.id)
    return _save(
        db,
        item,
        admin=admin,
        action="user.registration_approved",
        details={"role": item.role.value},
    )


@router.get("/users/{item_id}", response_model=AdminUserResponse)
def get_user(item_id: UUID, db: Session = Depends(get_db),
             admin: User = Depends(require_admin)):
    return _get(db, User, item_id, admin)


@router.put("/users/{item_id}", response_model=AdminUserResponse)
@router.patch("/users/{item_id}", response_model=AdminUserResponse)
def update_user(
    item_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, User, item_id, admin)
    values = payload.model_dump(exclude_unset=True)
    if admin.role is UserRole.ADMIN:
        if values.get("organization_id", admin.organization_id) != admin.organization_id:
            raise HTTPException(status_code=404, detail="User not found.")
        values["organization_id"] = item.organization_id
    requested_role = values.get("role")
    if item.role is UserRole.SUPER_ADMIN or requested_role is UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Super Admin privileges cannot be changed through regular user management.",
        )
    if requested_role is not None and requested_role is not item.role:
        if item.id == admin.id and requested_role is not UserRole.ADMIN:
            raise HTTPException(
                status_code=409,
                detail="You cannot remove your own administrator access.",
            )
        if item.is_active and item.role is UserRole.ADMIN and requested_role is not UserRole.ADMIN:
            active_admins = db.scalar(
                select(func.count(User.id)).where(
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                    User.organization_id == admin.organization_id,
                )
            ) or 0
            if active_admins <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="At least one active administrator must remain.",
                )
    if item.approval_pending and (
        "organization_id" in values or "branch_id" in values
    ):
        raise HTTPException(
            status_code=409,
            detail="Pending accounts must be approved with their organization.",
        )
    role = values.get("role", item.role)
    branch_id = values.get("branch_id", item.branch_id)
    if role is UserRole.STAFF and branch_id is None:
        raise HTTPException(
            status_code=422,
            detail="Staff users must be assigned to a branch",
        )
    if branch_id is not None:
        branch = _get(db, Branch, branch_id, admin)
        organization_id = values.get("organization_id", item.organization_id)
        if organization_id is not None and organization_id != branch.organization_id:
            if "organization_id" in values:
                raise HTTPException(
                    status_code=422,
                    detail="User organization must match the assigned branch",
                )
        values["organization_id"] = branch.organization_id
    organization_id = values.get("organization_id", item.organization_id)
    if organization_id is not None:
        organization = _get(db, Organization, organization_id, admin)
        if not organization.is_approved:
            raise HTTPException(
                status_code=409,
                detail="Approve the organization before assigning accounts to it.",
            )
    if "password" in values:
        values["password_hash"] = hash_password(values.pop("password"))
    if "password_hash" in values or requested_role is not None:
        db.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == item.id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
    if requested_role is not None and requested_role is not item.role:
        record_audit(
            db,
            actor_user_id=admin.id,
            action="user.role_changed",
            target_type="user",
            target_id=item.id,
            details={"from": item.role.value, "to": requested_role.value},
        )
    elif "password_hash" in values:
        record_audit(
            db,
            actor_user_id=admin.id,
            action="user.password_reset_by_admin",
            target_type="user",
            target_id=item.id,
        )
    for key, value in values.items(): setattr(item, key, value)
    _sync_organization_membership(db, item, admin.id)
    return _save(db, item)


@router.delete("/users/{item_id}", response_model=AdminUserResponse)
def deactivate_user(
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = _get(db, User, item_id, admin)
    return _deactivate_user(db, item, admin)


def _deactivate_user(db: Session, item: User, admin: User) -> AdminUserResponse:
    if item.role is UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Super Admin accounts cannot be deactivated through regular user management.",
        )
    if item.id == admin.id:
        raise HTTPException(
            status_code=409,
            detail="You cannot deactivate your own administrator account.",
        )
    if item.is_active and item.role is UserRole.ADMIN:
        active_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
                *(
                    [User.organization_id == admin.organization_id]
                    if admin.role is UserRole.ADMIN
                    else []
                ),
            )
        ) or 0
        if active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail="At least one active administrator must remain.",
            )
    item.is_active = False
    _sync_organization_membership(db, item, admin.id)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == item.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    record_audit(
        db,
        actor_user_id=admin.id,
        action="user.deactivated",
        target_type="user",
        target_id=item.id,
        details={"role": item.role.value},
    )
    return _save(db, item)


@router.post("/{resource}/{item_id}/activate")
def activate(
    resource: str,
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    model = {"organizations": Organization, "branches": Branch, "services": Service,
             "counters": Counter, "users": User}.get(resource)
    if model is None: raise HTTPException(status_code=404, detail="Resource not found")
    item = _get(db, model, item_id, admin)
    if isinstance(item, Organization) and not item.is_approved:
        raise HTTPException(
            status_code=409,
            detail="Use the organization approval action to approve pending requests.",
        )
    if isinstance(item, User) and (
        item.role is UserRole.SUPER_ADMIN
        or item.approval_pending
        or (item.organization is not None and not item.organization.is_approved)
    ):
        raise HTTPException(
            status_code=409,
            detail="Approve this user's organization before activating the account.",
        )
    item.is_active = True
    if isinstance(item, User):
        _sync_organization_membership(db, item, admin.id)
        record_audit(
            db,
            actor_user_id=admin.id,
            action="user.activated",
            target_type="user",
            target_id=item.id,
        )
        return _save(db, item)
    return _save(
        db,
        item,
        admin=admin,
        action=f"{model.__name__.lower()}.activated",
    )


@router.post("/{resource}/{item_id}/deactivate")
def deactivate(
    resource: str,
    item_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    model = {"organizations": Organization, "branches": Branch, "services": Service,
             "counters": Counter, "users": User}.get(resource)
    if model is None: raise HTTPException(status_code=404, detail="Resource not found")
    item = _get(db, model, item_id, admin)
    if isinstance(item, User):
        return _deactivate_user(db, item, admin)
    item.is_active = False
    return _save(
        db,
        item,
        admin=admin,
        action=f"{model.__name__.lower()}.deactivated",
    )


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(start: datetime | None = None, end: datetime | None = None,
              admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _organization_filter(QueueEntry, admin)
    entry_filters = []
    if start: entry_filters.append(QueueEntry.joined_at >= start)
    if end: entry_filters.append(QueueEntry.joined_at <= end)
    def count(model, *filters):
        scope = _organization_filter(model, admin)
        all_filters = (*filters, *((scope,) if scope is not None else ()))
        return db.scalar(
            select(func.count()).select_from(model).where(*all_filters)
        ) or 0

    entries = count(QueueEntry, *entry_filters)
    def ec(status_value): return count(QueueEntry, QueueEntry.status == status_value, *entry_filters)
    entry_scope = _organization_filter(QueueEntry, admin)
    wait_avg = db.scalar(select(func.avg(func.extract("epoch", QueueEntry.called_at - QueueEntry.joined_at) / 60)).where(
        QueueEntry.called_at.is_not(None), *entry_filters,
        *((entry_scope,) if entry_scope is not None else ()))) or 0
    service_avg = db.scalar(select(func.avg(func.extract("epoch", QueueEntry.completed_at - QueueEntry.service_started_at) / 60)).where(
        QueueEntry.completed_at.is_not(None), QueueEntry.service_started_at.is_not(None), *entry_filters,
        *((entry_scope,) if entry_scope is not None else ()))) or 0
    completed = ec(QueueEntryStatus.COMPLETED)
    skipped = ec(QueueEntryStatus.SKIPPED)
    cancelled = ec(QueueEntryStatus.CANCELLED)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_filter = QueueEntry.completed_at >= today_start
    busiest_service = db.execute(
        select(Service.name, func.count(QueueEntry.id))
        .join(Queue, Queue.service_id == Service.id).join(QueueEntry, QueueEntry.queue_id == Queue.id)
        .join(Branch, Service.branch_id == Branch.id)
        .where(QueueEntry.status == QueueEntryStatus.COMPLETED, today_filter,
               *((Branch.organization_id == admin.organization_id,)
                 if admin.role is UserRole.ADMIN else ()))
        .group_by(Service.name).order_by(func.count(QueueEntry.id).desc()).limit(1)
    ).first()
    busiest_hour = db.execute(
        select(func.extract("hour", QueueEntry.completed_at), func.count(QueueEntry.id))
        .join(Queue, QueueEntry.queue_id == Queue.id)
        .join(Service, Queue.service_id == Service.id)
        .join(Branch, Service.branch_id == Branch.id)
        .where(QueueEntry.status == QueueEntryStatus.COMPLETED, today_filter)
        .where(*((Branch.organization_id == admin.organization_id,)
                 if admin.role is UserRole.ADMIN else ()))
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


def _spreadsheet_safe(value: str) -> str:
    if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


@router.get("/reports/queue-entries.csv")
def export_queue_entries(
    start: datetime | None = None,
    end: datetime | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status_code=422,
            detail="Report start date must be on or before the end date.",
        )

    statement = (
        select(QueueEntry)
        .join(QueueEntry.queue)
        .join(Queue.service)
        .join(Service.branch)
        .options(
            joinedload(QueueEntry.customer),
            joinedload(QueueEntry.queue)
            .joinedload(Queue.service)
            .joinedload(Service.branch),
        )
        .order_by(QueueEntry.joined_at.desc(), QueueEntry.id)
        .execution_options(yield_per=500)
    )
    scope = _organization_filter(QueueEntry, admin)
    if scope is not None:
        statement = statement.where(scope)
    if start is not None:
        statement = statement.where(QueueEntry.joined_at >= start)
    if end is not None:
        statement = statement.where(QueueEntry.joined_at <= end)

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "entry_id",
                "ticket",
                "queue",
                "service",
                "branch",
                "customer_name",
                "customer_email",
                "status",
                "joined_at",
                "called_at",
                "service_started_at",
                "completed_at",
                "estimated_wait_minutes",
            ]
        )
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for entry in db.scalars(statement):
            values = [
                str(entry.id),
                f"{entry.queue.prefix}{entry.queue_number}",
                _spreadsheet_safe(entry.queue.name),
                _spreadsheet_safe(entry.queue.service.name),
                _spreadsheet_safe(entry.queue.service.branch.name),
                _spreadsheet_safe(entry.customer.full_name),
                _spreadsheet_safe(entry.customer.email),
                entry.status.value,
                entry.joined_at.isoformat(),
                entry.called_at.isoformat() if entry.called_at else "",
                entry.service_started_at.isoformat()
                if entry.service_started_at
                else "",
                entry.completed_at.isoformat() if entry.completed_at else "",
                entry.estimated_wait_minutes
                if entry.estimated_wait_minutes is not None
                else "",
            ]
            writer.writerow(values)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        rows(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="queueless-queue-report.csv"',
            "Cache-Control": "no-store",
        },
    )
