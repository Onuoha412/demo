from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str = "QueueLess API"
    allowed_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://queueless:queueless@localhost:5432/queueless"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    redis_url: str | None = None
    realtime_channel_prefix: str = "queueless:queue:"
    notification_approaching_threshold: int = 3

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        placeholders = {
            "change-me",
            "changeme",
            "secret",
            "replace-with-a-long-random-secret",
            "generate-a-unique-random-secret-at-least-32-bytes",
        }
        if len(value.encode("utf-8")) < 32 or value.strip().lower() in placeholders:
            raise ValueError("JWT_SECRET_KEY must be a unique secret of at least 32 bytes")
        return value

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
