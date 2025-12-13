"""
Transcripts router - handles transcript management.

Provides endpoints for listing, downloading, and deleting transcripts.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import ValidatedTranscriptId, get_storage_service
from app.models.api import TranscriptListResponse
from app.services import StorageService

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.get("", response_model=TranscriptListResponse)
async def list_transcripts(
    storage_svc: StorageService = Depends(get_storage_service),
) -> TranscriptListResponse:
    """
    List all saved transcript files.

    Args:
        storage_svc: Injected storage service

    Returns:
        TranscriptListResponse with transcript metadata
    """
    transcripts = storage_svc.list_transcripts()
    return TranscriptListResponse(transcripts=transcripts, total=len(transcripts))


@router.get("/{transcript_id}/download")
async def download_transcript(
    transcript_id: str = Depends(ValidatedTranscriptId()),
    storage_svc: StorageService = Depends(get_storage_service),
) -> FileResponse:
    """
    Download a transcript file.

    Args:
        transcript_id: Short ID of the transcript (validated)
        storage_svc: Injected storage service

    Returns:
        FileResponse with transcript content

    Raises:
        HTTPException: If transcript or file not found
    """
    metadata = storage_svc.get_transcript_metadata(transcript_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Transcript not found")

    file_path = Path(metadata.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path), filename=metadata.filename, media_type="text/plain"
    )


@router.delete("/{transcript_id}")
async def delete_transcript(
    transcript_id: str = Depends(ValidatedTranscriptId()),
    storage_svc: StorageService = Depends(get_storage_service),
) -> dict[str, bool]:
    """
    Delete a transcript file.

    Args:
        transcript_id: Short ID of the transcript (validated)
        storage_svc: Injected storage service

    Returns:
        Success status
    """
    success = storage_svc.delete_transcript(transcript_id)
    return {"success": success}
