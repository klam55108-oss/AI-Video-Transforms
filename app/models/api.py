"""
Pydantic models for web app API endpoints.

These models define the request/response schemas for the VideoAgent API,
including chat, history, transcripts, and upload features.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AgentStatus(str, Enum):
    """Possible states for the agent."""

    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"


class StatusResponse(BaseModel):
    """Response for /status endpoint."""

    status: AgentStatus
    session_id: str | None = None
    message: str | None = None


class ChatMessage(BaseModel):
    """A single chat message."""

    id: str
    role: str  # "user" | "agent"
    content: str
    timestamp: datetime


class SessionSummary(BaseModel):
    """Summary info for a chat session (for list views)."""

    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class SessionDetail(BaseModel):
    """Full session data including all messages."""

    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage]


class HistoryListResponse(BaseModel):
    """Response for /history endpoint."""

    sessions: list[SessionSummary]
    total: int


class TranscriptMetadata(BaseModel):
    """Metadata for a saved transcript."""

    id: str
    filename: str
    file_path: str
    original_source: str
    source_type: str  # "youtube" | "upload" | "local"
    created_at: datetime
    file_size: int
    session_id: str | None = None


class TranscriptListResponse(BaseModel):
    """Response for /transcripts endpoint."""

    transcripts: list[TranscriptMetadata]
    total: int


class UploadResponse(BaseModel):
    """Response for /upload endpoint."""

    success: bool
    file_id: str | None = None
    file_path: str | None = None
    error: str | None = None


class UsageStats(BaseModel):
    """Token usage statistics from Claude API."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    total_cost_usd: float = 0.0


class SessionCostResponse(BaseModel):
    """Cost data for a specific session."""

    session_id: str
    usage: UsageStats
    last_updated: datetime | None = None


class GlobalCostResponse(BaseModel):
    """Global cost statistics across all sessions."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cost_usd: float = 0.0
    session_count: int = 0
    last_updated: datetime | None = None


class ChatResponse(BaseModel):
    """Response model for chat messages."""

    response: str
    session_id: str
    usage: UsageStats | None = None  # Optional usage statistics
