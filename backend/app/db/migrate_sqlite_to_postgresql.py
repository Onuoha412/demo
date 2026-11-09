"""Copy a quiesced, current SQLite database into an empty PostgreSQL database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, func, insert, inspect, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from .base import Base


def migrate_sqlite_to_postgresql(
    source_path: Path,
    *,
    confirm_source_offline: bool,
    batch_size: int = 1000,
) -> dict[str, int]:
    if not confirm_source_offline:
        raise ValueError(
            "Confirm that every QueueLess process using the SQLite database is stopped."
        )
    if batch_size < 1:
        raise ValueError("Batch size must be a positive integer.")
    if not source_path.is_file():
        raise ValueError(f"SQLite source database does not exist: {source_path}")

    target_url = make_url(settings.database_url)
    if target_url.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must point to the PostgreSQL destination.")

    backend_directory = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(backend_directory / "alembic.ini"))
    alembic_config.set_main_option(
        "sqlalchemy.url", settings.database_url.replace("%", "%%")
    )
    expected_revision = ScriptDirectory.from_config(alembic_config).get_current_head()
    if expected_revision is None:
        raise RuntimeError("No Alembic migration head is configured.")

    source_url = URL.create(
        "sqlite+pysqlite",
        database=str(source_path.resolve()),
    )
    source_engine = create_engine(source_url)
    target_engine = create_engine(
        target_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
    )
    try:
        source_tables = set(inspect(source_engine).get_table_names())
        expected_source_tables = set(Base.metadata.tables) | {
            "alembic_version",
            "system_settings",
        }
        extra_source_tables = source_tables - expected_source_tables
        missing_source_tables = expected_source_tables - source_tables
        if extra_source_tables or missing_source_tables:
            raise ValueError(
                "SQLite source schema does not match the current QueueLess schema "
                f"(missing={sorted(missing_source_tables)}, "
                f"unexpected={sorted(extra_source_tables)})."
            )

        with source_engine.connect() as source:
            integrity = source.exec_driver_sql("PRAGMA integrity_check").scalar_one()
            if integrity != "ok":
                raise ValueError(f"SQLite integrity check failed: {integrity}")
            source_revision = source.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
            if source_revision != expected_revision:
                raise ValueError(
                    "Apply all QueueLess SQLite migrations before copying data "
                    f"(found {source_revision}, expected {expected_revision})."
                )

        existing_tables = set(inspect(target_engine).get_table_names())
        if not existing_tables:
            command.upgrade(alembic_config, "head")
            existing_tables = set(inspect(target_engine).get_table_names())

        expected_target_tables = expected_source_tables
        if existing_tables != expected_target_tables:
            raise ValueError(
                "PostgreSQL destination must be a fresh QueueLess schema "
                f"(missing={sorted(expected_target_tables - existing_tables)}, "
                f"unexpected={sorted(existing_tables - expected_target_tables)})."
            )
        with target_engine.connect() as target:
            target_revision = target.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one()
            if target_revision != expected_revision:
                raise ValueError(
                    "PostgreSQL destination must be migrated to the current "
                    f"revision {expected_revision}."
                )
            for table in Base.metadata.sorted_tables:
                if target.execute(select(table).limit(1)).first() is not None:
                    raise ValueError(
                        f"PostgreSQL destination table {table.name!r} is not empty."
                    )
            target_system_settings = Table(
                "system_settings",
                MetaData(),
                autoload_with=target,
            )
            if target.execute(select(target_system_settings).limit(1)).first() is not None:
                raise ValueError("PostgreSQL destination table 'system_settings' is not empty.")

        row_counts: dict[str, int] = {}
        with source_engine.connect() as source, target_engine.begin() as target:
            target.exec_driver_sql("SET TIME ZONE 'UTC'")
            source_system_settings = Table(
                "system_settings",
                MetaData(),
                autoload_with=source,
            )
            tables = [*Base.metadata.sorted_tables, source_system_settings]
            for table in tables:
                result = source.execution_options(stream_results=True).execute(
                    select(table)
                )
                copied = 0
                while batch := result.mappings().fetchmany(batch_size):
                    target.execute(insert(table), [dict(row) for row in batch])
                    copied += len(batch)
                source_count = source.scalar(
                    select(func.count()).select_from(table)
                )
                if copied != source_count:
                    raise RuntimeError(
                        f"Row count changed while copying {table.name!r}: "
                        f"read {copied}, expected {source_count}."
                    )
                row_counts[table.name] = copied

        with target_engine.connect() as target:
            target_metadata = MetaData()
            tables = [
                *Base.metadata.sorted_tables,
                Table("system_settings", target_metadata, autoload_with=target),
            ]
            for table in tables:
                target_count = target.scalar(select(func.count()).select_from(table))
                if target_count != row_counts[table.name]:
                    raise RuntimeError(
                        f"Post-copy verification failed for {table.name!r}: "
                        f"found {target_count}, expected {row_counts[table.name]}."
                    )
    except SQLAlchemyError as error:
        raise RuntimeError(
            "SQLite-to-PostgreSQL migration failed; destination data was rolled back."
        ) from error
    finally:
        source_engine.dispose()
        target_engine.dispose()

    return row_counts
