"""Scope organization announcements to their own staff and admins."""

import sqlalchemy as sa
from alembic import op

revision = "0019_organization_announcements"
down_revision = "0018_announcement_audience_maintenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "announcements" not in inspector.get_table_names():
        return
    organizations_exist = "organizations" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("announcements")}
    foreign_keys = inspector.get_foreign_keys("announcements")
    if "organization_id" not in columns:
        with op.batch_alter_table("announcements") as batch_op:
            batch_op.add_column(sa.Column("organization_id", sa.Uuid(), nullable=True))
            if organizations_exist:
                batch_op.create_foreign_key(
                    "fk_announcements_organization_id_organizations",
                    "organizations",
                    ["organization_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
    elif organizations_exist and not any(
        foreign_key["constrained_columns"] == ["organization_id"]
        and foreign_key["referred_table"] == "organizations"
        for foreign_key in foreign_keys
    ):
        with op.batch_alter_table("announcements") as batch_op:
            batch_op.create_foreign_key(
                "fk_announcements_organization_id_organizations",
                "organizations",
                ["organization_id"],
                ["id"],
                ondelete="CASCADE",
            )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("announcements")}
    if "ix_announcements_org_audience_published" not in indexes:
        op.create_index(
            "ix_announcements_org_audience_published",
            "announcements",
            ["organization_id", "audience", "published_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "announcements" not in sa.inspect(bind).get_table_names():
        return
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("announcements")}
    indexes = {index["name"] for index in inspector.get_indexes("announcements")}
    if "ix_announcements_org_audience_published" in indexes:
        op.drop_index(
            "ix_announcements_org_audience_published",
            table_name="announcements",
        )
    if "organization_id" in columns:
        with op.batch_alter_table("announcements") as batch_op:
            for foreign_key in inspector.get_foreign_keys("announcements"):
                if foreign_key["constrained_columns"] == ["organization_id"]:
                    if foreign_key["name"] is not None:
                        batch_op.drop_constraint(foreign_key["name"], type_="foreignkey")
            batch_op.drop_column("organization_id")
