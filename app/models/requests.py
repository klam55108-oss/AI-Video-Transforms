"""
Request models for API endpoints.

Defines Pydantic models for validating incoming HTTP requests,
including chat messages and session initialization.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.validators import UUID_PATTERN


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
