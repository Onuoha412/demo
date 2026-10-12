"""Initialize and verify the configured SQLite database through Alembic."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from alembic import command

from ..config import settings
from .session import engine


def main() -> None:
    if not settings.database_url.startswith("sqlite:"):
        raise RuntimeError("QueueLess database initialization requires SQLite")
    backend_directory = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(backend_directory / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        connection.execute(text("SELECT 1"))


if __name__ == "__main__":
    main()
