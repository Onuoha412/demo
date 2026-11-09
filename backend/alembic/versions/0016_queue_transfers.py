"""Record customer queue transfers."""

import sqlalchemy as sa

from alembic import op

revision = "0016_queue_transfers"
down_revision = "0015_queue_capacity_priority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "queue_transfers" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "queue_transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_entry_id", sa.Uuid(), nullable=False),
        sa.Column("target_entry_id", sa.Uuid(), nullable=False),
        sa.Column("source_queue_id", sa.Uuid(), nullable=False),
        sa.Column("target_queue_id", sa.Uuid(), nullable=False),
        sa.Column("source_queue_number", sa.Integer(), nullable=False),
        sa.Column("target_queue_number", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_entry_id"], ["queue_entries.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_entry_id"], ["queue_entries.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_queue_id"], ["queues.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_queue_id"], ["queues.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_entry_id", name="uq_queue_transfers_target_entry"),
    )
    op.create_index(
        "ix_queue_transfers_source_created",
        "queue_transfers",
        ["source_queue_id", "created_at"],
    )
    op.create_index(
        "ix_queue_transfers_target_created",
        "queue_transfers",
        ["target_queue_id", "created_at"],
    )


def downgrade() -> None:
    if "queue_transfers" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("queue_transfers")
