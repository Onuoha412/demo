"""Add branch assignments for staff users."""

from alembic import op

revision = "0002_staff_branch_assignment"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS branch_id UUID "
        "REFERENCES branches(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_branch_id ON users (branch_id)")


def downgrade() -> None:
    op.drop_index("ix_users_branch_id", table_name="users")
    op.drop_column("users", "branch_id")
