import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import (
    AuditLog,
    Branch,
    MigrationJob,
    MigrationMapping,
    Organization,
    OrganizationMembership,
    User,
)
from app.models.entities import UserRole


def _admin_client(db: Session, organization: Organization) -> TestClient:
    admin = User(
        full_name="Migration Admin",
        email=f"migration-admin-{uuid.uuid4()}@example.test",
        password_hash=hash_password("migration-admin-password"),
        role=UserRole.ADMIN,
        organization=organization,
    )
    db.add(admin)
    db.flush()
    db.add(
        OrganizationMembership(
            user_id=admin.id,
            organization_id=organization.id,
            role=UserRole.ADMIN.value,
        )
    )
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(str(admin.id))}"
    return client


def _csv_upload(content: bytes, filename: str = "customers.csv"):
    return {"file": (filename, content, "text/csv")}


def test_migration_template_requires_admin_and_has_exact_columns() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/admin/migrations/template.csv")
    assert response.status_code == 401


def test_csv_preview_import_and_idempotent_rerun(db_session: Session) -> None:
    organization = Organization(
        name="Migration Organization",
        slug=f"migration-{uuid.uuid4()}",
    )
    db_session.add(organization)
    db_session.commit()
    client = _admin_client(db_session, organization)

    template = client.get("/api/v1/admin/migrations/template.csv")
    assert template.status_code == 200
    assert template.text.strip() == "external_id,full_name,email,role,branch_id"

    source_csv = (
        b"external_id,full_name,email,role,branch_id\n"
        b"legacy-1,Ada Customer,ada-migration@example.test,customer,\n"
        b"legacy-2,Grace Customer,grace-migration@example.test,customer,\n"
    )
    preview = client.post(
        "/api/v1/admin/migrations/preview",
        data={"source_system": "  Legacy.CRM "},
        files=_csv_upload(source_csv),
    )
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()
    assert preview_data["status"] == "preview"
    assert preview_data["source_system"] == "legacy.crm"
    assert preview_data["total_rows"] == 2
    assert preview_data["valid_rows"] == 2
    assert {row["status"] for row in preview_data["preview_rows"]} == {"valid"}
    assert "email" not in preview_data["preview_rows"][0]

    changed_csv = source_csv.replace(b"Ada Customer", b"Changed Customer")
    mismatched = client.post(
        f"/api/v1/admin/migrations/{preview_data['id']}/import",
        data={"confirm": "true"},
        files=_csv_upload(changed_csv),
    )
    assert mismatched.status_code == 409

    imported = client.post(
        f"/api/v1/admin/migrations/{preview_data['id']}/import",
        data={"confirm": "true"},
        files=_csv_upload(source_csv),
    )
    assert imported.status_code == 200, imported.text
    imported_data = imported.json()
    assert imported_data["status"] == "completed"
    assert imported_data["created_rows"] == 2
    assert imported_data["rejected_rows"] == 0
    assert "email" not in imported_data["result_rows"][0]

    migrated_users = list(
        db_session.scalars(
            select(User).where(
                User.email.in_(
                    ["ada-migration@example.test", "grace-migration@example.test"]
                )
            )
        )
    )
    assert len(migrated_users) == 2
    assert all(user.role is UserRole.CUSTOMER for user in migrated_users)
    assert all(user.organization_id == organization.id for user in migrated_users)
    assert all(user.is_active for user in migrated_users)
    assert all(user.auth_provider == "local" for user in migrated_users)
    assert all(user.password_hash != "password" for user in migrated_users)
    assert db_session.scalar(
        select(MigrationMapping).where(
            MigrationMapping.organization_id == organization.id,
            MigrationMapping.source_system == "legacy.crm",
            MigrationMapping.external_id == "legacy-1",
        )
    )

    second_preview = client.post(
        "/api/v1/admin/migrations/preview",
        data={"source_system": "legacy.crm"},
        files=_csv_upload(source_csv),
    )
    assert second_preview.status_code == 200
    assert second_preview.json()["skipped_rows"] == 2
    second_import = client.post(
        f"/api/v1/admin/migrations/{second_preview.json()['id']}/import",
        data={"confirm": "true"},
        files=_csv_upload(source_csv),
    )
    assert second_import.status_code == 200
    assert second_import.json()["created_rows"] == 0
    assert second_import.json()["skipped_rows"] == 2
    assert len(
        list(
            db_session.scalars(
                select(User).where(
                    User.email.in_(
                        ["ada-migration@example.test", "grace-migration@example.test"]
                    )
                )
            )
        )
    ) == 2
    audit_actions = set(
        db_session.scalars(
            select(AuditLog.action).where(AuditLog.action.like("migration.%"))
        )
    )
    assert {"migration.previewed", "migration.imported"} <= audit_actions
    history = client.get("/api/v1/admin/migrations")
    assert history.status_code == 200
    assert history.json()["total"] == 2


def test_migration_preview_rejects_privileged_roles_and_existing_email(
    db_session: Session,
) -> None:
    organization = Organization(
        name="Validation Organization",
        slug=f"validation-{uuid.uuid4()}",
    )
    existing_user = User(
        full_name="Existing",
        email="existing-migration@example.test",
        password_hash=hash_password("existing-password"),
        role=UserRole.CUSTOMER,
    )
    db_session.add_all([organization, existing_user])
    db_session.commit()
    client = _admin_client(db_session, organization)

    invalid_csv = (
        b"external_id,full_name,email,role,branch_id\n"
        b"staff-1,Imported Staff,staff-migration@example.test,admin,\n"
        b"customer-1,Existing Customer,existing-migration@example.test,customer,\n"
    )
    response = client.post(
        "/api/v1/admin/migrations/preview",
        data={"source_system": "legacy"},
        files=_csv_upload(invalid_csv),
    )
    assert response.status_code == 200
    result = response.json()
    assert result["valid_rows"] == 0
    assert result["invalid_rows"] == 2
    assert "Only customer and staff accounts" in result["preview_rows"][0]["errors"][0]
    assert "never linked automatically" in result["preview_rows"][1]["errors"][0]

    imported = client.post(
        f"/api/v1/admin/migrations/{result['id']}/import",
        data={"confirm": "true"},
        files=_csv_upload(invalid_csv),
    )
    assert imported.status_code == 200
    assert imported.json()["created_rows"] == 0
    assert imported.json()["rejected_rows"] == 2


