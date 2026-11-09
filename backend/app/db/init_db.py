"""Initialize and verify the configured database through Alembic."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from alembic import command

from ..config import settings
from .session import engine


def main() -> None:
    backend_directory = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(backend_directory / "alembic.ini"))
    alembic_config.set_main_option(
        "sqlalchemy.url", settings.database_url.replace("%", "%%")
    )
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


if __name__ == "__main__":
    main()
