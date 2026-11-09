import pytest

from app.config import settings
from app.db.migrate_sqlite_to_postgresql import migrate_sqlite_to_postgresql


def test_sqlite_migration_requires_explicit_source_offline_confirmation(
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="every QueueLess process"):
        migrate_sqlite_to_postgresql(
            tmp_path / "queueless.db",
            confirm_source_offline=False,
        )


def test_sqlite_migration_rejects_non_postgresql_destination(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "queueless.db"
    source.touch()
    monkeypatch.setattr(settings, "database_url", "sqlite:///./queueless.db")

    with pytest.raises(ValueError, match="PostgreSQL destination"):
        migrate_sqlite_to_postgresql(source, confirm_source_offline=True)
