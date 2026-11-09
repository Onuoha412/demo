"""Add queue capacity and fair priority policies."""

import sqlalchemy as sa

from alembic import op

revision = "0015_queue_capacity_priority"
down_revision = "0014_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    queue_columns = {column["name"] for column in inspector.get_columns("queues")}
    if "capacity_limit" not in queue_columns:
        op.add_column("queues", sa.Column("capacity_limit", sa.Integer(), nullable=True))
    if "priority_enabled" not in queue_columns:
        op.add_column(
            "queues",
            sa.Column(
                "priority_enabled",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
        )

    entry_columns = {
        column["name"] for column in inspector.get_columns("queue_entries")
    }
    if "priority" not in entry_columns:
        op.add_column(
            "queue_entries",
            sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        )

    queue_constraints = {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("queues")
    }
    if "ck_queues_capacity_limit_positive" not in queue_constraints:
        with op.batch_alter_table("queues") as batch:
            batch.create_check_constraint(
                "ck_queues_capacity_limit_positive",
                "capacity_limit IS NULL OR capacity_limit > 0",
            )

    entry_constraints = {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_check_constraints(
            "queue_entries"
        )
    }
    if "ck_queue_entries_priority_range" not in entry_constraints:
        with op.batch_alter_table("queue_entries") as batch:
            batch.create_check_constraint(
                "ck_queue_entries_priority_range", "priority BETWEEN 0 AND 5"
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    queue_columns = {column["name"] for column in inspector.get_columns("queues")}
    if "ck_queues_capacity_limit_positive" in {
        constraint.get("name")
        for constraint in inspector.get_check_constraints("queues")
    }:
        with op.batch_alter_table("queues") as batch:
            batch.drop_constraint("ck_queues_capacity_limit_positive", type_="check")
    if "capacity_limit" in queue_columns:
        op.drop_column("queues", "capacity_limit")
    if "priority_enabled" in queue_columns:
        op.drop_column("queues", "priority_enabled")

    if "ck_queue_entries_priority_range" in {
        constraint.get("name")
        for constraint in inspector.get_check_constraints("queue_entries")
    }:
        with op.batch_alter_table("queue_entries") as batch:
            batch.drop_constraint("ck_queue_entries_priority_range", type_="check")
    if "priority" in {
        column["name"] for column in inspector.get_columns("queue_entries")
    }:
        op.drop_column("queue_entries", "priority")
