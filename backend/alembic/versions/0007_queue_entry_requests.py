"""Store customer request notes and admin verification on queue entries."""

import sqlalchemy as sa

from alembic import op

revision = "0007_queue_entry_requests"
down_revision = "0006_secure_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {
        column["name"] for column in inspector.get_columns("queue_entries")
    }
    has_verifier_foreign_key = any(
        foreign_key.get("constrained_columns") == ["verified_by_user_id"]
        and foreign_key.get("referred_table") == "users"
        for foreign_key in inspector.get_foreign_keys("queue_entries")
    )
    missing_columns = {
        "request_note": sa.Column("request_note", sa.Text(), nullable=True),
        "verified_at": sa.Column(
            "verified_at", sa.DateTime(timezone=True), nullable=True
        ),
        "verified_by_user_id": sa.Column(
            "verified_by_user_id", sa.Uuid(as_uuid=True), nullable=True
        ),
    }
    if (
        any(name not in existing_columns for name in missing_columns)
        or not has_verifier_foreign_key
    ):
        with op.batch_alter_table("queue_entries") as batch_op:
            for name, column in missing_columns.items():
                if name not in existing_columns:
                    batch_op.add_column(column)
            if not has_verifier_foreign_key:
                batch_op.create_foreign_key(
                    "fk_queue_entries_verified_by_user_id_users",
                    "users",
                    ["verified_by_user_id"],
                    ["id"],
                    ondelete="SET NULL",
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
