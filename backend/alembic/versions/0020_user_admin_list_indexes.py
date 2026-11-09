"""Index common user-list filters for large account tables."""

import sqlalchemy as sa
from alembic import op

revision = "0020_user_admin_list_indexes"
down_revision = "0019_organization_announcements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    required_columns = {"role", "is_active", "created_at"}
    if not required_columns <= user_columns:
        return
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_role_active_created_at" not in indexes:
        op.create_index(
            "ix_users_role_active_created_at",
            "users",
            ["role", "is_active", "created_at"],
        )
    if "ix_users_active_created_at" not in indexes:
        op.create_index(
            "ix_users_active_created_at",
            "users",
            ["is_active", "created_at"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    for name in (
        "ix_users_active_created_at",
        "ix_users_role_active_created_at",
    ):
        if name in indexes:
            op.drop_index(name, table_name="users")
