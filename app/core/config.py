"""Centralized application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    # Data storage path
    data_path: Path = Path("data")

    # Claude model configuration
    claude_model: str = "claude-opus-4-5"
    claude_api_max_concurrent: int = 2

    # Timeout configuration (seconds)
    response_timeout: float = 300.0
    greeting_timeout: float = 30.0
    session_ttl: float = 3600.0
    cleanup_interval: float = 300.0
    graceful_shutdown_timeout: float = 5.0

    # Queue/cache configuration
    queue_max_size: int = 10
    kg_project_cache_max_size: int = 100

    # Frontend polling intervals (milliseconds)
    kg_poll_interval_ms: int = 5000
    status_poll_interval_ms: int = 3000

    # Job queue configuration
    job_max_concurrent: int = 2
    job_poll_interval_ms: int = 1000

    # Export configuration
    export_ttl_hours: int = 24  # Auto-cleanup exports older than this
    batch_export_max_projects: int = 50  # Max projects in single batch export


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings()
