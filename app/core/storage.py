"""
File-based storage manager for sessions and transcripts.

This module provides persistent storage for chat history and transcript metadata
using JSON files, suitable for local development use.

Thread Safety:
    Uses atomic writes (write to temp file, then rename) to prevent data
    corruption from concurrent access. File renames are atomic on POSIX systems.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.validators import is_valid_uuid as _is_valid_uuid


class StorageManager:
    """File-based storage for sessions and transcripts."""

    def __init__(self, base_dir: Path | str = "data") -> None:
        self.base_dir = Path(base_dir)
        self.sessions_dir = self.base_dir / "sessions"
        self.transcripts_dir = self.base_dir / "transcripts"
        self.metadata_file = self.base_dir / "metadata.json"
        # Lock for metadata operations to prevent TOCTOU race conditions
        self._metadata_lock = threading.Lock()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, file_path: Path, data: dict[str, Any]) -> None:
        """
        Atomically write JSON data to a file.

        Uses write-to-temp-then-rename pattern for thread safety.
        File renames are atomic on POSIX systems, preventing partial writes.

        Args:
            file_path: Target file path
            data: Dictionary to serialize as JSON
        """
        # Create temp file in same directory to ensure same filesystem for rename
        fd, temp_path = tempfile.mkstemp(
            suffix=".tmp", prefix=file_path.stem, dir=file_path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            # Atomic rename
            os.replace(temp_path, file_path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _load_metadata(self) -> dict[str, Any]:
        """Load global metadata from file."""
        if self.metadata_file.exists():
            return json.loads(self.metadata_file.read_text())
        return {
            "transcripts": {},
            "global_cost": {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_creation_tokens": 0,
                "total_cache_read_tokens": 0,
                "total_cost_usd": 0.0,
                "session_count": 0,
            },
        }

    def _save_metadata(self, data: dict[str, Any]) -> None:
        """Save global metadata to file atomically."""
        self._atomic_write(self.metadata_file, data)

    # --- Session Methods ---

    def save_message(self, session_id: str, role: str, content: str) -> dict[str, Any]:
        """
        Save a chat message to session history.

        Args:
            session_id: UUID of the session
            role: "user" or "agent"
            content: Message content

        Returns:
            The saved message object

        Raises:
            ValueError: If session_id is not a valid UUID v4
        """
        if not _is_valid_uuid(session_id):
            raise ValueError(f"Invalid session_id format: {session_id}")

        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            session_data = json.loads(session_file.read_text())
        else:
            session_data = {
                "session_id": session_id,
                "title": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "messages": [],
            }

        message = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        session_data["messages"].append(message)
        session_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Set title from first user message
        if not session_data["title"] and role == "user":
            session_data["title"] = content[:50] + ("..." if len(content) > 50 else "")

        self._atomic_write(session_file, session_data)
        return message

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get full session data by ID."""
        if not _is_valid_uuid(session_id):
            return None  # Silently return None for invalid IDs (defense in depth)

        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            return json.loads(session_file.read_text())
        return None

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all sessions with summary info."""
        sessions = []
        for f in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                sessions.append(
                    {
                        "session_id": data["session_id"],
                        "title": data.get("title", "Untitled"),
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "message_count": len(data.get("messages", [])),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue

        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session's history."""
        if not _is_valid_uuid(session_id):
            return False  # Silently return False for invalid IDs (defense in depth)

        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False

    # --- Transcript Methods ---

    def register_transcript(
        self,
        file_path: str,
        original_source: str,
        source_type: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Register a transcript file in the metadata.

        Args:
            file_path: Path to the transcript file
            original_source: YouTube URL or uploaded filename
            source_type: "youtube", "upload", or "local"
            session_id: Optional link to originating session (must be valid UUID if provided)

        Returns:
            The transcript metadata entry

        Raises:
            ValueError: If session_id is provided but not a valid UUID
        """
        # Validate session_id format if provided
        if session_id is not None and not _is_valid_uuid(session_id):
            raise ValueError(f"Invalid session_id format: {session_id}")

        metadata = self._load_metadata()

        transcript_id = str(uuid.uuid4())[:8]
        path = Path(file_path)

        entry = {
            "id": transcript_id,
            "filename": path.name,
            "file_path": str(path.resolve()),
            "original_source": original_source,
            "source_type": source_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "file_size": path.stat().st_size if path.exists() else 0,
            "session_id": session_id,
        }

        metadata["transcripts"][transcript_id] = entry
        self._save_metadata(metadata)
        return entry

    def list_transcripts(self) -> list[dict[str, Any]]:
        """List all registered transcripts."""
        metadata = self._load_metadata()
        transcripts = list(metadata.get("transcripts", {}).values())
        transcripts.sort(key=lambda x: x["created_at"], reverse=True)
        return transcripts

    def get_transcript(self, transcript_id: str) -> dict[str, Any] | None:
        """Get transcript metadata by ID."""
        metadata = self._load_metadata()
        return metadata.get("transcripts", {}).get(transcript_id)

    def delete_transcript(self, transcript_id: str) -> bool:
        """Delete a transcript and optionally its file."""
        metadata = self._load_metadata()
        if transcript_id in metadata.get("transcripts", {}):
            entry = metadata["transcripts"].pop(transcript_id)
            self._save_metadata(metadata)

            # Optionally delete the file
            file_path = Path(entry.get("file_path", ""))
            if file_path.exists():
                file_path.unlink()
            return True
        return False

    # --- Cost Tracking Methods ---

    def save_session_cost(self, session_id: str, cost_data: dict[str, Any]) -> None:
        """
        Save cost tracking data for a session.

        Args:
            session_id: UUID of the session
            cost_data: Dictionary with cost tracking fields

        Raises:
            ValueError: If session_id is not a valid UUID v4
        """
        if not _is_valid_uuid(session_id):
            raise ValueError(f"Invalid session_id format: {session_id}")

        cost_file = self.sessions_dir / f"{session_id}_cost.json"
        self._atomic_write(cost_file, cost_data)

    def get_session_cost(self, session_id: str) -> dict[str, Any] | None:
        """
        Retrieve cost tracking data for a session.

        Args:
            session_id: UUID of the session

        Returns:
            Cost data dictionary or None if not found
        """
        if not _is_valid_uuid(session_id):
            return None

        cost_file = self.sessions_dir / f"{session_id}_cost.json"
        if cost_file.exists():
            return json.loads(cost_file.read_text())
        return None

    def update_global_cost(self, session_cost: dict[str, Any]) -> None:
        """
        Update global cost statistics with session cost data.

        This aggregates costs across all sessions for overall tracking.
        Thread-safe via lock + atomic writes to prevent TOCTOU race conditions.

        Args:
            session_cost: Session cost data with token counts and total_cost_usd
        """
        with self._metadata_lock:
            metadata = self._load_metadata()

            # Initialize global_cost if missing (legacy data)
            if "global_cost" not in metadata:
                metadata["global_cost"] = {
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cache_creation_tokens": 0,
                    "total_cache_read_tokens": 0,
                    "total_cost_usd": 0.0,
                    "session_count": 0,
                }

            global_cost = metadata["global_cost"]

            # Increment totals
            global_cost["total_input_tokens"] += session_cost.get(
                "total_input_tokens", 0
            )
            global_cost["total_output_tokens"] += session_cost.get(
                "total_output_tokens", 0
            )
            global_cost["total_cache_creation_tokens"] += session_cost.get(
                "total_cache_creation_tokens", 0
            )
            global_cost["total_cache_read_tokens"] += session_cost.get(
                "total_cache_read_tokens", 0
            )
            global_cost["total_cost_usd"] += session_cost.get("total_cost_usd", 0.0)
            global_cost["session_count"] += 1

            self._save_metadata(metadata)

    def get_global_cost(self) -> dict[str, Any]:
        """
        Get aggregated cost statistics across all sessions.

        Returns:
            Dictionary with global cost totals
        """
        metadata = self._load_metadata()
        return metadata.get(
            "global_cost",
            {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_creation_tokens": 0,
                "total_cache_read_tokens": 0,
                "total_cost_usd": 0.0,
                "session_count": 0,
            },
        )


# Global storage instance
storage = StorageManager()
