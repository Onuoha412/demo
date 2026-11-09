from app.db.base import Base
from app.models import Organization


EXPECTED_TABLES = {
    "users",
    "organizations",
    "branches",
    "services",
    "counters",
    "queues",
    "queue_entries",
    "queue_events",
    "notifications",
    "notification_preferences",
    "feedback",
    "sessions",
    "password_reset_tokens",
    "auth_rate_limits",
    "queue_requests",
    "audit_logs",
    "organization_memberships",
    "migration_jobs",
    "migration_mappings",
    "feedback_reports",
    "feedback_replies",
    "feedback_status_history",
    "feedback_votes",
    "feedback_improvement_tasks",
    "feedback_task_links",
    "appointment_slots",
    "appointments",
    "queue_transfers",
    "announcements",
    "platform_settings",
    "scheduled_jobs",
    "scheduled_job_executions",
    "outbox_events",
}

EXPECTED_COLUMNS = {
    "organizations": {"id", "name", "slug", "description", "is_active", "timezone"},
    "branches": {
        "id",
        "organization_id",
        "name",
        "address",
        "timezone",
        "is_active",
    },
    "services": {
        "id",
        "branch_id",
        "name",
        "code",
        "average_service_minutes",
    },
    "counters": {"id", "branch_id", "name", "number", "status"},
    "queues": {
        "id",
        "service_id",
        "prefix",
        "status",
        "current_number",
        "capacity_limit",
        "priority_enabled",
    },
    "queue_entries": {
        "id",
        "queue_id",
        "customer_id",
        "queue_number",
        "status",
        "counter_id",
        "joined_at",
        "called_at",
        "service_started_at",
        "completed_at",
        "estimated_wait_minutes",
        "priority",
    },
    "appointment_slots": {
        "id",
        "service_id",
        "starts_at",
        "ends_at",
        "capacity",
        "booked_count",
        "is_open",
    },
    "appointments": {
        "id",
        "slot_id",
        "customer_id",
        "status",
        "checked_in_at",
    },
    "queue_transfers": {
        "id",
        "source_entry_id",
        "target_entry_id",
        "source_queue_id",
        "target_queue_id",
        "actor_user_id",
    },
    "queue_events": {
        "id",
        "queue_id",
        "queue_entry_id",
        "event_type",
        "metadata",
        "created_at",
    },
    "notifications": {
        "id",
        "user_id",
        "queue_entry_id",
        "type",
        "message",
        "is_read",
    },
    "queue_requests": {
        "id",
        "customer_id",
        "branch_id",
        "request_text",
        "status",
        "assigned_queue_id",
        "queue_entry_id",
        "reviewed_by_user_id",
        "reviewed_at",
        "review_note",
        "created_at",
        "updated_at",
    },
    "migration_jobs": {
        "id",
        "organization_id",
        "requested_by_user_id",
        "source_system",
        "file_sha256",
        "status",
        "total_rows",
        "valid_rows",
        "invalid_rows",
        "created_rows",
        "skipped_rows",
        "rejected_rows",
        "preview_rows",
        "result_rows",
    },
    "migration_mappings": {
        "organization_id",
        "source_system",
        "external_id",
        "target_user_id",
        "migration_job_id",
        "source_hash",
    },
    "feedback_reports": {
        "id",
        "reporter_user_id",
        "reporter_role",
        "organization_id",
        "branch_id",
        "assigned_to_user_id",
        "category",
        "title",
        "description",
        "rating",
        "status",
        "priority",
        "severity",
        "resolution_summary",
        "release_version",
    },
    "feedback_replies": {
        "id",
        "report_id",
        "author_user_id",
        "body",
        "is_internal",
        "created_at",
    },
    "feedback_status_history": {
        "id",
        "report_id",
        "actor_user_id",
        "previous_status",
        "new_status",
        "created_at",
    },
    "feedback_votes": {"report_id", "user_id", "created_at"},
    "feedback_improvement_tasks": {
        "id",
        "title",
        "description",
        "assigned_to_user_id",
        "target_release",
        "release_version",
        "verification_notes",
        "post_release_outcome",
        "status",
    },
    "feedback_task_links": {"report_id", "task_id", "created_at"},
}

