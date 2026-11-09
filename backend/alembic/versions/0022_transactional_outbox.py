"""Add persistent transactional outbox events."""

import sqlalchemy as sa
from alembic import op

revision = "0022_transactional_outbox"
down_revision = "0021_time_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("outbox_events"):
        constraints = [
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "status IN ('pending', 'processing', 'published', 'dead')",
                name="ck_outbox_events_status",
            ),
        ]
        if inspector.has_table("queues"):
            constraints.insert(
                0,
                sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
            )
        op.create_table(
            "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("queue_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
            *constraints,
        )
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("outbox_events")}
    with op.batch_alter_table("outbox_events") as batch_op:
        if "sequence_number" not in columns:
            batch_op.add_column(sa.Column("sequence_number", sa.Integer(), nullable=True))
        if "idempotency_key" not in columns:
            batch_op.add_column(sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        if "created_at" not in columns:
            batch_op.add_column(
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True)
            )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("outbox_events")}
    if "ix_outbox_events_delivery" not in indexes:
        op.create_index("ix_outbox_events_delivery", "outbox_events", ["status", "available_at"])
    if "ix_outbox_events_queue_sequence" not in indexes:
        op.create_index("ix_outbox_events_queue_sequence", "outbox_events", ["queue_id", "sequence_number"])
    if "ix_outbox_events_idempotency" not in indexes:
        op.create_index("ix_outbox_events_idempotency", "outbox_events", ["idempotency_key"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("outbox_events")}
    if "ix_outbox_events_idempotency" in indexes:
        op.drop_index("ix_outbox_events_idempotency", table_name="outbox_events")
    if "ix_outbox_events_queue_sequence" in indexes:
        op.drop_index("ix_outbox_events_queue_sequence", table_name="outbox_events")
    columns = {column["name"] for column in inspector.get_columns("outbox_events")}
    if {"created_at", "idempotency_key", "sequence_number"} & columns:
        with op.batch_alter_table("outbox_events") as batch_op:
            if "created_at" in columns:
                batch_op.drop_column("created_at")
            if "idempotency_key" in columns:
                batch_op.drop_column("idempotency_key")
            if "sequence_number" in columns:
                batch_op.drop_column("sequence_number")
    op.drop_index("ix_outbox_events_delivery", table_name="outbox_events")
    op.drop_table("outbox_events")
