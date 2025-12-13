"""
Service layer models and types.

This module defines enums, models, and exceptions used by the service layer
to abstract storage and session management logic.
"""

from enum import Enum

from pydantic import BaseModel


class SourceType(str, Enum):
    """Video source types for transcription."""

    YOUTUBE = "youtube"
    UPLOAD = "upload"
    LOCAL = "local"


class SessionStatus(str, Enum):
    """Possible states for a session actor."""

    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"
    CLOSED = "closed"


class TranscriptContent(BaseModel):
    """Content of a transcript file."""

    content: str


class GlobalCostStats(BaseModel):
    """Global cost statistics across all sessions."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cost_usd: float = 0.0
    session_count: int = 0


class ServiceUnavailableError(Exception):
    """Raised when a service is not available (e.g., missing API key)."""

    def __init__(self, message: str = "Service unavailable"):
        self.message = message
        super().__init__(self.message)
