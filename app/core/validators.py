"""
Centralized validation utilities for UUID and ID patterns.

This module provides a single source of truth for validation patterns used
throughout the codebase, preventing duplication and ensuring consistency.
"""

from __future__ import annotations

import re

# UUID v4 validation pattern (RFC 4122 compliant)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Short ID pattern (8 hex characters, used for transcript_id and file_id)
# Lowercase only - IDs are generated via str(uuid.uuid4())[:8] which produces lowercase
SHORT_ID_PATTERN = re.compile(r"^[0-9a-f]{8}$")

# Project ID pattern (12 hex characters, used for KG project_id)
# Generated via uuid4().hex[:12] which produces lowercase
PROJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def is_valid_uuid(value: str) -> bool:
    """
    Check if a string is a valid UUID v4 format.

    Args:
        value: The string to validate

    Returns:
        True if the value matches UUID v4 format, False otherwise
    """
    return bool(UUID_PATTERN.match(value))


def is_valid_short_id(value: str) -> bool:
    """
    Check if a string is a valid short ID (8 hex characters).

    Args:
        value: The string to validate

    Returns:
        True if the value matches short ID format, False otherwise
    """
    return bool(SHORT_ID_PATTERN.match(value))


def is_valid_project_id(value: str) -> bool:
    """
    Check if a string is a valid project ID (12 hex characters).

    Args:
        value: The string to validate

    Returns:
        True if the value matches project ID format, False otherwise
    """
    return bool(PROJECT_ID_PATTERN.match(value))
