"""Add persistent feedback workflow, replies, votes, and improvement tasks."""

import sqlalchemy as sa

from alembic import op

revision = "0013_feedback_improvement"
down_revision = "0012_csv_migration_jobs"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "feedback_reports" not in tables:
        op.create_table(
            "feedback_reports",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("reporter_user_id", sa.Uuid(), nullable=True),
            sa.Column("reporter_role", sa.String(length=20), nullable=True),
            sa.Column("organization_id", sa.Uuid(), nullable=True),
            sa.Column("branch_id", sa.Uuid(), nullable=True),
            sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
            sa.Column("duplicate_of_id", sa.Uuid(), nullable=True),
            sa.Column("idempotency_key", sa.String(length=64), nullable=True),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("improvement_suggestion", sa.Text(), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("is_anonymous", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("page_identifier", sa.String(length=160), nullable=True),
            sa.Column("app_version", sa.String(length=40), nullable=True),
            sa.Column("status", sa.String(length=32), server_default="new", nullable=False),
            sa.Column("priority", sa.Integer(), server_default="3", nullable=False),
            sa.Column("severity", sa.String(length=16), server_default="low", nullable=False),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolution_summary", sa.Text(), nullable=True),
            sa.Column("release_version", sa.String(length=40), nullable=True),
            sa.Column("resolution_helpful", sa.Boolean(), nullable=True),
            sa.Column("resolution_confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "category IN ('general', 'bug', 'feature_request', 'ui_accessibility', "
                "'queue_accuracy', 'performance_connection', 'security_privacy', "
                "'account_login', 'staff_service', 'organization_setup_migration', "
                "'notification', 'other')",
                name="ck_feedback_reports_category",
            ),
            sa.CheckConstraint(
                "status IN ('new', 'under_review', 'planned', 'in_progress', "
                "'waiting_for_information', 'resolved', 'declined', 'duplicate')",
                name="ck_feedback_reports_status",
            ),
            sa.CheckConstraint("priority BETWEEN 1 AND 5", name="ck_feedback_reports_priority"),
            sa.CheckConstraint(
                "severity IN ('low', 'medium', 'high', 'critical')",
                name="ck_feedback_reports_severity",
            ),
            sa.CheckConstraint(
                "rating IS NULL OR rating BETWEEN 1 AND 5",
                name="ck_feedback_reports_rating",
            ),
            sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["duplicate_of_id"], ["feedback_reports.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key", name="uq_feedback_reports_idempotency_key"),
        )
        tables.add("feedback_reports")

    if "feedback_replies" not in tables:
        op.create_table(
            "feedback_replies",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("report_id", sa.Uuid(), nullable=False),
            sa.Column("author_user_id", sa.Uuid(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_internal", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["report_id"], ["feedback_reports.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("feedback_replies")

    if "feedback_status_history" not in tables:
        op.create_table(
            "feedback_status_history",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("report_id", sa.Uuid(), nullable=False),
            sa.Column("actor_user_id", sa.Uuid(), nullable=True),
            sa.Column("previous_status", sa.String(length=32), nullable=True),
            sa.Column("new_status", sa.String(length=32), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["report_id"], ["feedback_reports.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("feedback_status_history")

    if "feedback_votes" not in tables:
        op.create_table(
            "feedback_votes",
            sa.Column("report_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["report_id"], ["feedback_reports.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("report_id", "user_id"),
            sa.UniqueConstraint("report_id", "user_id", name="uq_feedback_votes_report_user"),
        )
        tables.add("feedback_votes")

    if "feedback_improvement_tasks" not in tables:
        op.create_table(
            "feedback_improvement_tasks",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("acceptance_criteria", sa.Text(), nullable=True),
            sa.Column("priority", sa.Integer(), server_default="3", nullable=False),
            sa.Column("impact", sa.String(length=20), server_default="medium", nullable=False),
            sa.Column("affected_features", sa.String(length=500), nullable=True),
            sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
            sa.Column("target_release", sa.String(length=40), nullable=True),
            sa.Column("release_version", sa.String(length=40), nullable=True),
            sa.Column("verification_notes", sa.Text(), nullable=True),
            sa.Column("post_release_outcome", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), server_default="reviewed", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "status IN ('reviewed', 'prioritized', 'assigned', 'implemented', "
                "'tested', 'released', 'measured', 'declined')",
                name="ck_feedback_improvement_tasks_status",
            ),
            sa.CheckConstraint(
                "priority BETWEEN 1 AND 5",
                name="ck_feedback_improvement_tasks_priority",
            ),
            sa.CheckConstraint(
                "impact IN ('low', 'medium', 'high', 'critical')",
                name="ck_feedback_improvement_tasks_impact",
            ),
            sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("feedback_improvement_tasks")

    if "feedback_task_links" not in tables:
        op.create_table(
            "feedback_task_links",
            sa.Column("report_id", sa.Uuid(), nullable=False),
            sa.Column("task_id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["report_id"], ["feedback_reports.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["task_id"], ["feedback_improvement_tasks.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("report_id", "task_id"),
        )

    indexes = {
        table: {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
        for table in (
            "feedback_reports",
            "feedback_replies",
            "feedback_status_history",
            "feedback_improvement_tasks",
        )
    }
    for name, table, columns in (
        ("ix_feedback_reports_org_status_created", "feedback_reports", ["organization_id", "status", "created_at"]),
        ("ix_feedback_reports_category_created", "feedback_reports", ["category", "created_at"]),
        ("ix_feedback_reports_reporter_created", "feedback_reports", ["reporter_user_id", "created_at"]),
        ("ix_feedback_replies_report_created", "feedback_replies", ["report_id", "created_at"]),
        ("ix_feedback_status_history_report_created", "feedback_status_history", ["report_id", "created_at"]),
        ("ix_feedback_improvement_tasks_status", "feedback_improvement_tasks", ["status"]),
    ):
        if name not in indexes[table]:
            op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table in (
        ("ix_feedback_improvement_tasks_status", "feedback_improvement_tasks"),
        ("ix_feedback_status_history_report_created", "feedback_status_history"),
        ("ix_feedback_replies_report_created", "feedback_replies"),
        ("ix_feedback_reports_reporter_created", "feedback_reports"),
        ("ix_feedback_reports_category_created", "feedback_reports"),
        ("ix_feedback_reports_org_status_created", "feedback_reports"),
    ):
        op.drop_index(name, table_name=table)
    for table in (
        "feedback_task_links",
        "feedback_improvement_tasks",
        "feedback_votes",
        "feedback_status_history",
        "feedback_replies",
        "feedback_reports",
    ):
        op.drop_table(table)
