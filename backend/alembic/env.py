from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db.base import Base
from app import models  # noqa: F401

config = context.config
database_url = settings.database_url
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if (
    config.config_file_name is not None
    and config.get_section("loggers") is not None
):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connect_args = (
        {"check_same_thread": False, "timeout": 30}
        if settings.database_url.startswith(("sqlite://", "sqlite+pysqlite://"))
        else {}
    )
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            # SQLite batch migrations rebuild tables that may be referenced by foreign keys.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
