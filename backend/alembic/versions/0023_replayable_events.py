"""Add replay cursors and idempotency metadata to the transactional outbox."""

import sqlalchemy as sa
from alembic import op

revision = "0023_replayable_events"
down_revision = "0022_transactional_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("outbox_events")}
    with op.batch_alter_table("outbox_events") as batch_op:
        if "sequence_number" not in columns:
            batch_op.add_column(sa.Column("sequence_number", sa.Integer(), nullable=True))
        if "idempotency_key" not in columns:
            batch_op.add_column(sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        if "created_at" not in columns:
            batch_op.add_column(
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=True,
                )
            )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("outbox_events")}
    if "ix_outbox_events_queue_sequence" in indexes:
        op.drop_index("ix_outbox_events_queue_sequence", table_name="outbox_events")
    op.create_index(
        "ix_outbox_events_queue_sequence",
        "outbox_events",
        ["queue_id", "sequence_number"],
    )
    if "ix_outbox_events_idempotency" not in indexes:
        op.create_index(
            "ix_outbox_events_idempotency",
            "outbox_events",
            ["idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_idempotency", table_name="outbox_events")
    op.drop_index("ix_outbox_events_queue_sequence", table_name="outbox_events")
    with op.batch_alter_table("outbox_events") as batch_op:
        batch_op.drop_column("created_at")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("sequence_number")
