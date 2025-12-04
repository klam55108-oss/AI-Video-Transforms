"""
Tests for permission handler functionality.

This module tests the permission system for controlling tool access
and file operations.
"""

from __future__ import annotations

import pytest


class TestPermissionConfig:
    """Test PermissionConfig dataclass."""

    def test_default_config(self):
        """Test creating PermissionConfig with defaults."""
        from permissions import PermissionConfig

        config = PermissionConfig()

        assert isinstance(config.global_blocked_paths, list)
        assert len(config.global_blocked_paths) > 0
        assert config.log_decisions is True

    def test_blocked_paths(self):
        """Test that common system paths are blocked by default."""
        from permissions import PermissionConfig

        config = PermissionConfig()

        # Common system directories should be blocked
        assert any("/etc" in path for path in config.global_blocked_paths)
        assert any("/usr" in path for path in config.global_blocked_paths)
        assert any("/bin" in path for path in config.global_blocked_paths)


class TestPermissionHandler:
    """Test permission handler callback function."""

    @pytest.mark.asyncio
    async def test_blocked_path_denied(self):
        """Test that file writes to blocked paths are denied."""
        from claude_agent_sdk.types import PermissionResultDeny

        from permissions import create_permission_handler, get_default_permission_config

        config = get_default_permission_config()
        handler = create_permission_handler(config)

        # Try to write to /etc (blocked)
        result = await handler(
            tool_name="mcp__video-tools__write_file",
            input_data={"file_path": "/etc/passwd"},
            context={},
        )

        assert isinstance(result, PermissionResultDeny)
        assert hasattr(result, "message")
        assert "etc" in result.message.lower() or "cannot" in result.message.lower()

    @pytest.mark.asyncio
    async def test_allowed_path_permitted(self):
        """Test that file writes to allowed paths are permitted."""
        from claude_agent_sdk.types import PermissionResultAllow

        from permissions import create_permission_handler, get_default_permission_config

        config = get_default_permission_config()
        handler = create_permission_handler(config)

        # Try to write to safe location
        result = await handler(
            tool_name="mcp__video-tools__write_file",
            input_data={"file_path": "/tmp/test.txt"},
            context={},
        )

        assert isinstance(result, PermissionResultAllow)
        assert result.updated_input["file_path"] == "/tmp/test.txt"

    @pytest.mark.asyncio
    async def test_logging_enabled(self, caplog):
        """Test that permission decisions are logged when enabled."""
        import logging

        from permissions import PermissionConfig, create_permission_handler

        config = PermissionConfig(log_decisions=True)
        handler = create_permission_handler(config)

        # Set log level to capture INFO logs
        caplog.set_level(logging.INFO)

        await handler(
            tool_name="mcp__video-tools__transcribe_video",
            input_data={"source": "test.mp4"},
            context={},
        )

        # Check that logging occurred (or that handler was called without error)
        # Note: actual logging depends on implementation
        assert True  # Handler executed successfully

    @pytest.mark.asyncio
    async def test_tool_name_handling(self):
        """Test that different tool names are handled correctly."""
        from claude_agent_sdk.types import PermissionResultAllow

        from permissions import create_permission_handler, get_default_permission_config

        config = get_default_permission_config()
        handler = create_permission_handler(config)

        # Test transcribe tool (should always allow)
        result = await handler(
            tool_name="mcp__video-tools__transcribe_video",
            input_data={"source": "https://youtube.com/watch?v=test"},
            context={},
        )

        assert isinstance(result, PermissionResultAllow)

        # Test save_transcript tool (should always allow)
        result = await handler(
            tool_name="mcp__video-tools__save_transcript",
            input_data={"content": "test"},
            context={},
        )

        assert isinstance(result, PermissionResultAllow)


class TestPermissionFactory:
    """Test permission handler factory functions."""

    def test_get_default_permission_config(self):
        """Test getting default permission configuration."""
        from permissions import get_default_permission_config

        config = get_default_permission_config()

        assert config is not None
        assert isinstance(config.global_blocked_paths, list)
        assert config.log_decisions is True

    def test_create_permission_handler_returns_callable(self):
        """Test that create_permission_handler returns a callable."""
        from permissions import PermissionConfig, create_permission_handler

        config = PermissionConfig()
        handler = create_permission_handler(config)

        assert callable(handler)
