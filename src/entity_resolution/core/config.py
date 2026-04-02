"""Application configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables and .env file.

    All settings can be overridden via environment variables prefixed with ``ERE_``.
    For example, ``ERE_DATABASE_PATH=data/prod.db`` sets ``database_path``.
    """

    database_path: str = "data/companies.db"
    nta_prefecture_code: str = "14"  # Kanagawa
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # Matching config
    trigram_candidate_limit: int = 200
    phonetic_candidate_limit: int = 100
    min_score_threshold: float = 0.3

    # Batch config
    batch_max_queries: int = 100
    batch_worker_count: int = 4

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ERE_")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
