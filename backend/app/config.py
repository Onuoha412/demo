from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import make_url

_SECRET_PLACEHOLDER_PREFIXES = (
    "change-me",
    "changeme",
    "replace-with",
    "generate-a",
    "secret",
    "your-",
)


class Settings(BaseSettings):
    app_name: str = "QueueLess API"
    environment: str = "development"
    allowed_origins: str = Field(
        default=(
            "http://localhost:5173,http://localhost:4173,"
            "http://127.0.0.1:5173,http://127.0.0.1:4173"
        ),
        validation_alias=AliasChoices("allowed_origins", "CORS_ORIGINS", "ALLOWED_ORIGINS"),
    )
    database_url: str = "sqlite:///./queueless.db"
    database_pool_size: int = Field(default=10, gt=0)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout: int = Field(default=30, gt=0)
    database_pool_recycle: int = Field(default=1800, gt=0)
    sqlite_busy_timeout_ms: int = Field(default=30_000, gt=0, le=300_000)
    sqlite_synchronous: str = "NORMAL"
    database_backup_dir: str = Field(
        default="./backups",
        validation_alias=AliasChoices("database_backup_dir", "DATABASE_BACKUP_DIR"),
    )
    database_backup_interval_hours: int = Field(default=24, ge=0, le=8760)
    database_backup_retention_count: int = Field(default=7, ge=1, le=365)
    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("redis_url", "REDIS_URL"),
    )
    realtime_pubsub_channel: str = "queueless:realtime"
    jwt_secret_key: str = Field(
        validation_alias=AliasChoices("jwt_secret_key", "JWT_SECRET", "JWT_SECRET_KEY")
    )
    secret_key: str | None = Field(
        default=None, validation_alias=AliasChoices("secret_key", "SECRET_KEY")
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    session_expire_days: int = Field(default=14, gt=0, le=90)
    session_cookie_name: str = "queueless_session"
    session_cookie_samesite: str = "lax"
    frontend_url: str = "http://localhost:5173"
    super_admin_email: str | None = None
    email_mode: str = "console"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, gt=0, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    reset_password_url: str = "http://localhost:5173/reset-password"
    auth_rate_limit_login: int = Field(default=10, gt=0)
    auth_rate_limit_register: int = Field(default=5, gt=0)
    auth_rate_limit_reset: int = Field(default=5, gt=0)
    realtime_channel_prefix: str = "queueless:queue:"
    realtime_queue_connection_limit: int = Field(default=1000, gt=0, le=10_000)
    notification_approaching_threshold: int = 3
    scheduled_job_poll_interval_seconds: float = Field(default=0.5, gt=0, le=60)
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.05, ge=0, le=1)

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        normalized = value.strip()
        try:
            parsed = make_url(normalized)
        except ArgumentError as error:
            raise ValueError("DATABASE_URL must be a valid SQLAlchemy URL") from error
        if parsed.drivername in {"sqlite", "sqlite+pysqlite"}:
            if parsed.database is None:
                raise ValueError("DATABASE_URL must include a SQLite database path")
        elif parsed.drivername in {"postgresql", "postgresql+psycopg"}:
            if not parsed.host or not parsed.database:
                raise ValueError(
                    "PostgreSQL DATABASE_URL must include a host and database name"
                )
            if parsed.drivername == "postgresql":
                normalized = parsed.set(drivername="postgresql+psycopg").render_as_string(
                    hide_password=False
                )
        else:
            raise ValueError("DATABASE_URL must use SQLite or PostgreSQL")
        return normalized

    @field_validator("sqlite_synchronous")
    @classmethod
    def validate_sqlite_synchronous(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"NORMAL", "FULL", "EXTRA"}:
            raise ValueError("SQLITE_SYNCHRONOUS must be NORMAL, FULL, or EXTRA")
        return normalized

    @field_validator("email_mode")
    @classmethod
    def validate_email_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"console", "smtp"}:
            raise ValueError("EMAIL_MODE must be console or smtp")
        return normalized

    @field_validator("session_cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("SESSION_COOKIE_SAMESITE must be lax, strict, or none")
        return normalized

    @field_validator(
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "smtp_from",
    )
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()

    @field_validator("super_admin_email")
    @classmethod
    def normalize_super_admin_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().lower()
        if (
            len(normalized) > 320
            or normalized.count("@") != 1
            or "." not in normalized.rsplit("@", maxsplit=1)[1]
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("SUPER_ADMIN_EMAIL must be a valid email address")
        return normalized

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32 or cls._is_placeholder_secret(value):
            raise ValueError("JWT_SECRET_KEY must be a unique secret of at least 32 bytes")
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value.encode("utf-8")) < 32 or cls._is_placeholder_secret(value)
        ):
            raise ValueError("SECRET_KEY must be a unique secret of at least 32 bytes")
        return value

    @field_validator("sentry_dsn")
    @classmethod
    def validate_sentry_dsn(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            return None
        if value is not None:
            parsed = urlparse(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is None
                or parsed.password is not None
                or not parsed.path.strip("/")
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("SENTRY_DSN must be a valid HTTPS ingest DSN")
        return value

    @staticmethod
    def _is_placeholder_secret(value: str) -> bool:
        normalized = value.strip().lower()
        return any(
            normalized == prefix or normalized.startswith(prefix)
            for prefix in _SECRET_PLACEHOLDER_PREFIXES
        )

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.email_mode == "smtp" and not all(
            (self.smtp_host, self.smtp_from)
        ):
            raise ValueError("SMTP_HOST and SMTP_FROM are required when EMAIL_MODE=smtp")
        if self.environment != "production":
            return self
        if not self.redis_url:
            raise ValueError("REDIS_URL is required in production for shared realtime state")
        origins = [origin.strip() for origin in self.allowed_origins.split(",")]
        if not origins or any(not self._is_secure_origin(origin) for origin in origins):
            raise ValueError("CORS_ORIGINS must contain only known HTTPS origins in production")
        if self.access_token_expire_minutes > 60:
            raise ValueError("Access tokens must expire within 60 minutes in production")
        if self.secret_key is None:
            raise ValueError("SECRET_KEY is required in production")
        if self.secret_key.strip() == self.jwt_secret_key.strip():
            raise ValueError("SECRET_KEY and JWT_SECRET must be different values")
        if not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE is required in production")
        if self.email_mode != "smtp":
            raise ValueError("EMAIL_MODE=smtp is required in production")
        for name, value in (
            ("FRONTEND_URL", self.frontend_url),
            ("RESET_PASSWORD_URL", self.reset_password_url),
        ):
            parsed_url = urlparse(value)
            if (
                parsed_url.scheme != "https"
                or not parsed_url.hostname
                or parsed_url.username
                or parsed_url.password
            ):
                raise ValueError(f"{name} must be an HTTPS URL in production")
        frontend = urlparse(self.frontend_url)
        if f"{frontend.scheme}://{frontend.netloc}" not in origins:
            raise ValueError("FRONTEND_URL origin must be included in CORS_ORIGINS")
        database = make_url(self.database_url).database
        if database in {None, "", ":memory:"}:
            raise ValueError("Production DATABASE_URL must use a persistent database")
        return self

    @property
    def session_cookie_secure(self) -> bool:
        return self.environment == "production"

    @staticmethod
    def _is_secure_origin(origin: str) -> bool:
        parsed = urlparse(origin)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and "*" not in origin
            and parsed.path == ""
            and parsed.params == ""
            and parsed.query == ""
            and parsed.fragment == ""
            and parsed.username is None
            and parsed.password is None
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )


settings = Settings()
