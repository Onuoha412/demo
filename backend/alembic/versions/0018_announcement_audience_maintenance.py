"""Add announcement targeting and persisted maintenance controls."""

import json

import sqlalchemy as sa
from alembic import op

revision = "0018_announcement_audience_maintenance"
down_revision = "0017_platform_operations"
branch_labels = None
depends_on = None

DEFAULT_MAINTENANCE_MESSAGE = (
    "QueueLess is temporarily unavailable for scheduled maintenance."
)


def _decode_json_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "announcements" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("announcements")}
        if "audience" not in columns:
            op.add_column(
                "announcements",
                sa.Column(
                    "audience",
                    sa.String(length=20),
                    nullable=False,
                    server_default="all",
                ),
            )
        if "published_at" not in columns:
            op.add_column(
                "announcements",
                sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            )
            bind.execute(
                sa.text(
                    "UPDATE announcements SET published_at = created_at "
                    "WHERE is_published = true"
                )
            )
        if "expires_at" not in columns:
            op.add_column(
                "announcements",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )
        index_names = {index["name"] for index in inspector.get_indexes("announcements")}
        if "ix_announcements_published_expires" not in index_names:
            op.create_index(
                "ix_announcements_published_expires",
                "announcements",
                ["published_at", "expires_at"],
            )

    inspector = sa.inspect(bind)
    if "platform_settings" not in inspector.get_table_names():
        op.create_table(
            "platform_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "maintenance_mode",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
            sa.Column(
                "maintenance_message",
                sa.String(length=500),
                server_default=DEFAULT_MAINTENANCE_MESSAGE,
                nullable=False,
            ),
            sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.CheckConstraint("id = 1", name="ck_platform_settings_singleton"),
            sa.ForeignKeyConstraint(
                ["updated_by_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    if (
        "system_settings" in inspector.get_table_names()
        and bind.scalar(sa.text("SELECT COUNT(*) FROM platform_settings")) == 0
    ):
        values = {
            row["key"]: _decode_json_value(row["value"])
            for row in bind.execute(
                sa.text('SELECT "key", value FROM system_settings')
            ).mappings()
        }
        maintenance = values.get("maintenance")
        if not isinstance(maintenance, dict):
            maintenance = {}
        maintenance_mode = _as_bool(
            values.get(
                "maintenance_mode",
                values.get("maintenance_enabled", maintenance.get("enabled", False)),
            )
        )
        message = values.get(
            "maintenance_message",
            maintenance.get("message", DEFAULT_MAINTENANCE_MESSAGE),
        )
        if not isinstance(message, str) or not message.strip():
            message = DEFAULT_MAINTENANCE_MESSAGE
        bind.execute(
            sa.text(
                "INSERT INTO platform_settings "
                "(id, maintenance_mode, maintenance_message) "
                "VALUES (1, :maintenance_mode, :maintenance_message)"
            ),
            {
                "maintenance_mode": maintenance_mode,
                "maintenance_message": message[:500],
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "platform_settings" in tables:
        op.drop_table("platform_settings")
    if "announcements" not in tables:
        return
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("announcements")}
    indexes = {index["name"] for index in inspector.get_indexes("announcements")}
    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("announcements")
    }
    if "ix_announcements_published_expires" in indexes:
        op.drop_index(
            "ix_announcements_published_expires", table_name="announcements"
        )
    with op.batch_alter_table("announcements") as batch:
        if "ck_announcements_audience" in constraints:
            batch.drop_constraint("ck_announcements_audience", type_="check")
        for column in ("expires_at", "published_at", "audience"):
            if column in columns:
                batch.drop_column(column)
