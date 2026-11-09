"""Add audit logs for security-sensitive super-admin actions."""

import sqlalchemy as sa

from alembic import op

revision = "0010_super_admin_audit_logs"
down_revision = "0009_freeform_queue_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "audit_logs" not in inspector.get_table_names():
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("actor_user_id", sa.Uuid(), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("target_type", sa.String(length=80), nullable=False),
            sa.Column("target_id", sa.String(length=80), nullable=True),
            sa.Column(
                "details",
                sa.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["actor_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_audit_logs_created_at", "audit_logs", ["created_at"]
        )
        op.create_index(
            "ix_audit_logs_actor_created",
            "audit_logs",
            ["actor_user_id", "created_at"],
        )

    existing_indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("users")
    }
    if "uq_users_single_super_admin" not in existing_indexes:
        op.create_index(
            "uq_users_single_super_admin",
            "users",
            ["role"],
            unique=True,
            sqlite_where=sa.text("role = 'super_admin'"),
            postgresql_where=sa.text("role = 'super_admin'"),
        )


def downgrade() -> None:
    op.drop_index("uq_users_single_super_admin", table_name="users")
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")