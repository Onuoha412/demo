"""Index queue entries for queue position counts."""

from alembic import op

revision = "0004_queue_position_index"
down_revision = "0003_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.create_index(
        "ix_queue_entries_position",
        "queue_entries",
        ["queue_id", "status", "queue_number"],
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.drop_index("ix_queue_entries_position", table_name="queue_entries")
