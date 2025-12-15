"""
Permission handler for Claude Agent SDK tool access control.

This module implements dynamic permission logic for restricting agent tool usage,
with special focus on preventing writes to system directories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
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


def validate_file_path(file_path: str) -> tuple[bool, str]:
    """
    Validate file path for safety.

    Args:
        file_path: The path to validate.

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    try:
        path = Path(file_path).resolve()
    except (OSError, ValueError) as e:
        return False, f"Invalid path format: {e}"

    path_str = str(path)
    for prefix in BLOCKED_SYSTEM_PATHS:
        if path_str.startswith(prefix):
            return False, f"Cannot write to system directory: {prefix}"

    if path.name.startswith(".") and not any(
        p.startswith(".") for p in path.parent.parts
    ):
        return False, "Cannot write to hidden files in non-hidden directories"

    return True, ""


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
            raw_path = input_data.get("file_path", "")

            # Normalize path to prevent bypass via traversal (e.g., /etc/../etc/passwd)
            # or symlinks pointing to blocked directories
            try:
                normalized_path = str(Path(raw_path).resolve())
            except (OSError, ValueError):
                normalized_path = raw_path

            for blocked in config.global_blocked_paths:
                if normalized_path.startswith(blocked):
                    if config.log_decisions:
                        logger.warning(
                            f"DENIED: {tool_name} to {normalized_path} (blocked path: {blocked})"
                        )
                    return PermissionResultDeny(
                        message=f"Cannot write to system directory: {blocked}",
                        interrupt=True,
                    )

        # Check transcribe_video's optional output_file parameter
        if tool_name == "mcp__video-tools__transcribe_video":
            raw_path = input_data.get("output_file", "")
            if raw_path:
                try:
                    normalized_path = str(Path(raw_path).resolve())
                except (OSError, ValueError):
                    normalized_path = raw_path

                for blocked in config.global_blocked_paths:
                    if normalized_path.startswith(blocked):
                        if config.log_decisions:
                            logger.warning(
                                f"DENIED: {tool_name} output_file to {normalized_path} (blocked path: {blocked})"
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
