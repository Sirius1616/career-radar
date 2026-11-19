"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "career-radar"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str | None = None
    anthropic_api_key: str | None = None
    auth_jwt_secret: str | None = None
    ai_cheap_model: str = "claude-3-5-haiku-latest"
    ai_capable_model: str = "claude-sonnet-4-5"
    ai_daily_budget_micro: int | None = None  # micro-USD (1e-6)
    ai_monthly_budget_micro: int | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
