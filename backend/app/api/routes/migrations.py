import csv
import hashlib
import io
import json
import re
import secrets
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ...api.auth_dependencies import require_admin, require_admin_write_reauth
from ...core.security import hash_password
from ...db.session import get_db
from ...models import (
    Branch,
    MigrationJob,
    MigrationMapping,
    Organization,
    OrganizationMembership,
    User,
)
from ...models.entities import UserRole
from ...schemas.admin import MigrationJobPageResponse, MigrationJobResponse
from ...services.audit import record_audit

router = APIRouter(
    prefix="/admin/migrations",
    tags=["admin", "migrations"],
    dependencies=[Depends(require_admin_write_reauth)],
)

_CSV_COLUMNS = ("external_id", "full_name", "email", "role", "branch_id")
_MAX_FILE_SIZE = 2 * 1024 * 1024
_MAX_ROWS = 5000
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
def _organization_id(
    db: Session,
    admin: User,
    requested_id: UUID | None,
) -> UUID:
    if admin.role is UserRole.SUPER_ADMIN:
        if requested_id is None:
            raise HTTPException(
                status_code=422,
                detail="Super Admins must select an organization for an import.",
            )
        organization_id = requested_id
    else:
        if admin.organization_id is None:
            raise HTTPException(
                status_code=403,
                detail="Assign this administrator to an organization before importing data.",
            )
        organization_id = admin.organization_id
        if requested_id is not None and requested_id != organization_id:
            raise HTTPException(status_code=404, detail="Organization not found.")

    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    if not organization.is_active or not organization.is_approved:
        raise HTTPException(
            status_code=409,
            detail="The organization must be active and approved before importing data.",
        )
    return organization_id


def _source_system(value: str) -> str:
    source = value.strip().casefold()
    if (
        not source
        or len(source) > 80
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]*", source) is None
    ):
        raise HTTPException(
            status_code=422,
            detail="Source system must use 1-80 letters, digits, dots, underscores, or hyphens.",
        )
    return source


def _upload_bytes(upload: UploadFile) -> bytes:
    if not (upload.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a .csv file.")
    content = upload.file.read(_MAX_FILE_SIZE + 1)
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="CSV files must be no larger than 2 MiB.",
        )
    return content


def _parse_csv(content: bytes) -> list[dict[str, object]]:
    try:
        source = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="CSV files must use UTF-8 encoding.",
        ) from None

    reader = csv.DictReader(io.StringIO(source, newline=""), strict=True)
    headers = reader.fieldnames
    if (
        headers is None
        or len(headers) != len(_CSV_COLUMNS)
        or len(set(headers)) != len(headers)
        or set(headers) != set(_CSV_COLUMNS)
    ):
        raise HTTPException(
            status_code=422,
            detail="CSV headers must be exactly: " + ", ".join(_CSV_COLUMNS) + ".",
        )

    rows: list[dict[str, object]] = []
    try:
        for row_number, values in enumerate(reader, start=2):
            if row_number > _MAX_ROWS + 1:
                raise HTTPException(
                    status_code=413,
                    detail=f"CSV files may contain at most {_MAX_ROWS} data rows.",
                )
            errors: list[str] = []
            if None in values:
                errors.append("Row has more fields than the header.")
            external_id = (values.get("external_id") or "").strip()
            full_name = (values.get("full_name") or "").strip()
            email = (values.get("email") or "").strip().lower()
            role = (values.get("role") or "").strip().casefold()
            if not external_id:
                errors.append("External ID is required.")
            elif len(external_id) > 160:
                errors.append("External ID must be 160 characters or fewer.")
            if not full_name:
                errors.append("Full name is required.")
            elif len(full_name) > 160:
                errors.append("Full name must be 160 characters or fewer.")
            if len(email) > 320 or _EMAIL_PATTERN.fullmatch(email) is None:
                errors.append("Enter a valid email address of at most 320 characters.")
            branch_id_raw = (values.get("branch_id") or "").strip()
            branch_id: UUID | None = None
            if role not in (UserRole.CUSTOMER.value, UserRole.STAFF.value):
                errors.append("Only customer and staff accounts can be imported.")
            elif role == UserRole.STAFF.value:
                try:
                    branch_id = UUID(branch_id_raw)
                except ValueError:
                    errors.append("Staff rows require a valid branch ID.")
            elif branch_id_raw:
                errors.append("Customer rows must leave branch_id blank.")
            if any(values.get(column) is None for column in _CSV_COLUMNS):
                errors.append("Row is missing one or more required fields.")
            rows.append(
                {
                    "row_number": row_number,
                    "external_id": external_id or None,
                    "full_name": full_name,
                    "email": email,
                    "role": role,
                    "branch_id": branch_id,
                    "errors": errors,
                    "status": "invalid" if errors else "valid",
                }
            )
    except csv.Error:
        raise HTTPException(status_code=422, detail="CSV syntax is invalid.") from None

    if not rows:
        raise HTTPException(status_code=422, detail="The CSV contains no data rows.")
    return rows


