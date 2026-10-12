import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="queueless-tests-")
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"sqlite:///{Path(_TEST_DIRECTORY.name) / 'queueless-tests.db'}",
)
if not TEST_DATABASE_URL.startswith("sqlite:"):
    raise RuntimeError("Tests require a SQLite TEST_DATABASE_URL")
os.environ.setdefault("JWT_SECRET_KEY", "queueless-test-only-secret-not-for-deployment-32-bytes")
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
        connect_args={"check_same_thread": False, "timeout": 60},
        pool_pre_ping=True,
    )
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("PRAGMA journal_mode=WAL"))
        connection.execute(text("SELECT 1"))
    alembic_config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_config, "head")
    yield engine
    command.downgrade(alembic_config, "base")
    engine.dispose()


def pytest_unconfigure() -> None:
    _TEST_DIRECTORY.cleanup()


@pytest.fixture
def db_session(database_engine: Engine) -> Generator[Session, None, None]:
    session = sessionmaker(bind=database_engine, expire_on_commit=False)()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
