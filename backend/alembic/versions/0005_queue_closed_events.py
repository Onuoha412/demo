"""Record queue closure events and notify waiting customers."""

from alembic import op

revision = "0005_queue_closed_events"
down_revision = "0004_queue_position_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.execute(
        "ALTER TABLE queue_events DROP CONSTRAINT IF EXISTS queue_events_event_type_check"
    )
    op.execute(
        """ALTER TABLE queue_events ADD CONSTRAINT queue_events_event_type_check CHECK (
        event_type IN (
          'created', 'joined', 'called', 'serving', 'completed', 'skipped',
          'cancelled', 'paused', 'resumed', 'closed'
        ))"""
    )
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_type_check"
    )
    op.execute(
        """ALTER TABLE notifications ADD CONSTRAINT notifications_type_check CHECK (
        type IN (
          'queue_update', 'turn_approaching', 'turn_called', 'system',
          'queue_joined', 'queue_approaching', 'customer_called',
          'service_completed', 'queue_paused', 'queue_resumed', 'queue_closed'
        ))"""
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.execute(
        "UPDATE queue_events SET event_type = 'paused' WHERE event_type = 'closed'"
    )
    op.execute(
        "ALTER TABLE queue_events DROP CONSTRAINT IF EXISTS queue_events_event_type_check"
    )
    op.execute(
        """ALTER TABLE queue_events ADD CONSTRAINT queue_events_event_type_check CHECK (
        event_type IN (
          'created', 'joined', 'called', 'serving', 'completed', 'skipped',
          'cancelled', 'paused', 'resumed'
        ))"""
    )
    op.execute(
        "UPDATE notifications SET type = 'queue_paused' WHERE type = 'queue_closed'"
    )
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_type_check"
    )
    op.execute(
        """ALTER TABLE notifications ADD CONSTRAINT notifications_type_check CHECK (
        type IN (
          'queue_update', 'turn_approaching', 'turn_called', 'system',
          'queue_joined', 'queue_approaching', 'customer_called',
          'service_completed', 'queue_paused', 'queue_resumed'
        ))"""
    )
