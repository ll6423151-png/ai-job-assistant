from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+psycopg://jobai:jobai_dev_password@postgres:5432/jobai"
    redis_url: str = "redis://redis:6379/0"
    backend_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ai_provider: str = "local"
    openai_api_key: str = ""
    openai_text_model: str = "gpt-4.1-mini"
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"
    local_transcription_model: str = "base"
    resume_upload_max_mb: int = 8
    audio_upload_max_mb: int = 12
    browser_proxy_url: str = "http://127.0.0.1:3456"
    browser_proxy_timeout_seconds: int = 20
    application_automation_daily_limit: int = Field(default=20, ge=1, le=200)
    application_automation_cooldown_seconds: int = Field(default=60, ge=0, le=3600)
    auth_secret_key: str = "change-this-development-auth-secret"
    auth_cookie_name: str = "careerpilot_session"
    auth_session_days: int = Field(default=30, ge=1, le=90)
    auth_idle_minutes: int = Field(default=120, ge=15, le=1440)
    auth_cookie_secure: bool = False
    bootstrap_admin_enabled: bool = True
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_authorization_code: str = ""
    smtp_sender_name: str = "CareerPilot AI"
    smtp_use_ssl: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def async_database_url(self) -> str:
        """Normalize common Neon and local URLs for SQLAlchemy Async."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    @property
    def migration_database_url(self) -> str:
        """Return a synchronous URL for Alembic while using the same database."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
