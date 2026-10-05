from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QueueLess API"
    allowed_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://queueless:queueless@localhost:5432/queueless"
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
