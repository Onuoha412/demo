"""Index queue entries for queue position counts."""

import sqlalchemy as sa

from alembic import op

revision = "0004_queue_position_index"
down_revision = "0003_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("queue_entries")
    }
    if "ix_queue_entries_position" not in indexes:
        op.create_index(
            "ix_queue_entries_position",
            "queue_entries",
            ["queue_id", "status", "queue_number"],
        )


def downgrade() -> None:
    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("queue_entries")
    }
    if "ix_queue_entries_position" in indexes:
        op.drop_index("ix_queue_entries_position", table_name="queue_entries")
