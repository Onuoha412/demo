"""Create the initial platform announcements and key/value settings tables."""

import sqlalchemy as sa
from alembic import op

revision = "0017_platform_operations"
down_revision = "0016_queue_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "announcements" not in inspector.get_table_names():
        op.create_table(
            "announcements",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "is_published",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
            sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_announcements_published_created",
            "announcements",
            ["is_published", "created_at"],
        )
    if "system_settings" not in inspector.get_table_names():
        op.create_table(
            "system_settings",
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column(
                "value",
                sa.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "announcements" in inspector.get_table_names():
        indexes = {
            index["name"] for index in inspector.get_indexes("announcements")
        }
        if "ix_announcements_published_created" in indexes:
            op.drop_index(
                "ix_announcements_published_created", table_name="announcements"
            )
        op.drop_table("announcements")
    if "system_settings" in inspector.get_table_names():
        op.drop_table("system_settings")