def test_staff_import_requires_and_syncs_an_active_tenant_branch(
    db_session: Session,
) -> None:
    organization = Organization(
        name="Staff Migration Organization",
        slug=f"staff-migration-{uuid.uuid4()}",
    )
    other_organization = Organization(
        name="Other Staff Organization",
        slug=f"other-staff-{uuid.uuid4()}",
    )
    local_branch = Branch(name="Local Branch", organization=organization)
    foreign_branch = Branch(name="Foreign Branch", organization=other_organization)
    db_session.add_all([local_branch, foreign_branch])
    db_session.commit()
    client = _admin_client(db_session, organization)

    staff_csv = (
        "external_id,full_name,email,role,branch_id\n"
        f"staff-local,Local Staff,local-staff-{uuid.uuid4()}@example.test,staff,{local_branch.id}\n"
        f"staff-foreign,Foreign Staff,foreign-staff-{uuid.uuid4()}@example.test,staff,{foreign_branch.id}\n"
    ).encode()
    preview = client.post(
        "/api/v1/admin/migrations/preview",
        data={"source_system": "legacy"},
        files=_csv_upload(staff_csv),
    )
    assert preview.status_code == 200, preview.text
    preview_rows = preview.json()["preview_rows"]
    assert [row["status"] for row in preview_rows] == ["valid", "invalid"]
    assert "belong to the target organization" in preview_rows[1]["errors"][0]

    imported = client.post(
        f"/api/v1/admin/migrations/{preview.json()['id']}/import",
        data={"confirm": "true"},
        files=_csv_upload(staff_csv),
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created_rows"] == 1
    assert imported.json()["rejected_rows"] == 1
    staff = db_session.scalar(
        select(User).where(User.email.like("local-staff-%@example.test"))
    )
    assert staff is not None
    assert staff.role is UserRole.STAFF
    assert staff.branch_id == local_branch.id
    assert staff.organization_id == organization.id
    membership = db_session.get(
        OrganizationMembership,
        (staff.id, organization.id),
    )
    assert membership is not None
    assert membership.role == UserRole.STAFF.value
    assert membership.is_active


def test_migration_is_organization_scoped_and_requires_confirmation(
    db_session: Session,
) -> None:
    organization = Organization(
        name="Scoped Migration Organization",
        slug=f"scoped-migration-{uuid.uuid4()}",
    )
    other_organization = Organization(
        name="Other Migration Organization",
        slug=f"other-migration-{uuid.uuid4()}",
    )
    db_session.add_all([organization, other_organization])
    db_session.commit()
    client = _admin_client(db_session, organization)
    upload = _csv_upload(
        b"external_id,full_name,email,role,branch_id\n"
        b"id-1,Scoped Customer,scoped-customer@example.test,customer,\n"
    )

    cross_tenant = client.post(
        "/api/v1/admin/migrations/preview",
        data={
            "source_system": "legacy",
            "organization_id": str(other_organization.id),
        },
        files=upload,
    )
    assert cross_tenant.status_code == 404

    preview = client.post(
        "/api/v1/admin/migrations/preview",
        data={"source_system": "legacy"},
        files=upload,
    )
    assert preview.status_code == 200
    not_confirmed = client.post(
        f"/api/v1/admin/migrations/{preview.json()['id']}/import",
        data={"confirm": "false"},
        files=upload,
    )
    assert not_confirmed.status_code == 422
    assert client.get(
        f"/api/v1/admin/migrations/{uuid.uuid4()}"
    ).status_code == 404


def test_migration_csv_headers_and_size_are_bounded(db_session: Session) -> None:
    organization = Organization(
        name="CSV Bounds Organization",
        slug=f"csv-bounds-{uuid.uuid4()}",
    )
    db_session.add(organization)
    db_session.commit()
    client = _admin_client(db_session, organization)

    bad_headers = client.post(
        "/api/v1/admin/migrations/preview",
        data={"source_system": "legacy"},
        files=_csv_upload(b"email,full_name\nperson@example.test,Person\n"),
    )
    assert bad_headers.status_code == 422

    too_large = client.post(
        "/api/v1/admin/migrations/preview",
        data={"source_system": "legacy"},
        files=_csv_upload(b"x" * (2 * 1024 * 1024 + 1)),
    )
    assert too_large.status_code == 413


def test_migration_job_database_model_is_durable(db_session: Session) -> None:
    organization = Organization(
        name="Job History Organization",
        slug=f"job-history-{uuid.uuid4()}",
    )
    db_session.add(organization)
    admin = User(
        full_name="Job History Admin",
        email=f"job-history-admin-{uuid.uuid4()}@example.test",
        password_hash=hash_password("job-history-password"),
        role=UserRole.ADMIN,
        organization=organization,
    )
    db_session.add(admin)
    db_session.flush()
    job = MigrationJob(
        organization_id=organization.id,
        requested_by_user_id=admin.id,
        source_system="legacy",
        file_sha256="a" * 64,
        status="preview",
        preview_rows=[],
        result_rows=[],
    )
    db_session.add(job)
    db_session.commit()
    assert db_session.get(MigrationJob, job.id) is not None
