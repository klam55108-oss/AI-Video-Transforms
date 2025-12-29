"""
Request models for API endpoints.

Defines Pydantic models for validating incoming HTTP requests,
including chat messages and session initialization.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from app.core.validators import UUID_PATTERN

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entity Name Validation Constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Maximum length for entity names (labels, names) in KB
MAX_ENTITY_NAME_LENGTH = 500

# Control character pattern (C0 and C1 control chars)
# C0: \x00-\x1f (except common whitespace like \t \n \r which we'll preserve)
# C1: \x7f-\x9f (DEL and extended control chars)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Node ID pattern: exactly 12 hex characters (matches KG node ID format)
# Node IDs are generated via uuid4().hex[:12] which produces lowercase hex
NODE_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def sanitize_entity_name(value: str) -> str:
    """Sanitize an entity name by stripping control characters.

    Args:
        value: The entity name to sanitize.

    Returns:
        Sanitized string with control characters removed and whitespace stripped.

    Raises:
        ValueError: If the resulting name exceeds MAX_ENTITY_NAME_LENGTH.
    """
    if not value:
        return value

    # Strip control characters (preserving normal whitespace like spaces, tabs)
    sanitized = CONTROL_CHAR_PATTERN.sub("", value)

    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()

    # Enforce max length
    if len(sanitized) > MAX_ENTITY_NAME_LENGTH:
        raise ValueError(
            f"Entity name exceeds {MAX_ENTITY_NAME_LENGTH} characters "
            f"(got {len(sanitized)})"
        )

    return sanitized


class EntityNameMixin:
    """Mixin providing entity name validation for Pydantic models.

    Models using this mixin should have 'name' and/or 'label' fields.
    The validator strips control characters and enforces max length.

    Example:
        class CreateEntityRequest(EntityNameMixin, BaseModel):
            name: str
            label: str | None = None
    """

    @field_validator("name", "label", mode="before", check_fields=False)
    @classmethod
    def validate_entity_name(cls, v: str | None) -> str | None:
        """Strip control characters and enforce max length on entity names."""
        if v is None:
            return None
        return sanitize_entity_name(v)


class ChatRequest(BaseModel):
    """Request model for chat messages."""

    session_id: str = Field(
        ..., min_length=36, max_length=36, description="UUID v4 session identifier"
    )
    message: str = Field(
        ..., min_length=1, max_length=50000, description="User message content"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        """Validate session_id is a valid UUID v4."""
        if not UUID_PATTERN.match(v):
            raise ValueError("session_id must be a valid UUID v4 format")
        return v

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        """Validate message is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("message cannot be empty or whitespace only")
        return stripped


class InitRequest(BaseModel):
    """Request model for session initialization."""

    session_id: str = Field(
        ..., min_length=36, max_length=36, description="UUID v4 session identifier"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id_format(cls, v: str) -> str:
        """Validate session_id is a valid UUID v4."""
        if not UUID_PATTERN.match(v):
            raise ValueError("session_id must be a valid UUID v4 format")
        return v


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Knowledge Graph Request Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CreateProjectRequest(BaseModel):
    """Request model for creating a new KG project."""

    name: str = Field(..., min_length=1, max_length=200, description="Project name")


class BootstrapRequest(BaseModel):
    """Request model for bootstrapping a project from a transcript."""

    transcript: str = Field(..., min_length=1, description="Transcript content")
    title: str = Field(..., min_length=1, max_length=500, description="Source title")
    source_id: str = Field(..., min_length=1, max_length=50, description="Source ID")


class ConfirmDiscoveryRequest(BaseModel):
    """Request model for confirming or rejecting a discovery."""

    discovery_id: str = Field(..., min_length=1, description="Discovery ID to confirm")
    confirmed: bool = Field(..., description="True to confirm, False to reject")


class ExtractRequest(BaseModel):
    """Request model for extracting entities from a transcript."""

    transcript: str = Field(..., min_length=1, description="Transcript content")
    title: str = Field(..., min_length=1, max_length=500, description="Source title")
    source_id: str = Field(..., min_length=1, max_length=50, description="Source ID")
    transcript_id: str | None = Field(
        default=None,
        max_length=50,
        description="Transcript ID (from save_transcript) for evidence linking",
    )


class ExportRequest(BaseModel):
    """Request model for exporting the knowledge graph."""

    format: str = Field(
        default="graphml",
        pattern="^(graphml|json|csv)$",
        description="Export format: 'graphml', 'json', or 'csv'",
    )


class BatchExportRequest(BaseModel):
    """Request model for batch exporting multiple projects."""

    project_ids: list[str] = Field(
        ..., min_length=1, description="List of project IDs to export"
    )
    format: str = Field(
        default="graphml",
        pattern="^(graphml|json|csv)$",
        description="Export format: 'graphml', 'json', or 'csv'",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entity Resolution Request Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MergeEntitiesRequest(BaseModel):
    """Request model for merging two entities.

    Node IDs must be exactly 12 lowercase hex characters (KG node ID format).
    Optional request_id provides idempotency for retry scenarios.
    """

    survivor_id: str = Field(..., description="ID of node to keep (12 hex chars)")
    merged_id: str = Field(
        ..., description="ID of node to merge into survivor (12 hex chars)"
    )
    request_id: str | None = Field(
        default=None,
        max_length=64,
        description="Idempotency key for deduplicating retries",
    )

    @field_validator("survivor_id", "merged_id")
    @classmethod
    def validate_node_id(cls, v: str) -> str:
        """Validate node ID format (12 lowercase hex characters)."""
        if not v:
            raise ValueError("Node ID cannot be empty")
        if len(v) != 12:
            raise ValueError("Node ID must be exactly 12 characters")
        if not NODE_ID_PATTERN.match(v):
            raise ValueError("Node ID must be lowercase hexadecimal")
        return v


class ReviewMergeRequest(BaseModel):
    """Request model for approving or rejecting a merge candidate."""

    approved: bool = Field(..., description="Whether to approve the merge")


class ScanDuplicatesRequest(BaseModel):
    """Request model for scanning for duplicate entities."""

    auto_merge_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override auto-merge threshold (0.0-1.0)",
    )
    review_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override review threshold (0.0-1.0)",
    )
