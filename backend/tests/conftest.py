import os
from collections.abc import Generator
from pathlib import Path
from tempfile import gettempdir

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_PATH = Path(gettempdir()) / f"queueless-test-{os.getpid()}.db"
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
)
if make_url(TEST_DATABASE_URL).get_backend_name() != "sqlite":
    raise RuntimeError("QueueLess tests require SQLite")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "JWT_SECRET_KEY", "queueless-test-only-secret-not-for-deployment-32-bytes"
)
os.environ.setdefault("SECRET_KEY", "queueless-test-only-other-secret-32-bytes")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def clear_fastapi_dependency_overrides():
    yield
    from app.main import app

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def database_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("PRAGMA journal_mode=WAL"))
        connection.execute(text("SELECT 1"))
    alembic_config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    alembic_config.set_main_option(
        "sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%")
    )
    command.upgrade(alembic_config, "head")
    yield engine
    command.downgrade(alembic_config, "base")
    engine.dispose()
    if "TEST_DATABASE_URL" not in os.environ:
        TEST_DATABASE_PATH.unlink(missing_ok=True)


@pytest.fixture
def db_session(database_engine: Engine) -> Generator[Session, None, None]:
    session = sessionmaker(bind=database_engine, expire_on_commit=False)()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
