"""
Storage Service - Typed wrapper around StorageManager.

Provides a typed interface to the file-based storage layer with
Pydantic model transformations for API consumption.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.storage import storage
from app.models.api import (
    ChatMessage,
    GlobalCostResponse,
    SessionDetail,
    SessionSummary,
    TranscriptMetadata,
    UsageStats,
)
from app.models.service import SourceType, TranscriptContent


class StorageService:
    """
    Service layer for storage operations.

    Wraps StorageManager with typed methods that return Pydantic models
    suitable for API responses. Handles serialization/deserialization
    between raw dict storage and typed models.
    """

    def __init__(self) -> None:
        """Initialize storage service with global storage manager."""
        self._storage = storage

    # --- Session Methods ---

    def get_session(self, session_id: str) -> SessionDetail | None:
        """
        Retrieve full session data including all messages.

        Args:
            session_id: UUID of the session

        Returns:
            SessionDetail model or None if not found
        """
        data = self._storage.get_session(session_id)
        if not data:
            return None

        return SessionDetail(
            session_id=data["session_id"],
            title=data.get("title", "Untitled"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=[
                ChatMessage(
                    id=msg["id"],
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                )
                for msg in data.get("messages", [])
            ],
        )

    def list_sessions(self, limit: int = 50) -> list[SessionSummary]:
        """
        List all sessions with summary info.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of SessionSummary models sorted by updated_at descending
        """
        sessions_data = self._storage.list_sessions(limit=limit)

        return [
            SessionSummary(
                session_id=s["session_id"],
                title=s["title"],
                created_at=datetime.fromisoformat(s["created_at"]),
                updated_at=datetime.fromisoformat(s["updated_at"]),
                message_count=s["message_count"],
            )
            for s in sessions_data
        ]

    def save_message(self, session_id: str, role: str, content: str) -> dict[str, str]:
        """
        Save a chat message to session history.

        Args:
            session_id: UUID of the session
            role: "user" or "agent"
            content: Message content

        Returns:
            The saved message dict with id and timestamp
        """
        return self._storage.save_message(session_id, role, content)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session's history.

        Args:
            session_id: UUID of the session

        Returns:
            True if deleted, False if not found
        """
        return self._storage.delete_session(session_id)

    # --- Transcript Methods ---

    def register_transcript(
        self,
        file_path: str,
        original_source: str,
        source_type: SourceType,
        session_id: str | None = None,
        title: str | None = None,
    ) -> TranscriptMetadata:
        """
        Register a transcript file in metadata.

        Args:
            file_path: Path to the transcript file
            original_source: YouTube URL or uploaded filename
            source_type: Video source type
            session_id: Optional link to originating session
            title: Optional human-readable title (e.g., video name for YouTube)
                   Used for evidence linking in knowledge graphs

        Returns:
            TranscriptMetadata model for the registered transcript
        """
        entry = self._storage.register_transcript(
            file_path=file_path,
            original_source=original_source,
            source_type=source_type.value,
            session_id=session_id,
            title=title,
        )

        return TranscriptMetadata(
            id=entry["id"],
            filename=entry["filename"],
            original_source=entry["original_source"],
            source_type=entry["source_type"],
            created_at=datetime.fromisoformat(entry["created_at"]),
            file_size=entry["file_size"],
            session_id=entry.get("session_id"),
        )

    def list_transcripts(self) -> list[TranscriptMetadata]:
        """
        List all registered transcripts.

        Returns:
            List of TranscriptMetadata models sorted by created_at descending
        """
        transcripts_data = self._storage.list_transcripts()

        return [
            TranscriptMetadata(
                id=t["id"],
                filename=t["filename"],
                original_source=t["original_source"],
                source_type=t["source_type"],
                created_at=datetime.fromisoformat(t["created_at"]),
                file_size=t["file_size"],
                session_id=t.get("session_id"),
                title=t.get("title"),  # Human-readable title for KG matching
                format=t.get("format", "text"),
                duration=t.get("duration"),
            )
            for t in transcripts_data
        ]

    def get_transcript_metadata(self, transcript_id: str) -> TranscriptMetadata | None:
        """
        Get transcript metadata by ID.

        Args:
            transcript_id: Transcript ID

        Returns:
            TranscriptMetadata model or None if not found
        """
        data = self._storage.get_transcript(transcript_id)
        if not data:
            return None

        return TranscriptMetadata(
            id=data["id"],
            filename=data["filename"],
            original_source=data["original_source"],
            source_type=data["source_type"],
            created_at=datetime.fromisoformat(data["created_at"]),
            file_size=data["file_size"],
            session_id=data.get("session_id"),
            format=data.get("format", "text"),
            duration=data.get("duration"),
        )

    def get_transcript_raw(self, transcript_id: str) -> dict[str, str] | None:
        """
        Get raw transcript metadata dict including internal file_path.

        This method is for internal use (export/download) where file_path
        is needed. For API responses, use get_transcript_metadata() instead.

        Args:
            transcript_id: Transcript ID

        Returns:
            Raw metadata dict with file_path, or None if not found
        """
        return self._storage.get_transcript(transcript_id)

    def get_transcript_content(self, file_path: str) -> TranscriptContent | None:
        """
        Read transcript content from file.

        Args:
            file_path: Path to transcript file

        Returns:
            TranscriptContent model or None if file doesn't exist
        """
        path = Path(file_path)

        if not path.exists():
            return None

        return TranscriptContent(content=path.read_text(encoding="utf-8"))

    def delete_transcript(self, transcript_id: str) -> bool:
        """
        Delete a transcript and its file.

        Args:
            transcript_id: Transcript ID

        Returns:
            True if deleted, False if not found
        """
        return self._storage.delete_transcript(transcript_id)

    # --- Cost Tracking Methods ---

    def get_global_cost(self) -> GlobalCostResponse:
        """
        Get aggregated cost statistics across all sessions.

        Returns:
            GlobalCostResponse model with total costs and session count
        """
        data = self._storage.get_global_cost()

        return GlobalCostResponse(
            total_input_tokens=data["total_input_tokens"],
            total_output_tokens=data["total_output_tokens"],
            total_cache_creation_tokens=data["total_cache_creation_tokens"],
            total_cache_read_tokens=data["total_cache_read_tokens"],
            total_cost_usd=data["total_cost_usd"],
            session_count=data["session_count"],
            last_updated=None,  # Storage doesn't track this yet
        )

    def get_session_cost(self, session_id: str) -> UsageStats | None:
        """
        Get cost data for a specific session.

        Args:
            session_id: UUID of the session

        Returns:
            UsageStats model or None if not found
        """
        data = self._storage.get_session_cost(session_id)
        if not data:
            return None

        return UsageStats(
            input_tokens=data.get("total_input_tokens", 0),
            output_tokens=data.get("total_output_tokens", 0),
            cache_creation_tokens=data.get("total_cache_creation_tokens", 0),
            cache_read_tokens=data.get("total_cache_read_tokens", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
        )
