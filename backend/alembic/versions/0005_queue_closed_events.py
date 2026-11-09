"""Queue event enums are stored as strings in SQLite."""

revision = "0005_queue_closed_events"
down_revision = "0004_queue_position_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite stores SQLAlchemy's non-native enum values as strings. The current
    # model metadata creates those columns without PostgreSQL-only CHECK DDL.
    pass


def downgrade() -> None:
    pass
