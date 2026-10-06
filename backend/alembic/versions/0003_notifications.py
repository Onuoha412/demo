"""Add notification idempotency and preferences."""

from alembic import op

revision = "0003_notifications"
down_revision = "0002_staff_branch_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS event_key VARCHAR(160)")
    op.execute(
        "UPDATE notifications SET event_key = id::text WHERE event_key IS NULL"
    )
    op.execute("ALTER TABLE notifications ALTER COLUMN event_key SET NOT NULL")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_user_event_key "
        "ON notifications (user_id, event_key)"
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
    op.execute(
        """CREATE TABLE IF NOT EXISTS notification_preferences (
        user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        joined BOOLEAN NOT NULL DEFAULT TRUE,
        called BOOLEAN NOT NULL DEFAULT TRUE,
        approaching BOOLEAN NOT NULL DEFAULT TRUE,
        completed BOOLEAN NOT NULL DEFAULT TRUE,
        queue_updates BOOLEAN NOT NULL DEFAULT TRUE
        )"""
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_type_check"
    )
    op.execute(
        """UPDATE notifications SET type = CASE type
        WHEN 'queue_joined' THEN 'queue_update'
        WHEN 'queue_approaching' THEN 'turn_approaching'
        WHEN 'customer_called' THEN 'turn_called'
        WHEN 'service_completed' THEN 'system'
        WHEN 'queue_paused' THEN 'queue_update'
        WHEN 'queue_resumed' THEN 'queue_update'
        ELSE type END"""
    )
    op.execute(
        """ALTER TABLE notifications ADD CONSTRAINT notifications_type_check CHECK (
        type IN ('queue_update', 'turn_approaching', 'turn_called', 'system')
        )"""
    )
    op.drop_table("notification_preferences")
    op.drop_index("uq_notifications_user_event_key", table_name="notifications")
    op.drop_column("notifications", "event_key")
