"""Tests for application configuration."""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings


class TestSettings:
    """Test Settings class."""

    def test_default_values(self) -> None:
        """Test that defaults are sensible."""
        settings = Settings()
        assert settings.claude_model == "claude-opus-4-5"
        assert settings.claude_api_max_concurrent == 2
        assert settings.response_timeout == 300.0
        assert settings.greeting_timeout == 30.0
        assert settings.session_ttl == 3600.0
        assert settings.cleanup_interval == 300.0
        assert settings.graceful_shutdown_timeout == 5.0
        assert settings.queue_max_size == 10
        assert settings.kg_project_cache_max_size == 100

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env vars override defaults."""
        monkeypatch.setenv("APP_CLAUDE_MODEL", "claude-sonnet-4")
        monkeypatch.setenv("APP_CLAUDE_API_MAX_CONCURRENT", "5")
        monkeypatch.setenv("APP_RESPONSE_TIMEOUT", "600.0")
        monkeypatch.setenv("APP_KG_PROJECT_CACHE_MAX_SIZE", "50")

        # Clear lru_cache
        get_settings.cache_clear()

        settings = get_settings()
        assert settings.claude_model == "claude-sonnet-4"
        assert settings.claude_api_max_concurrent == 5
        assert settings.response_timeout == 600.0
        assert settings.kg_project_cache_max_size == 50

        # Restore cache for other tests
        get_settings.cache_clear()

    def test_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that APP_ prefix is required."""
        # Set without prefix - should not affect Settings
        monkeypatch.setenv("CLAUDE_MODEL", "wrong-model")

        # Clear lru_cache
        get_settings.cache_clear()

        settings = get_settings()
        # Should use default, not the env var without prefix
        assert settings.claude_model == "claude-opus-4-5"

        # Restore
        get_settings.cache_clear()


class TestGetSettings:
    """Test get_settings function."""

    def test_cached_singleton(self) -> None:
        """Test that get_settings returns cached instance."""
        # Clear any existing cache
        get_settings.cache_clear()

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

        # Clean up
        get_settings.cache_clear()

    def test_cache_clear(self) -> None:
        """Test that cache can be cleared."""
        get_settings.cache_clear()

        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()

        # After clearing, we get a new instance
        assert s1 is not s2

        # Clean up
        get_settings.cache_clear()
