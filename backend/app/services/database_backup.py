from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

from sqlalchemy.engine import make_url

_BACKUP_PREFIX = "queueless-"
_BACKUP_SUFFIX = ".sqlite3"
_REQUIRED_TABLES = {"alembic_version", "users", "organizations", "queues", "queue_entries"}


def _database_path(database_url: str) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        raise ValueError("Backup and restore require a file-backed SQLite database.")
    if url.database == ":memory:":
        raise ValueError("Backup and restore do not support in-memory databases.")
    return Path(url.database).expanduser().resolve()


def _validate_database(path: Path) -> None:
    if not path.is_file():
        raise ValueError("The SQLite database file does not exist.")
    uri = f"{path.as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise ValueError("SQLite integrity_check failed.")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing = _REQUIRED_TABLES - tables
            if missing:
                raise ValueError(
                    "The file is not a QueueLess database or is missing required tables."
                )
    except sqlite3.DatabaseError as error:
        raise ValueError("The file is not a readable SQLite database.") from error


def _sync_file(path: Path) -> None:
    with path.open("rb") as file:
        os.fsync(file.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def create_database_backup(database_url: str, backup_directory: str | Path) -> Path:
    source_path = _database_path(database_url)
    if not source_path.is_file():
        raise ValueError("The configured SQLite database file does not exist.")
    destination_directory = Path(backup_directory).expanduser().resolve()
    destination_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{_BACKUP_PREFIX}{timestamp}-{uuid4().hex[:8]}{_BACKUP_SUFFIX}"
    destination_path = destination_directory / name
    temporary_path = destination_directory / f".{name}.{uuid4().hex}.tmp"
    try:
        try:
            source_uri = f"{source_path.as_uri()}?mode=ro"
            with sqlite3.connect(source_uri, uri=True) as source:
                with sqlite3.connect(temporary_path) as destination:
                    source.backup(destination)
                    result = destination.execute("PRAGMA integrity_check").fetchone()
                    if result is None or result[0] != "ok":
                        raise ValueError("The backup failed SQLite integrity_check.")
        except sqlite3.DatabaseError as error:
            raise ValueError("The configured SQLite database could not be backed up.") from error
        _validate_database(temporary_path)
        os.chmod(temporary_path, 0o600)
        _sync_file(temporary_path)
        os.replace(temporary_path, destination_path)
        _sync_file(destination_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination_path


def list_database_backups(
    backup_directory: str | Path, *, limit: int = 20
) -> list[dict[str, str | int]]:
    if not 1 <= limit <= 100:
        raise ValueError("Backup listing limit must be between 1 and 100.")
    directory = Path(backup_directory).expanduser().resolve()
    if not directory.exists():
        return []
    files = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.name.startswith(_BACKUP_PREFIX)
            and path.name.endswith(_BACKUP_SUFFIX)
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "created_at": datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).isoformat(),
        }
        for path in files[:limit]
    ]


def prune_database_backups(
    backup_directory: str | Path, *, keep: int
) -> list[Path]:
    if not 1 <= keep <= 365:
        raise ValueError("Backup retention count must be between 1 and 365.")
    directory = Path(backup_directory).expanduser().resolve()
    if not directory.exists():
        return []
    candidates = sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.name.startswith(_BACKUP_PREFIX)
            and path.name.endswith(_BACKUP_SUFFIX)
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    valid_backups: list[Path] = []
    for path in candidates:
        try:
            _validate_database(path)
        except ValueError:
            continue
        valid_backups.append(path)

    removed: list[Path] = []
    for path in valid_backups[keep:]:
        path.unlink()
        removed.append(path)
    return removed


def restore_database(
    backup_path: str | Path,
    database_url: str,
    backup_directory: str | Path,
    *,
    confirm_offline: bool,
) -> tuple[Path, Path]:
    if not confirm_offline:
        raise ValueError(
            "Restore requires --confirm-offline after stopping all QueueLess API processes."
        )
    destination_path = _database_path(database_url)
    source_path = Path(backup_path).expanduser().resolve()
    if not source_path.is_file() or source_path == destination_path:
        raise ValueError("Choose an existing backup file different from the live database.")
    _validate_database(source_path)
    if not destination_path.is_file():
        raise ValueError(
            "The destination database must exist; initialize it with Alembic before restore."
        )

    safety_backup = create_database_backup(database_url, backup_directory)
    temporary_path = destination_path.parent / (
        f".{destination_path.name}.{uuid4().hex}.restore"
    )
    try:
        shutil.copyfile(source_path, temporary_path)
        _validate_database(temporary_path)
        os.chmod(temporary_path, 0o600)
        _sync_file(temporary_path)

        try:
            with sqlite3.connect(destination_path) as live_database:
                checkpoint = live_database.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
        except sqlite3.DatabaseError as error:
            raise ValueError("The live database could not be checkpointed.") from error
        if checkpoint is not None and checkpoint[0] != 0:
            raise ValueError(
                "SQLite WAL checkpoint is busy. Confirm the application is offline and retry."
            )
        Path(f"{destination_path}-wal").unlink(missing_ok=True)
        Path(f"{destination_path}-shm").unlink(missing_ok=True)
        os.replace(temporary_path, destination_path)
        _sync_file(destination_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination_path, safety_backup
