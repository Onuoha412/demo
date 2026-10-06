"""Create QueueLess database foundation."""

from pathlib import Path

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[3] / "database" / "schema.sql"
    op.execute(schema_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS feedback, notifications, queue_events, "
        "queue_entries, queues, counters, services, branches, users, "
        "organizations CASCADE"
    )
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
