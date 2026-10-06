from pathlib import Path


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
}


def test_stage_one_schema_contains_all_core_tables() -> None:
    schema = (Path(__file__).resolve().parents[2] / "database" / "schema.sql").read_text()
    tables = {
        line.split()[2]
        for line in schema.splitlines()
        if line.startswith("CREATE TABLE ")
    }
    assert tables == EXPECTED_TABLES
