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
}

EXPECTED_COLUMNS = {
    "organizations": {"id", "name", "slug", "description", "is_active"},
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
}


def test_sqlite_metadata_contains_all_core_tables() -> None:
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
