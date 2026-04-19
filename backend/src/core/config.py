"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute the project root as an absolute path. This file lives at
# backend/src/core/config.py, so the project root is three parents up.
# Using an absolute path means `.env` loads correctly regardless of
# where Python is invoked from (project root, backend/, tests, CI, etc.).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Typed application settings.

    Values are loaded from environment variables, falling back to the `.env`
    file in the project root if present. Never commit `.env` — only `.env.example`.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://datum:datum_dev_password@localhost:5432/datum",
        description="SQLAlchemy connection string for the app database.",
    )

    # LLM
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key. Required for semantic layer proposal.",
    )

    # Environment
    environment: str = Field(default="development")
    log_level: str = Field(default="info")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Using lru_cache ensures we only parse environment variables once per process.
    """
    return Settings()