def _validate_rows(
    db: Session,
    rows: list[dict[str, object]],
    organization_id: UUID,
    source_system: str,
) -> list[dict[str, object]]:
    seen_external_ids: set[str] = set()
    seen_emails: set[str] = set()
    for row in rows:
        external_id = row["external_id"]
        email = row["email"]
        errors = row["errors"]
        if external_id is not None:
            if external_id in seen_external_ids:
                errors.append("External ID appears more than once in this CSV.")
            seen_external_ids.add(external_id)
        if email:
            if email in seen_emails:
                errors.append("Email appears more than once in this CSV.")
            seen_emails.add(email)
        if errors:
            row["status"] = "invalid"

    identifiers = list(seen_external_ids)
    existing_identifiers: set[str] = set()
    for offset in range(0, len(identifiers), 500):
        existing_identifiers.update(
            db.scalars(
                select(MigrationMapping.external_id).where(
                    MigrationMapping.organization_id == organization_id,
                    MigrationMapping.source_system == source_system,
                    MigrationMapping.external_id.in_(
                        identifiers[offset : offset + 500]
                    ),
                )
            )
        )

    emails = list(seen_emails)
    existing_emails: set[str] = set()
    for offset in range(0, len(emails), 500):
        existing_emails.update(
            email.casefold()
            for email in db.scalars(
                select(User.email).where(
                    func.lower(User.email).in_(emails[offset : offset + 500])
                )
            )
        )

    branch_ids = {
        row["branch_id"]
        for row in rows
        if row["status"] == "valid" and row["branch_id"] is not None
    }
    valid_branch_ids: set[UUID] = set()
    if branch_ids:
        valid_branch_ids.update(
            db.scalars(
                select(Branch.id).where(
                    Branch.id.in_(branch_ids),
                    Branch.organization_id == organization_id,
                    Branch.is_active.is_(True),
                )
            )
        )

    for row in rows:
        if row["status"] != "valid":
            continue
        if row["role"] == UserRole.STAFF.value and row["branch_id"] not in valid_branch_ids:
            row["errors"].append(
                "Staff branch must be active and belong to the target organization."
            )
            row["status"] = "invalid"
        elif row["external_id"] in existing_identifiers:
            row["status"] = "skipped"
        elif row["email"].casefold() in existing_emails:
            row["errors"].append(
                "Email is already registered; existing accounts are never linked automatically."
            )
            row["status"] = "invalid"
    return rows


def _public_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "row_number": row["row_number"],
            "external_id": row["external_id"],
            "status": row["status"],
            "errors": row["errors"],
        }
        for row in rows
    ]


@router.get("/template.csv")
def download_template() -> Response:
    output = io.StringIO(newline="")
    csv.writer(output).writerow(_CSV_COLUMNS)
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="queueless-import-template.csv"'
        },
    )


