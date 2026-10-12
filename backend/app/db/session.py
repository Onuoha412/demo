from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings


def _prepare_sqlite_database(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme == "sqlite" and parsed.path and parsed.path != "/:memory:":
        Path(parsed.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


if not settings.database_url.startswith("sqlite:"):
    raise RuntimeError("QueueLess supports SQLite as its only application database")

_prepare_sqlite_database(settings.database_url)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False, "timeout": 60},
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
)


@event.listens_for(engine, "connect")
def configure_sqlite_connection(connection, _) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=60000")
    cursor.close()


with engine.connect() as connection:
    connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    connection.exec_driver_sql("PRAGMA synchronous=NORMAL")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def begin_write(session: Session) -> None:
    """Acquire SQLite's writer lock before queue state is read and modified."""
    if session.get_bind().dialect.name != "sqlite":
        return
    connection = session.connection()
    driver_connection = connection.connection.driver_connection
    if not driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
