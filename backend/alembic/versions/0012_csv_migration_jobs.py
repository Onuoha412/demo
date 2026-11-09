"""Add durable CSV migration jobs and external identity mappings."""

import sqlalchemy as sa

from alembic import op

revision = "0012_csv_migration_jobs"
down_revision = "0011_organization_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "migration_jobs" not in tables:
        op.create_table(
            "migration_jobs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
            sa.Column("source_system", sa.String(length=80), nullable=False),
            sa.Column("file_sha256", sa.String(length=64), nullable=False),
            sa.Column(
                "status", sa.String(length=20), server_default="preview", nullable=False
            ),
            sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
            sa.Column("valid_rows", sa.Integer(), server_default="0", nullable=False),
            sa.Column("invalid_rows", sa.Integer(), server_default="0", nullable=False),
            sa.Column("created_rows", sa.Integer(), server_default="0", nullable=False),
            sa.Column("skipped_rows", sa.Integer(), server_default="0", nullable=False),
            sa.Column("rejected_rows", sa.Integer(), server_default="0", nullable=False),
            sa.Column("preview_rows", sa.JSON(), server_default="'[]'", nullable=False),
            sa.Column("result_rows", sa.JSON(), server_default="'[]'", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "status IN ('preview', 'completed', 'failed')",
                name="ck_migration_jobs_status",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("migration_jobs")
    job_indexes = (
        {
            index["name"]
            for index in sa.inspect(op.get_bind()).get_indexes("migration_jobs")
        }
        if "migration_jobs" in tables
        else set()
    )
    if "ix_migration_jobs_organization_created" not in job_indexes:
        op.create_index(
            "ix_migration_jobs_organization_created",
            "migration_jobs",
            ["organization_id", "created_at"],
        )

    if "migration_mappings" not in tables:
        op.create_table(
            "migration_mappings",
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("source_system", sa.String(length=80), nullable=False),
            sa.Column("external_id", sa.String(length=160), nullable=False),
            sa.Column("target_user_id", sa.Uuid(), nullable=False),
            sa.Column("migration_job_id", sa.Uuid(), nullable=False),
            sa.Column("source_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["target_user_id"], ["users.id"], ondelete="RESTRICT"
            ),
            sa.ForeignKeyConstraint(
                ["migration_job_id"], ["migration_jobs.id"], ondelete="RESTRICT"
            ),
            sa.PrimaryKeyConstraint("organization_id", "source_system", "external_id"),
        )
        tables.add("migration_mappings")
    mapping_indexes = (
        {
            index["name"]
            for index in sa.inspect(op.get_bind()).get_indexes("migration_mappings")
        }
        if "migration_mappings" in tables
        else set()
    )
    if "ix_migration_mappings_target_user" not in mapping_indexes:
        op.create_index(
            "ix_migration_mappings_target_user",
            "migration_mappings",
            ["target_user_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_migration_mappings_target_user", table_name="migration_mappings")
    op.drop_table("migration_mappings")
    op.drop_index(
        "ix_migration_jobs_organization_created", table_name="migration_jobs"
    )
    op.drop_table("migration_jobs")
