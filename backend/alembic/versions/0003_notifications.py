"""Add notification idempotency and preferences."""

import sqlalchemy as sa
from alembic import op

revision = "0003_notifications"
down_revision = "0002_staff_branch_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("notifications")}
    if "event_key" not in columns:
        with op.batch_alter_table("notifications") as batch_op:
            batch_op.add_column(sa.Column("event_key", sa.String(160), nullable=True))
        bind.execute(
            sa.text(
                "UPDATE notifications SET event_key = CAST(id AS VARCHAR) "
                "WHERE event_key IS NULL"
            )
        )
        with op.batch_alter_table("notifications") as batch_op:
            batch_op.alter_column("event_key", existing_type=sa.String(160), nullable=False)

    indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("notifications")
    }
    unique_constraints = {
        constraint["name"]
        for constraint in sa.inspect(bind).get_unique_constraints("notifications")
    }
    if (
        "uq_notifications_user_event_key" not in indexes
        and "uq_notifications_user_event_key" not in unique_constraints
    ):
        op.create_index(
            "uq_notifications_user_event_key",
            "notifications",
            ["user_id", "event_key"],
            unique=True,
        )

    if not sa.inspect(bind).has_table("notification_preferences"):
        op.create_table(
            "notification_preferences",
            sa.Column(
                "user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("joined", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("called", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column(
                "approaching", sa.Boolean(), server_default=sa.true(), nullable=False
            ),
            sa.Column(
                "completed", sa.Boolean(), server_default=sa.true(), nullable=False
            ),
            sa.Column(
                "queue_updates", sa.Boolean(), server_default=sa.true(), nullable=False
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("notification_preferences"):
        op.drop_table("notification_preferences")
    if inspector.has_table("notifications"):
        indexes = {
            index["name"] for index in inspector.get_indexes("notifications")
        }
        if "uq_notifications_user_event_key" in indexes:
            op.drop_index(
                "uq_notifications_user_event_key", table_name="notifications"
            )
        columns = {
            column["name"] for column in inspector.get_columns("notifications")
        }
        if "event_key" in columns:
            with op.batch_alter_table("notifications") as batch_op:
                batch_op.drop_column("event_key")
