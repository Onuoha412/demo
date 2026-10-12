"""Store customer request notes and admin verification on queue entries."""

import sqlalchemy as sa

from alembic import op

revision = "0007_queue_entry_requests"
down_revision = "0006_secure_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("queue_entries")
    }
    if "request_note" not in existing_columns:
        op.add_column("queue_entries", sa.Column("request_note", sa.Text(), nullable=True))
    if "verified_at" not in existing_columns:
        op.add_column(
            "queue_entries",
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "verified_by_user_id" not in existing_columns:
        op.add_column(
            "queue_entries",
            sa.Column(
                "verified_by_user_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    existing_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("queue_entries")
    }
    columns_to_drop = [
        name
        for name in ("verified_by_user_id", "verified_at", "request_note")
        if name in existing_columns
    ]
    if columns_to_drop:
        with op.batch_alter_table("queue_entries") as batch_op:
            for name in columns_to_drop:
                batch_op.drop_column(name)
