"""Remove Google authentication storage.

Revision ID: 0025_remove_google_auth
Revises: 0024_durable_job_leases
"""

from alembic import op
import sqlalchemy as sa

revision = "0025_remove_google_auth"
down_revision = "0024_durable_job_leases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "google_id" in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("google_id")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("google_id", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint("uq_users_google_id", ["google_id"])
