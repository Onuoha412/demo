"""Add persistent authentication sessions and password reset state."""

import sqlalchemy as sa

from alembic import op

revision = "0006_secure_authentication"
down_revision = "0005_queue_closed_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_user_columns = {column["name"] for column in inspector.get_columns("users")}
    user_columns = (
        sa.Column("google_id", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column(
            "auth_provider",
            sa.String(20),
            server_default="local",
            nullable=False,
        ),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    missing_columns = [
        column for column in user_columns if column.name not in existing_user_columns
    ]
    user_constraints = inspector.get_unique_constraints("users")
    if missing_columns or not any(
        constraint.get("column_names") == ["google_id"]
        for constraint in user_constraints
    ):
        with op.batch_alter_table(
            "users",
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
        ) as batch_op:
            for column in missing_columns:
                batch_op.add_column(column)
            if not any(
                constraint.get("column_names") == ["google_id"]
                for constraint in user_constraints
            ):
                batch_op.create_unique_constraint("uq_users_google_id", ["google_id"])

    if not inspector.has_table("sessions"):
        op.create_table(
            "sessions",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("session_token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
        )
    if not any(
        index["name"] == "ix_sessions_user_expires"
        for index in sa.inspect(op.get_bind()).get_indexes("sessions")
    ):
        op.create_index("ix_sessions_user_expires", "sessions", ["user_id", "expires_at"])

    if not sa.inspect(op.get_bind()).has_table("password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    reset_indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("password_reset_tokens")
    }
    if "ix_password_reset_tokens_user" not in reset_indexes:
        op.create_index(
            "ix_password_reset_tokens_user", "password_reset_tokens", ["user_id"]
        )
    if "ix_password_reset_tokens_expires" not in reset_indexes:
        op.create_index(
            "ix_password_reset_tokens_expires",
            "password_reset_tokens",
            ["expires_at"],
        )

    if not sa.inspect(op.get_bind()).has_table("auth_rate_limits"):
        op.create_table(
            "auth_rate_limits",
            sa.Column("bucket_key", sa.String(128), primary_key=True),
            sa.Column("count", sa.Integer(), nullable=False),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        )
    op.get_bind().execute(sa.text("UPDATE users SET email = lower(email)"))
    if not any(
        index.get("name") == "uq_users_email_case_insensitive"
        for index in sa.inspect(op.get_bind()).get_indexes("users")
    ):
        op.create_index(
            "uq_users_email_case_insensitive",
            "users",
            ["email"],
            unique=True,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("users") and any(
        index.get("name") == "uq_users_email_case_insensitive"
        for index in inspector.get_indexes("users")
    ):
        op.drop_index("uq_users_email_case_insensitive", table_name="users")
    if inspector.has_table("auth_rate_limits"):
        op.drop_table("auth_rate_limits")
    if inspector.has_table("password_reset_tokens"):
        indexes = {item["name"] for item in inspector.get_indexes("password_reset_tokens")}
        for name in (
            "ix_password_reset_tokens_expires",
            "ix_password_reset_tokens_user",
        ):
            if name in indexes:
                op.drop_index(name, table_name="password_reset_tokens")
        op.drop_table("password_reset_tokens")
    if inspector.has_table("sessions"):
        indexes = {item["name"] for item in inspector.get_indexes("sessions")}
        if "ix_sessions_user_expires" in indexes:
            op.drop_index("ix_sessions_user_expires", table_name="sessions")
        op.drop_table("sessions")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    google_id_constraints = [
        constraint
        for constraint in inspector.get_unique_constraints("users")
        if constraint.get("column_names") == ["google_id"]
    ]
    with op.batch_alter_table(
        "users",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch_op:
        for constraint in google_id_constraints:
            if constraint.get("name"):
                batch_op.drop_constraint(constraint["name"], type_="unique")
        for name in (
            "last_login_at",
            "email_verified",
            "auth_provider",
            "avatar_url",
            "google_id",
        ):
            if name in user_columns:
                batch_op.drop_column(name)