@router.post("/preview", response_model=MigrationJobResponse)
def preview(
    file: UploadFile = File(...),
    source_system: str = Form(..., min_length=1, max_length=80),
    organization_id: UUID | None = Form(default=None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MigrationJob:
    source = _source_system(source_system)
    target_organization_id = _organization_id(db, admin, organization_id)
    content = _upload_bytes(file)
    rows = _validate_rows(
        db,
        _parse_csv(content),
        target_organization_id,
        source,
    )
    job = MigrationJob(
        id=uuid.uuid4(),
        organization_id=target_organization_id,
        requested_by_user_id=admin.id,
        source_system=source,
        file_sha256=hashlib.sha256(content).hexdigest(),
        status="preview",
        total_rows=len(rows),
        valid_rows=sum(row["status"] == "valid" for row in rows),
        invalid_rows=sum(row["status"] == "invalid" for row in rows),
        skipped_rows=sum(row["status"] == "skipped" for row in rows),
        preview_rows=_public_rows(rows),
    )
    db.add(job)
    record_audit(
        db,
        actor_user_id=admin.id,
        action="migration.previewed",
        target_type="migration_job",
        target_id=job.id,
        details={
            "organization_id": str(target_organization_id),
            "source_system": source,
            "file_sha256": job.file_sha256,
            "total_rows": job.total_rows,
            "valid_rows": job.valid_rows,
            "invalid_rows": job.invalid_rows,
        },
    )
    try:
        db.commit()
        db.refresh(job)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Migration preview could not be saved.",
        ) from None
    return job


@router.get("", response_model=MigrationJobPageResponse)
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MigrationJobPageResponse:
    statement = select(MigrationJob)
    count_statement = select(func.count(MigrationJob.id))
    if admin.role is UserRole.ADMIN:
        if admin.organization_id is None:
            return MigrationJobPageResponse(
                items=[], total=0, page=page, page_size=page_size
            )
        scope = MigrationJob.organization_id == admin.organization_id
        statement = statement.where(scope)
        count_statement = count_statement.where(scope)
    jobs = list(
        db.scalars(
            statement.order_by(MigrationJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return MigrationJobPageResponse(
        items=jobs,
        total=db.scalar(count_statement) or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=MigrationJobResponse)
def get_job(
    job_id: UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MigrationJob:
    statement = select(MigrationJob).where(MigrationJob.id == job_id)
    if admin.role is UserRole.ADMIN:
        if admin.organization_id is None:
            raise HTTPException(status_code=404, detail="Migration job not found.")
        statement = statement.where(
            MigrationJob.organization_id == admin.organization_id
        )
    job = db.scalar(statement)
    if job is None:
        raise HTTPException(status_code=404, detail="Migration job not found.")
    return job


@router.post("/{job_id}/import", response_model=MigrationJobResponse)
def import_csv(
    job_id: UUID,
    file: UploadFile = File(...),
    confirm: bool = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MigrationJob:
    if not confirm:
        raise HTTPException(
            status_code=422,
            detail="Set confirm=true to explicitly authorize this import.",
        )
    job = db.scalar(select(MigrationJob).where(MigrationJob.id == job_id))
    if (
        job is None
        or (
            admin.role is UserRole.ADMIN
            and job.organization_id != admin.organization_id
        )
    ):
        raise HTTPException(status_code=404, detail="Migration job not found.")
    if job.status != "preview":
        raise HTTPException(
            status_code=409,
            detail="Only a pending preview can be imported. Create a new preview to retry.",
        )
    target_organization_id = _organization_id(db, admin, job.organization_id)
    content = _upload_bytes(file)
    file_hash = hashlib.sha256(content).hexdigest()
    if file_hash != job.file_sha256:
        raise HTTPException(
            status_code=409,
            detail="The uploaded file differs from the previewed file.",
        )
    rows = _validate_rows(
        db,
        _parse_csv(content),
        target_organization_id,
        job.source_system,
    )

    results: list[dict[str, object]] = []
    created_count = 0
    skipped_count = 0
    rejected_count = 0
    try:
        for row in rows:
            if row["status"] == "skipped":
                skipped_count += 1
                result_status = "skipped"
            elif row["status"] == "invalid":
                rejected_count += 1
                result_status = "rejected"
            else:
                row_source = json.dumps(
                    {
                        "external_id": row["external_id"],
                        "full_name": row["full_name"],
                        "email": row["email"],
                        "role": row["role"],
                        "branch_id": (
                            str(row["branch_id"]) if row["branch_id"] is not None else None
                        ),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                user_role = UserRole(row["role"])
                user = User(
                    full_name=row["full_name"],
                    email=row["email"],
                    password_hash=hash_password(secrets.token_urlsafe(48)),
                    organization_id=target_organization_id,
                    branch_id=row["branch_id"],
                    role=user_role,
                    is_active=True,
                    approval_pending=False,
                    auth_provider="local",
                )
                db.add(user)
                db.flush()
                if user_role is UserRole.STAFF:
                    db.add(
                        OrganizationMembership(
                            user_id=user.id,
                            organization_id=target_organization_id,
                            role=UserRole.STAFF.value,
                            is_active=True,
                            assigned_by_user_id=admin.id,
                        )
                    )
                db.add(
                    MigrationMapping(
                        organization_id=target_organization_id,
                        source_system=job.source_system,
                        external_id=row["external_id"],
                        target_user_id=user.id,
                        migration_job_id=job.id,
                        source_hash=hashlib.sha256(row_source).hexdigest(),
                    )
                )
                created_count += 1
                result_status = "created"
            results.append(
                {
                    "row_number": row["row_number"],
                    "external_id": row["external_id"],
                    "status": result_status,
                    "errors": row["errors"],
                }
            )

        job.status = "completed"
        job.total_rows = len(rows)
        job.valid_rows = sum(row["status"] == "valid" for row in rows)
        job.invalid_rows = sum(row["status"] == "invalid" for row in rows)
        job.created_rows = created_count
        job.skipped_rows = skipped_count
        job.rejected_rows = rejected_count
        job.result_rows = results
        record_audit(
            db,
            actor_user_id=admin.id,
            action="migration.imported",
            target_type="migration_job",
            target_id=job.id,
            details={
                "organization_id": str(target_organization_id),
                "source_system": job.source_system,
                "file_sha256": file_hash,
                "created_rows": created_count,
                "skipped_rows": skipped_count,
                "rejected_rows": rejected_count,
            },
        )
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        failed_job = db.get(MigrationJob, job_id)
        if failed_job is not None:
            failed_job.status = "failed"
            failed_job.created_rows = 0
            failed_job.skipped_rows = sum(row["status"] == "skipped" for row in rows)
            failed_job.rejected_rows = len(rows) - failed_job.skipped_rows
            failed_job.result_rows = [
                {
                    "row_number": row["row_number"],
                    "external_id": row["external_id"],
                    "status": (
                        "skipped" if row["status"] == "skipped" else "rejected"
                    ),
                    "errors": (
                        row["errors"]
                        if row["status"] == "invalid"
                        else [
                            "Import conflicted with an account or mapping created concurrently."
                        ]
                        if row["status"] == "valid"
                        else []
                    ),
                }
                for row in rows
            ]
            record_audit(
                db,
                actor_user_id=admin.id,
                action="migration.failed",
                target_type="migration_job",
                target_id=job_id,
                details={
                    "organization_id": str(target_organization_id),
                    "reason": "concurrent_identity_conflict",
                },
            )
            db.commit()
        raise HTTPException(
            status_code=409,
            detail="Import conflicted with an account or mapping created concurrently. Create a new preview before retrying.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Migration import could not be completed.",
        ) from None
    return job
