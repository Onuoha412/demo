"""Add organization and account approval state."""

import sqlalchemy as sa

from alembic import op

revision = "0008_organization_approval"
down_revision = "0007_queue_entry_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    organization_columns = {
        column["name"] for column in inspector.get_columns("organizations")
    }
    if "is_approved" not in organization_columns:
        op.add_column(
            "organizations",
            sa.Column(
                "is_approved",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            ),
        )

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "approval_pending" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "approval_pending",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "approval_pending" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("approval_pending")

    organization_columns = {
        column["name"] for column in inspector.get_columns("organizations")
    }
    if "is_approved" in organization_columns:
        with op.batch_alter_table("organizations") as batch_op:
            batch_op.drop_column("is_approved")
