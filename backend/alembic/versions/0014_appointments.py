"""Add appointment slots and customer bookings."""

import sqlalchemy as sa

from alembic import op

revision = "0014_appointments"
down_revision = "0013_feedback_improvement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "appointment_slots" not in tables:
        op.create_table(
            "appointment_slots",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("service_id", sa.Uuid(), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("capacity", sa.Integer(), nullable=False),
            sa.Column("booked_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("is_open", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.CheckConstraint(
                "ends_at > starts_at", name="ck_appointment_slots_end_after_start"
            ),
            sa.CheckConstraint(
                "capacity > 0", name="ck_appointment_slots_capacity_positive"
            ),
            sa.CheckConstraint(
                "booked_count >= 0", name="ck_appointment_slots_booked_nonnegative"
            ),
            sa.CheckConstraint(
                "booked_count <= capacity",
                name="ck_appointment_slots_booked_within_capacity",
            ),
            sa.ForeignKeyConstraint(
                ["service_id"], ["services.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "service_id", "starts_at", name="uq_appointment_slots_service_start"
            ),
        )
        op.create_index(
            "ix_appointment_slots_service_start",
            "appointment_slots",
            ["service_id", "starts_at"],
        )

    if "appointments" not in tables:
        op.create_table(
            "appointments",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("slot_id", sa.Uuid(), nullable=False),
            sa.Column("customer_id", sa.Uuid(), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="booked", nullable=False),
            sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True),
                server_default=sa.func.now(), nullable=False,
            ),
            sa.CheckConstraint(
                "status IN ('booked', 'checked_in', 'cancelled', 'completed', 'no_show')",
                name="ck_appointments_status",
            ),
            sa.ForeignKeyConstraint(
                ["customer_id"], ["users.id"], ondelete="RESTRICT"
            ),
            sa.ForeignKeyConstraint(
                ["slot_id"], ["appointment_slots.id"], ondelete="RESTRICT"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_appointments_customer_created",
            "appointments",
            ["customer_id", "created_at"],
        )
        op.create_index(
            "ix_appointments_slot_status", "appointments", ["slot_id", "status"]
        )
        op.create_index(
            "uq_appointments_active_customer_slot",
            "appointments",
            ["slot_id", "customer_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('booked', 'checked_in')"),
            postgresql_where=sa.text("status IN ('booked', 'checked_in')"),
        )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "appointments" in tables:
        op.drop_table("appointments")
    if "appointment_slots" in tables:
        op.drop_table("appointment_slots")