EXPECTED_FOREIGN_KEYS = {
    "branches": {("organization_id", "organizations.id")},
    "services": {("branch_id", "branches.id")},
    "counters": {("branch_id", "branches.id")},
    "queues": {("service_id", "services.id")},
    "queue_entries": {
        ("queue_id", "queues.id"),
        ("customer_id", "users.id"),
        ("counter_id", "counters.id"),
    },
    "queue_events": {
        ("queue_id", "queues.id"),
        ("queue_entry_id", "queue_entries.id"),
    },
    "notifications": {
        ("user_id", "users.id"),
        ("queue_entry_id", "queue_entries.id"),
    },
    "queue_requests": {
        ("customer_id", "users.id"),
        ("branch_id", "branches.id"),
        ("assigned_queue_id", "queues.id"),
        ("queue_entry_id", "queue_entries.id"),
        ("reviewed_by_user_id", "users.id"),
    },
    "feedback_reports": {
        ("reporter_user_id", "users.id"),
        ("organization_id", "organizations.id"),
        ("branch_id", "branches.id"),
        ("assigned_to_user_id", "users.id"),
        ("duplicate_of_id", "feedback_reports.id"),
    },
    "feedback_replies": {
        ("report_id", "feedback_reports.id"),
        ("author_user_id", "users.id"),
    },
    "feedback_status_history": {
        ("report_id", "feedback_reports.id"),
        ("actor_user_id", "users.id"),
    },
    "feedback_votes": {
        ("report_id", "feedback_reports.id"),
        ("user_id", "users.id"),
    },
    "feedback_improvement_tasks": {("assigned_to_user_id", "users.id")},
    "feedback_task_links": {
        ("report_id", "feedback_reports.id"),
        ("task_id", "feedback_improvement_tasks.id"),
    },
    "appointment_slots": {("service_id", "services.id")},
    "appointments": {
        ("slot_id", "appointment_slots.id"),
        ("customer_id", "users.id"),
    },
    "queue_transfers": {
        ("source_entry_id", "queue_entries.id"),
        ("target_entry_id", "queue_entries.id"),
        ("source_queue_id", "queues.id"),
        ("target_queue_id", "queues.id"),
        ("actor_user_id", "users.id"),
    },
    "announcements": {
        ("created_by_user_id", "users.id"),
        ("organization_id", "organizations.id"),
    },
    "platform_settings": {("updated_by_user_id", "users.id")},
    "scheduled_jobs": {
        ("organization_id", "organizations.id"),
        ("created_by_user_id", "users.id"),
    },
    "scheduled_job_executions": {("job_id", "scheduled_jobs.id")},
    "outbox_events": {("queue_id", "queues.id")},
}


def test_metadata_contains_all_core_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_orm_models_match_queue_diagram_columns_and_relationships() -> None:
    assert Organization.__table__ is Base.metadata.tables["organizations"]

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        table = Base.metadata.tables[table_name]
        assert expected_columns <= set(table.columns.keys())

    for table_name, expected_foreign_keys in EXPECTED_FOREIGN_KEYS.items():
        table = Base.metadata.tables[table_name]
        foreign_keys = {
            (foreign_key.parent.name, foreign_key.target_fullname)
            for foreign_key in table.foreign_keys
        }
        assert expected_foreign_keys <= foreign_keys


def test_orm_models_include_database_numeric_checks() -> None:
    services = Base.metadata.tables["services"]
    queues = Base.metadata.tables["queues"]

    assert any(
        str(constraint.sqltext) == "average_service_minutes > 0"
        for constraint in services.constraints
        if hasattr(constraint, "sqltext")
    )
    assert any(
        str(constraint.sqltext) == "current_number >= 0"
        for constraint in queues.constraints
        if hasattr(constraint, "sqltext")
    )
