from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models import Branch, Organization, Queue, Service
from ...schemas.catalog import BranchSummary, OrganizationSummary, ServiceSummary

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/organizations", response_model=list[OrganizationSummary])
def organizations(db: Session = Depends(get_db)) -> list[Organization]:
    return db.query(Organization).filter(Organization.is_active.is_(True)).order_by(Organization.name).all()


@router.get("/branches", response_model=list[BranchSummary])
def branches(
    organization_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Branch]:
    query = db.query(Branch).filter(Branch.is_active.is_(True))
    if organization_id:
        query = query.filter(Branch.organization_id == organization_id)
    return query.order_by(Branch.name).all()


@router.get("/services", response_model=list[ServiceSummary])
def services(
    branch_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ServiceSummary]:
    filters = [Service.is_active.is_(True)]
    if branch_id:
        filters.append(Service.branch_id == branch_id)
    queue_id = (
        select(Queue.id)
        .where(Queue.service_id == Service.id)
        .order_by(Queue.created_at)
        .limit(1)
        .scalar_subquery()
    )
    items = db.execute(
        select(Service, queue_id).where(*filters).order_by(Service.name)
    ).all()
    return [
        ServiceSummary(
            id=item.id,
            branch_id=item.branch_id,
            name=item.name,
            code=item.code,
            description=item.description,
            average_service_minutes=item.average_service_minutes,
            queue_id=service_queue_id,
        )
        for item, service_queue_id in items
    ]


@router.get("/services/{service_id}", response_model=ServiceSummary)
def service_detail(service_id: UUID, db: Session = Depends(get_db)) -> ServiceSummary:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    queue = db.query(Queue).filter(Queue.service_id == service.id).first()
    return ServiceSummary(
        id=service.id,
        branch_id=service.branch_id,
        name=service.name,
        code=service.code,
        description=service.description,
        average_service_minutes=service.average_service_minutes,
        queue_id=queue.id if queue else None,
    )
