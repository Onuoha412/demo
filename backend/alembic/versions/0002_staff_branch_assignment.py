"""Add branch assignments for staff users."""

from alembic import op
import sqlalchemy as sa

revision = "0002_staff_branch_assignment"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "branch_id" not in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("branch_id", sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(
                "fk_users_branch_id_branches",
                "branches",
                ["branch_id"],
                ["id"],
                ondelete="SET NULL",
            )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("users")}
    if "ix_users_branch_id" not in indexes:
        op.create_index("ix_users_branch_id", "users", ["branch_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_branch_id" in indexes:
        op.drop_index("ix_users_branch_id", table_name="users")
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "branch_id" in columns:
        with op.batch_alter_table("users") as batch_op:
            for foreign_key in inspector.get_foreign_keys("users"):
                if foreign_key.get("constrained_columns") == ["branch_id"] and foreign_key.get("name"):
                    batch_op.drop_constraint(foreign_key["name"], type_="foreignkey")
            batch_op.drop_column("branch_id")
