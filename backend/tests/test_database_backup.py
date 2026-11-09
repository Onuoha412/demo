import sqlite3

import pytest

from app.services.database_backup import (
    create_database_backup,
    list_database_backups,
    prune_database_backups,
    restore_database,
)


def make_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version VALUES ('0016_queue_transfers');
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE organizations (id INTEGER PRIMARY KEY);
            CREATE TABLE queues (id INTEGER PRIMARY KEY);
            CREATE TABLE queue_entries (id INTEGER PRIMARY KEY, message TEXT);
            INSERT INTO queue_entries (id, message) VALUES (1, 'original');
            """
        )


def test_backup_is_integrity_checked_private_and_captures_wal_data(tmp_path) -> None:
    database_path = tmp_path / "queueless.sqlite3"
    backup_dir = tmp_path / "snapshots"
    make_database(database_path)

    backup = create_database_backup(
        f"sqlite:///{database_path}", backup_dir
    )

    assert backup.exists()
    assert backup.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute(
            "SELECT message FROM queue_entries WHERE id=1"
        ).fetchone()[0] == "original"
    assert list_database_backups(backup_dir)[0]["filename"] == backup.name


def test_backup_retention_keeps_the_newest_valid_snapshot(tmp_path) -> None:
    database_path = tmp_path / "queueless.sqlite3"
    backup_dir = tmp_path / "snapshots"
    make_database(database_path)
    database_url = f"sqlite:///{database_path}"

    older = create_database_backup(database_url, backup_dir)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE queue_entries SET message='newer state' WHERE id=1"
        )
        connection.commit()
    newer = create_database_backup(database_url, backup_dir)

    removed = prune_database_backups(backup_dir, keep=1)

    assert removed == [older]
    assert newer.exists()
    assert len(list_database_backups(backup_dir)) == 1


def test_backup_retention_does_not_remove_the_only_valid_snapshot(tmp_path) -> None:
    database_path = tmp_path / "queueless.sqlite3"
    backup_dir = tmp_path / "snapshots"
    make_database(database_path)
    only_backup = create_database_backup(f"sqlite:///{database_path}", backup_dir)

    assert prune_database_backups(backup_dir, keep=1) == []
    assert only_backup.exists()


def test_restore_requires_offline_confirmation_and_creates_safety_snapshot(
    tmp_path,
) -> None:
    database_path = tmp_path / "queueless.sqlite3"
    backup_dir = tmp_path / "snapshots"
    make_database(database_path)
    database_url = f"sqlite:///{database_path}"
    backup = create_database_backup(database_url, backup_dir)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE queue_entries SET message='newer live state' WHERE id=1"
        )
        connection.commit()

    with pytest.raises(ValueError, match="--confirm-offline"):
        restore_database(
            backup,
            database_url,
            backup_dir,
            confirm_offline=False,
        )

    restored_path, safety_backup = restore_database(
        backup,
        database_url,
        backup_dir,
        confirm_offline=True,
    )
    assert restored_path == database_path
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT message FROM queue_entries WHERE id=1"
        ).fetchone()[0] == "original"
    with sqlite3.connect(safety_backup) as connection:
        assert connection.execute(
            "SELECT message FROM queue_entries WHERE id=1"
        ).fetchone()[0] == "newer live state"
    assert len(list_database_backups(backup_dir)) == 2


def test_restore_rejects_invalid_backup_without_changing_live_database(tmp_path) -> None:
    database_path = tmp_path / "queueless.sqlite3"
    backup_dir = tmp_path / "snapshots"
    make_database(database_path)
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_text("not a database")

    with pytest.raises(ValueError, match="SQLite"):
        restore_database(
            corrupt,
            f"sqlite:///{database_path}",
            backup_dir,
            confirm_offline=True,
        )

    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT message FROM queue_entries WHERE id=1"
        ).fetchone()[0] == "original"
