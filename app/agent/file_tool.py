"""
File Writing Tool for Claude Agent SDK.

This module provides a tool for saving content to files, enabling the agent
to persist transcriptions, summaries, and other generated content.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from app.core.permissions import BLOCKED_SYSTEM_PATHS  # noqa: E402


def _validate_path(file_path: str) -> tuple[bool, str]:
    """
    Validate the file path for safety and accessibility.

    Args:
        file_path: The path to validate.

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    # Normalize and resolve the path
    try:
        path = Path(file_path).resolve()
    except (OSError, ValueError) as e:
        return False, f"Invalid path format: {e}"

    # Prevent writing to sensitive system directories
    path_str = str(path)
    for prefix in BLOCKED_SYSTEM_PATHS:
        if path_str.startswith(prefix):
            return False, f"Cannot write to system directory: {prefix}"

    # Prevent overwriting hidden files unless explicitly in a hidden directory
    if path.name.startswith(".") and not any(
        p.startswith(".") for p in path.parent.parts
    ):
        return False, "Cannot write to hidden files in non-hidden directories"

    return True, ""


def _ensure_parent_directory(file_path: Path) -> tuple[bool, str]:
    """
    Ensure the parent directory exists, creating it if necessary.

    Args:
        file_path: The file path whose parent directory should exist.

    Returns:
        Tuple of (success, error_message). If successful, error_message is empty.
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        return True, ""
    except PermissionError:
        return False, f"Permission denied creating directory: {file_path.parent}"
    except OSError as e:
        return False, f"Failed to create directory: {e}"


def _write_file_sync(path: Path, content: str) -> tuple[int, int]:
    """
    Synchronous file write operation.

    Returns:
        Tuple of (file_size, line_count)
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    file_size = os.path.getsize(path)
    line_count = content.count("\n") + (
        1 if content and not content.endswith("\n") else 0
    )
    return file_size, line_count


@tool(
    "write_file",
    "Write or save content to a file. Use this to save transcriptions, summaries, "
    "extracted key points, or any other content the user wants to keep. "
    "Creates parent directories if they don't exist. "
    "Will not overwrite existing files unless overwrite=true.",
    {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path where the file should be saved. "
                "Parent directories will be created if needed.",
            },
            "content": {
                "type": "string",
                "description": "The text content to write to the file.",
            },
            "overwrite": {
                "type": "boolean",
                "description": "If true, overwrite existing files. Default is false.",
                "default": False,
            },
        },
        "required": ["file_path", "content"],
    },
)
async def write_file(args: dict[str, Any]) -> dict[str, Any]:
    """
    Write content to a file.

    This tool enables the agent to save transcriptions, summaries, and other
    generated content to files when requested by the user.

    Args:
        args: Dictionary containing:
            - file_path: Path where the file should be saved (required)
            - content: Text content to write (required)
            - overwrite: Whether to overwrite existing files (optional, default False)

    Returns:
        Structured response indicating success or failure with details.
    """
    file_path = args.get("file_path")
    content = args.get("content")
    overwrite = args.get("overwrite", False)

    # Validate required parameters
    if not file_path:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: file_path parameter is required",
                }
            ]
        }

    if content is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: content parameter is required",
                }
            ]
        }

    # Resolve to absolute path
    try:
        path = Path(file_path).resolve()
    except (OSError, ValueError) as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Invalid file path - {e}",
                }
            ]
        }

    # Validate path safety
    is_valid, error_msg = _validate_path(str(path))
    if not is_valid:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {error_msg}",
                }
            ]
        }

    # Check if file exists
    if path.exists() and not overwrite:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: File already exists: {path}\n"
                    "Set overwrite=true to replace the existing file.",
                }
            ]
        }

    # Ensure parent directory exists
    success, error_msg = _ensure_parent_directory(path)
    if not success:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {error_msg}",
                }
            ]
        }

    # Write the file asynchronously
    try:
        file_size, line_count = await asyncio.to_thread(_write_file_sync, path, content)

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Successfully saved file: {path}\n"
                    f"Size: {file_size:,} bytes\n"
                    f"Lines: {line_count:,}",
                }
            ]
        }

    except PermissionError:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Permission denied writing to: {path}",
                }
            ]
        }
    except OSError as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: Failed to write file - {e}",
                }
            ]
        }
