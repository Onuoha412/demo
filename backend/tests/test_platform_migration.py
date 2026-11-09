import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_platform_migration_preserves_legacy_announcements_and_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'platform-operations.db').as_posix()}"
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    monkeypatch.setattr("app.config.settings.database_url", database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE alembic_version "
                    "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO alembic_version (version_num) "
                    "VALUES ('0017_platform_operations')"
                )
            )
            connection.execute(
                text("CREATE TABLE users (id CHAR(32) PRIMARY KEY)")
            )
            connection.execute(
                text(
                    "CREATE TABLE announcements ("
                    "id CHAR(32) PRIMARY KEY, "
                    "title VARCHAR(160) NOT NULL, "
                    "message TEXT NOT NULL, "
                    "is_published BOOLEAN DEFAULT false NOT NULL, "
                    "created_by_user_id CHAR(32), "
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
                )
            )
            connection.execute(
                text(
                    'CREATE TABLE system_settings ('
                    '"key" VARCHAR(100) PRIMARY KEY, '
                    "value JSON DEFAULT '{}' NOT NULL, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_announcements_published_created "
                    "ON announcements (is_published, created_at)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO announcements "
                    "(id, title, message, is_published) "
                    "VALUES (:id, :title, :message, :is_published)"
                ),
                {
                    "id": "a" * 32,
                    "title": "Existing notice",
                    "message": "Previously published content.",
                    "is_published": True,
                },
            )
            connection.execute(
                text(
                    'INSERT INTO system_settings ("key", value) '
                    "VALUES (:key, :value)"
                ),
                {"key": "maintenance_mode", "value": json.dumps(True)},
            )
            connection.execute(
                text(
                    'INSERT INTO system_settings ("key", value) '
                    "VALUES (:key, :value)"
                ),
                {
                    "key": "maintenance_message",
                    "value": json.dumps("Planned maintenance."),
                },
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            announcement = connection.execute(
                text(
                    "SELECT title, message, audience, is_published, published_at "
                    "FROM announcements"
                )
            ).mappings().one()
            settings = connection.execute(
                text(
                    "SELECT maintenance_mode, maintenance_message "
                    "FROM platform_settings WHERE id = 1"
                )
            ).mappings().one()
        assert announcement["title"] == "Existing notice"
        assert announcement["message"] == "Previously published content."
        assert announcement["audience"] == "all"
        assert bool(announcement["is_published"]) is True
        assert announcement["published_at"] is not None
        assert bool(settings["maintenance_mode"]) is True
        assert settings["maintenance_message"] == "Planned maintenance."
    finally:
        engine.dispose()
