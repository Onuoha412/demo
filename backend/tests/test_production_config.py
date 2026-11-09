import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "allowed_origins": "https://customer.example.com",
        "database_url": "sqlite:////var/data/queueless.db",
        "redis_url": "redis://redis.example.com:6379/0",
        "sentry_dsn": "https://public-key@sentry.example.com/123",
        "secret_key": "s" * 32,
        "jwt_secret_key": "j" * 32,
        "frontend_url": "https://customer.example.com",
        "reset_password_url": "https://customer.example.com/reset-password",
        "email_mode": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_from": "no-reply@example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_accepts_persistent_sqlite() -> None:
    config = production_settings()

    assert config.environment == "production"
    assert config.access_token_expire_minutes == 30
    assert config.database_url == "sqlite:////var/data/queueless.db"


def test_production_configuration_accepts_postgresql() -> None:
    config = production_settings(
        database_url="postgresql://queue:secret@db.example.com/queueless"
    )

    assert config.database_url.startswith("postgresql+psycopg://")


@pytest.mark.parametrize(
    "database_url",
    [
        "mysql+pymysql://queue:secret@db.example.com/app",
        "postgresql+psycopg://db.example.com",
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite+pysqlite:///:memory:",
    ],
)
def test_configuration_rejects_unsupported_or_ephemeral_production_databases(
    database_url: str,
) -> None:
    with pytest.raises(ValidationError):
        production_settings(database_url=database_url)


def test_development_configuration_defaults_to_sqlite() -> None:
    config = Settings(
        _env_file=None,
        database_url="sqlite:///./queueless.db",
        jwt_secret_key="queueless-test-only-secret-not-for-deployment-32-bytes",
    )

    assert Settings.model_fields["database_url"].default == "sqlite:///./queueless.db"
    assert config.database_url == "sqlite:///./queueless.db"
    assert config.allowed_origins.split(",") == [
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    ]
    assert config.sqlite_busy_timeout_ms == 30_000
    assert config.sqlite_synchronous == "NORMAL"
    assert config.database_backup_interval_hours == 24
    assert config.database_backup_retention_count == 7


@pytest.mark.parametrize("mode", ["normal", "FULL", "extra"])
def test_sqlite_synchronous_mode_is_normalized(mode: str) -> None:
    config = Settings(
        _env_file=None,
        database_url="sqlite:///./queueless.db",
        jwt_secret_key="queueless-test-only-secret-not-for-deployment-32-bytes",
        sqlite_synchronous=mode,
    )

    assert config.sqlite_synchronous == mode.upper()


def test_sqlite_synchronous_mode_rejects_unsafe_values() -> None:
    with pytest.raises(ValidationError, match="SQLITE_SYNCHRONOUS"):
        Settings(
            _env_file=None,
            database_url="sqlite:///./queueless.db",
            jwt_secret_key="queueless-test-only-secret-not-for-deployment-32-bytes",
            sqlite_synchronous="OFF",
        )


@pytest.mark.parametrize("timeout", [0, 300_001])
def test_sqlite_busy_timeout_is_bounded(timeout: int) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="sqlite:///./queueless.db",
            jwt_secret_key="queueless-test-only-secret-not-for-deployment-32-bytes",
            sqlite_busy_timeout_ms=timeout,
        )


def test_backup_retention_requires_at_least_one_snapshot() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="sqlite:///./queueless.db",
            jwt_secret_key="queueless-test-only-secret-not-for-deployment-32-bytes",
            database_backup_retention_count=0,
        )


def test_production_configuration_does_not_require_optional_sentry() -> None:
    assert production_settings(sentry_dsn=None).sentry_dsn is None


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("jwt_secret_key", "replace-with-a-different-unique-random-secret-at-least-32-bytes"),
        ("secret_key", "replace-with-a-unique-random-secret-at-least-32-bytes"),
        ("allowed_origins", "https://*"),
        ("database_url", "mysql+pymysql://db.example.com/queueless"),
        ("sentry_dsn", "http://public-key@sentry.example.com/123"),
        ("access_token_expire_minutes", 61),
    ],
)
def test_production_configuration_rejects_unsafe_values(
    setting: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        production_settings(**{setting: value})


def test_production_signing_keys_must_be_distinct() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        production_settings(secret_key="x" * 32, jwt_secret_key="x" * 32)
