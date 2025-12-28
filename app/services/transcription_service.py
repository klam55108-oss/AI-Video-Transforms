"""
Transcription Service - Orchestrates transcript workflows.

Coordinates between transcript generation and storage, providing
high-level operations for the API layer.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.models.api import TranscriptMetadata
from app.models.service import SourceType, TranscriptContent
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Service layer for transcription operations.

    Orchestrates transcript save workflows by coordinating between
    the transcription process and storage layer.
    """

    def __init__(self, storage_service: StorageService) -> None:
        """
        Initialize transcription service.

        Args:
            storage_service: Storage service for persistence
        """
        self._storage = storage_service

    async def save_transcript(
        self,
        file_path: str,
        original_source: str,
        source_type: SourceType,
        session_id: str | None = None,
        title: str | None = None,
    ) -> TranscriptMetadata:
        """
        Save and register a transcript.

        Args:
            file_path: Path to the transcript file
            original_source: YouTube URL or uploaded filename
            source_type: Video source type
            session_id: Optional link to originating session
            title: Optional human-readable title (e.g., video name for YouTube)
                   Used for evidence linking in knowledge graphs

        Returns:
            TranscriptMetadata for the saved transcript

        Raises:
            FileNotFoundError: If file_path doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Transcript file not found: {file_path}")

        logger.info(
            f"Registering transcript: {path.name} (source: {source_type.value})"
        )

        metadata = self._storage.register_transcript(
            file_path=str(path.resolve()),
            original_source=original_source,
            source_type=source_type,
            session_id=session_id,
            title=title,
        )

        logger.info(f"Transcript registered with ID: {metadata.id}")
        return metadata

    async def get_transcript(self, transcript_id: str) -> TranscriptContent | None:
        """
        Retrieve transcript content by ID.

        Args:
            transcript_id: Transcript ID

        Returns:
            TranscriptContent model or None if not found
        """
        # Get raw metadata from storage (includes internal file_path)
        from app.core.storage import storage as raw_storage

        metadata_dict = raw_storage.get_transcript(transcript_id)
        if not metadata_dict:
            logger.warning(f"Transcript not found: {transcript_id}")
            return None

        file_path = metadata_dict["file_path"]
        content = self._storage.get_transcript_content(file_path)
        if not content:
            logger.error(f"Transcript metadata exists but file missing: {file_path}")
            return None

        return content

    async def list_transcripts(self) -> list[TranscriptMetadata]:
        """
        List all registered transcripts.

        Returns:
            List of TranscriptMetadata sorted by created_at descending
        """
        return self._storage.list_transcripts()

    async def delete_transcript(self, transcript_id: str) -> bool:
        """
        Delete a transcript and its file.

        Args:
            transcript_id: Transcript ID

        Returns:
            True if deleted, False if not found
        """
        metadata = self._storage.get_transcript_metadata(transcript_id)
        if not metadata:
            logger.warning(f"Cannot delete: transcript not found: {transcript_id}")
            return False

        success = self._storage.delete_transcript(transcript_id)
        if success:
            logger.info(f"Deleted transcript: {transcript_id} ({metadata.filename})")
        return success

    def get_transcript_metadata(self, transcript_id: str) -> TranscriptMetadata | None:
        """
        Get transcript metadata without content.

        Args:
            transcript_id: Transcript ID

        Returns:
            TranscriptMetadata or None if not found
        """
        return self._storage.get_transcript_metadata(transcript_id)
