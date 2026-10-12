import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "allowed_origins": "https://customer.example.com",
        "database_url": "sqlite:////var/lib/queueless/queueless.db",
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


def test_production_configuration_accepts_persistent_sqlite_without_redis() -> None:
    config = production_settings()

    assert config.environment == "production"
    assert config.access_token_expire_minutes == 30


def test_production_configuration_does_not_require_optional_sentry() -> None:
    config = production_settings(sentry_dsn=None)

    assert config.sentry_dsn is None


def test_development_configuration_allows_vite_and_preview_origins() -> None:
    config = Settings(
        _env_file=None,
        jwt_secret_key="queueless-test-only-secret-not-for-deployment-32-bytes",
    )

    assert config.allowed_origins.split(",") == [
        "http://localhost:5173",
        "http://localhost:4173",
    ]


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("jwt_secret_key", "replace-with-a-different-unique-random-secret-at-least-32-bytes"),
        ("secret_key", "replace-with-a-unique-random-secret-at-least-32-bytes"),
        ("allowed_origins", "https://*"),
        ("database_url", "postgresql://db.example.com/queueless"),
        ("database_url", "sqlite:///:memory:"),
        ("database_url", "sqlite:///relative.db"),
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
