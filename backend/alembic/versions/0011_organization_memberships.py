"""Add organization-scoped staff and administrator memberships."""

import sqlalchemy as sa

from alembic import op

revision = "0011_organization_memberships"
down_revision = "0010_super_admin_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "organization_memberships" not in inspector.get_table_names():
        op.create_table(
            "organization_memberships",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default=sa.true(),
                nullable=False,
            ),
            sa.Column("assigned_by_user_id", sa.Uuid(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "role IN ('staff', 'admin')",
                name="ck_organization_memberships_role",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("user_id", "organization_id"),
        )

    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("organization_memberships")
    }
    if "ix_organization_memberships_org_role_active" not in indexes:
        op.create_index(
            "ix_organization_memberships_org_role_active",
            "organization_memberships",
            ["organization_id", "role", "is_active"],
        )

    op.execute(
        sa.text(
            """
            INSERT INTO organization_memberships
                (user_id, organization_id, role, is_active, created_at)
            SELECT id, organization_id, role, is_active, created_at
            FROM users
            WHERE organization_id IS NOT NULL
              AND role IN ('staff', 'admin')
            ON CONFLICT (user_id, organization_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "organization_memberships" in inspector.get_table_names():
        op.drop_table("organization_memberships")
