"""Add organization timezones and durable scheduler tables."""

import sqlalchemy as sa
from alembic import op

revision = "0021_time_engine"
down_revision = "0020_user_admin_list_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    organization_columns = (
        {column["name"] for column in inspector.get_columns("organizations")}
        if inspector.has_table("organizations")
        else set()
    )
    if organization_columns and "timezone" not in organization_columns:
        op.add_column(
            "organizations",
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Lagos"),
        )
    if not inspector.has_table("scheduled_jobs"):
        job_constraints = [
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key", name="uq_scheduled_jobs_idempotency_key"),
            sa.CheckConstraint(
                "status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'retrying')",
                name="ck_scheduled_jobs_status",
            ),
        ]
        if inspector.has_table("organizations"):
            job_constraints.insert(
                0,
                sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            )
        op.create_table(
            "scheduled_jobs",
            sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_execution_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_execution_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            *job_constraints,
        )
    existing_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("scheduled_jobs")}
    if "ix_scheduled_jobs_due" not in existing_indexes:
        op.create_index(
            "ix_scheduled_jobs_due",
            "scheduled_jobs",
            ["status", "scheduled_at"],
        )
    if "ix_scheduled_jobs_organization" not in existing_indexes:
        op.create_index(
            "ix_scheduled_jobs_organization",
            "scheduled_jobs",
            ["organization_id", "scheduled_at"],
        )
    if not inspector.has_table("scheduled_job_executions"):
        op.create_table(
            "scheduled_job_executions",
            sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["job_id"], ["scheduled_jobs.id"], ondelete="CASCADE"),
        )
    execution_indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("scheduled_job_executions")
    }
    if "ix_scheduled_job_executions_job_started" not in execution_indexes:
        op.create_index(
            "ix_scheduled_job_executions_job_started",
            "scheduled_job_executions",
            ["job_id", "started_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_scheduled_job_executions_job_started", table_name="scheduled_job_executions")
    op.drop_table("scheduled_job_executions")
    op.drop_index("ix_scheduled_jobs_organization", table_name="scheduled_jobs")
    op.drop_index("ix_scheduled_jobs_due", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
    op.drop_column("organizations", "timezone")
