from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings


database_url = make_url(settings.database_url)
if database_url.get_backend_name() == "sqlite":
    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
            "timeout": settings.sqlite_busy_timeout_ms / 1000,
        },
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite_connection(connection, _connection_record) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA synchronous={settings.sqlite_synchronous}")
        finally:
            cursor.close()
else:
    engine = create_engine(
        database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def configure_postgresql_connection(connection, _connection_record) -> None:
        cursor = connection.cursor()
        cursor.execute("SET TIME ZONE 'UTC'")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
