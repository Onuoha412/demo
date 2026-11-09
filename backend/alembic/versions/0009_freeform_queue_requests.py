"""Add free-form customer queue requests for staff assignment and approval."""

import sqlalchemy as sa

from alembic import op

revision = "0009_freeform_queue_requests"
down_revision = "0008_organization_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "queue_requests" not in inspector.get_table_names():
        op.create_table(
            "queue_requests",
            sa.Column("customer_id", sa.Uuid(), nullable=False),
            sa.Column("branch_id", sa.Uuid(), nullable=False),
            sa.Column("request_text", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="pending",
                nullable=False,
            ),
            sa.Column("assigned_queue_id", sa.Uuid(), nullable=True),
            sa.Column("queue_entry_id", sa.Uuid(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
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
            sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(
                ["assigned_queue_id"], ["queues.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["queue_entry_id"], ["queue_entries.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("queue_entry_id", name="uq_queue_requests_queue_entry"),
        )
        inspector = sa.inspect(op.get_bind())
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("queue_requests")
    }
    if "ix_queue_requests_customer_created" not in existing_indexes:
        op.create_index(
            "ix_queue_requests_customer_created",
            "queue_requests",
            ["customer_id", "created_at"],
        )
    if "ix_queue_requests_branch_status_created" not in existing_indexes:
        op.create_index(
            "ix_queue_requests_branch_status_created",
            "queue_requests",
            ["branch_id", "status", "created_at"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "queue_requests" not in inspector.get_table_names():
        return
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("queue_requests")
    }
    if "ix_queue_requests_branch_status_created" in existing_indexes:
        op.drop_index(
            "ix_queue_requests_branch_status_created", table_name="queue_requests"
        )
    if "ix_queue_requests_customer_created" in existing_indexes:
        op.drop_index(
            "ix_queue_requests_customer_created", table_name="queue_requests"
        )
    op.drop_table("queue_requests")
