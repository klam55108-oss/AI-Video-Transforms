"""
Permission handler for Claude Agent SDK tool access control.

This module implements dynamic permission logic for restricting agent tool usage,
with special focus on preventing writes to system directories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk.types import (
    ToolPermissionContext,
    PermissionResultAllow,
    PermissionResultDeny,
)

logger = logging.getLogger(__name__)

# Single source of truth for system paths that should never be written to
BLOCKED_SYSTEM_PATHS = [
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/var",
    "/boot",
    "/sys",
    "/proc",
    "/dev",
]


@dataclass
class PermissionConfig:
    """
    Configuration for permission handler behavior.

    Attributes:
        global_blocked_paths: Path prefixes that cannot be written to
        log_decisions: Whether to log all permission decisions
    """

    global_blocked_paths: list[str] = field(
        default_factory=lambda: BLOCKED_SYSTEM_PATHS.copy()
    )
    log_decisions: bool = True


def create_permission_handler(
    config: PermissionConfig,
) -> Any:  # Returns the permission_handler async callable
    """
    Factory function that creates a permission handler callback.

    The returned async function matches the signature required by
    ClaudeAgentOptions.can_use_tool.

    Args:
        config: Permission configuration

    Returns:
        Async permission handler function
    """

    async def permission_handler(
        tool_name: str, input_data: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        """
        Permission callback invoked before each tool use.

        Args:
            tool_name: Name of the tool being invoked
            input_data: Tool input arguments
            context: Additional context from the SDK

        Returns:
            Permission decision (Allow or Deny)
        """
        # Check file write operations for blocked paths
        if tool_name in ("mcp__video-tools__write_file", "Write", "Edit"):
            file_path = input_data.get("file_path", "")

            for blocked in config.global_blocked_paths:
                if file_path.startswith(blocked):
                    if config.log_decisions:
                        logger.warning(
                            f"DENIED: {tool_name} to {file_path} (blocked path: {blocked})"
                        )
                    return PermissionResultDeny(
                        message=f"Cannot write to system directory: {blocked}",
                        interrupt=True,
                    )

        # Log allowed operations
        if config.log_decisions:
            logger.info(f"ALLOWED: {tool_name}")

        return PermissionResultAllow(updated_input=input_data)

    return permission_handler


def get_default_permission_config() -> PermissionConfig:
    """
    Get default permission configuration for video transcription use case.

    Blocks writes to system directories but allows everything else needed
    for video processing, transcription, and file storage.

    Returns:
        PermissionConfig with sensible defaults
    """
    return PermissionConfig(
        global_blocked_paths=BLOCKED_SYSTEM_PATHS.copy(),
        log_decisions=True,
    )
