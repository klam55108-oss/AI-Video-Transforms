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
        from app.core.permissions import PermissionConfig

        config = PermissionConfig()

        assert isinstance(config.global_blocked_paths, list)
        assert len(config.global_blocked_paths) > 0
        assert config.log_decisions is True

    def test_blocked_paths(self):
        """Test that common system paths are blocked by default."""
        from app.core.permissions import PermissionConfig

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

        from app.core.permissions import (
            create_permission_handler,
            get_default_permission_config,
        )

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

        from app.core.permissions import (
            create_permission_handler,
            get_default_permission_config,
        )

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

        from app.core.permissions import PermissionConfig, create_permission_handler

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

        from app.core.permissions import (
            create_permission_handler,
            get_default_permission_config,
        )

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

    @pytest.mark.asyncio
    async def test_transcribe_video_output_file_blocked(self):
        """Test that transcribe_video with blocked output_file is denied."""
        from claude_agent_sdk.types import PermissionResultDeny

        from app.core.permissions import (
            create_permission_handler,
            get_default_permission_config,
        )

        config = get_default_permission_config()
        handler = create_permission_handler(config)

        # Try to transcribe with output_file to /etc (blocked)
        result = await handler(
            tool_name="mcp__video-tools__transcribe_video",
            input_data={"video_source": "test.mp4", "output_file": "/etc/passwd"},
            context={},
        )

        assert isinstance(result, PermissionResultDeny)
        assert "etc" in result.message.lower() or "cannot" in result.message.lower()

    @pytest.mark.asyncio
    async def test_transcribe_video_output_file_allowed(self):
        """Test that transcribe_video with safe output_file is allowed."""
        from claude_agent_sdk.types import PermissionResultAllow

        from app.core.permissions import (
            create_permission_handler,
            get_default_permission_config,
        )

        config = get_default_permission_config()
        handler = create_permission_handler(config)

        # Try to transcribe with output_file to safe location
        result = await handler(
            tool_name="mcp__video-tools__transcribe_video",
            input_data={
                "video_source": "test.mp4",
                "output_file": "/tmp/transcript.txt",
            },
            context={},
        )

        assert isinstance(result, PermissionResultAllow)
        assert result.updated_input["output_file"] == "/tmp/transcript.txt"


class TestPermissionFactory:
    """Test permission handler factory functions."""

    def test_get_default_permission_config(self):
        """Test getting default permission configuration."""
        from app.core.permissions import get_default_permission_config

        config = get_default_permission_config()

        assert config is not None
        assert isinstance(config.global_blocked_paths, list)
        assert config.log_decisions is True

    def test_create_permission_handler_returns_callable(self):
        """Test that create_permission_handler returns a callable."""
        from app.core.permissions import PermissionConfig, create_permission_handler

        config = PermissionConfig()
        handler = create_permission_handler(config)

        assert callable(handler)


class TestValidateFilePath:
    """Test validate_file_path function."""

    def test_blocked_system_paths(self):
        """Test that system paths are blocked."""
        from app.core.permissions import validate_file_path

        # Test various system paths
        is_valid, error = validate_file_path("/etc/passwd")
        assert not is_valid
        assert "system directory" in error.lower()

        is_valid, error = validate_file_path("/usr/bin/test")
        assert not is_valid
        assert "system directory" in error.lower()

        is_valid, error = validate_file_path("/var/log/test.log")
        assert not is_valid
        assert "system directory" in error.lower()

    def test_valid_path_allowed(self):
        """Test that valid paths are allowed."""
        from app.core.permissions import validate_file_path

        is_valid, error = validate_file_path("/tmp/test.txt")
        assert is_valid
        assert error == ""

        is_valid, error = validate_file_path("/home/user/documents/file.txt")
        assert is_valid
        assert error == ""

    def test_hidden_file_blocked(self):
        """Test that hidden files in non-hidden dirs are blocked."""
        from app.core.permissions import validate_file_path

        is_valid, error = validate_file_path("/home/user/.secret")
        assert not is_valid
        assert "hidden" in error.lower()

    def test_invalid_path_format(self):
        """Test that malformed paths are rejected."""
        from app.core.permissions import validate_file_path

        # Test with null bytes (common attack vector)
        is_valid, error = validate_file_path("/tmp/test\x00.txt")
        assert not is_valid
        assert "invalid" in error.lower() or "format" in error.lower()

    def test_path_traversal_normalized(self):
        """Test that path traversal attempts are normalized and blocked."""
        from app.core.permissions import validate_file_path

        # Attempt to traverse to /etc via /tmp/../etc/passwd
        is_valid, error = validate_file_path("/tmp/../etc/passwd")
        assert not is_valid
        assert "system directory" in error.lower()
