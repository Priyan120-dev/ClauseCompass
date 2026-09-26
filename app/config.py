"""Application configuration module."""
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ClauseCompass Application Settings."""

    app_name: str = "ClauseCompass"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # API key is read solely from environment variable or .env
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    # If demo_mode is True or gemini_api_key is empty, FakeLLMClient is used
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")

    # Ingestion & Security limits
    max_file_size_mb: int = Field(default=5, alias="MAX_FILE_SIZE_MB")
    max_pages: int = Field(default=60, alias="MAX_PAGES")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    cache_size_items: int = Field(default=100, alias="CACHE_SIZE_ITEMS")

    # Networking: respects $HOST and $PORT dynamically
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=int(os.environ.get("PORT", "8000")), alias="PORT")
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_demo_mode(self) -> bool:
        """Return True if demo mode is enabled or if no Gemini API key is provided."""
        return self.demo_mode or not self.gemini_api_key.strip()


settings = Settings()
