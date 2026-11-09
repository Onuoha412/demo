"""Add durable job payloads and worker leases."""

import sqlalchemy as sa
from alembic import op

revision = "0024_durable_job_leases"
down_revision = "0023_replayable_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("scheduled_jobs")}
    with op.batch_alter_table("scheduled_jobs") as batch_op:
        if "payload" not in columns:
            batch_op.add_column(
                sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
            )
        if "lease_until" not in columns:
            batch_op.add_column(sa.Column("lease_until", sa.DateTime(timezone=True)))
        if "worker_id" not in columns:
            batch_op.add_column(sa.Column("worker_id", sa.String(length=100)))
        if "max_attempts" not in columns:
            batch_op.add_column(
                sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8")
            )


def downgrade() -> None:
    with op.batch_alter_table("scheduled_jobs") as batch_op:
        batch_op.drop_column("max_attempts")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("lease_until")
        batch_op.drop_column("payload")
