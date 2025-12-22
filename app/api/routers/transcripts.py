"""
Transcripts router - handles transcript management.

Provides endpoints for listing, downloading, and deleting transcripts.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.api.deps import ValidatedTranscriptId, get_storage_service
from app.models.api import TranscriptListResponse
from app.models.transcript import Transcript
from app.services import StorageService
from app.services.transcript_exporter import TranscriptExporter

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


@router.get("/{transcript_id}/export")
async def export_transcript(
    transcript_id: str = Depends(ValidatedTranscriptId()),
    format: str = Query(default="json", pattern="^(srt|vtt|json|txt)$"),
    storage_svc: StorageService = Depends(get_storage_service),
) -> Response:
    """
    Export a transcript in the specified format.

    Supports JSON, plain text, SRT, and VTT export formats.
    Note: SRT/VTT exports return single-caption format (no segment timestamps).

    Args:
        transcript_id: Short ID of the transcript (validated)
        format: Export format (srt, vtt, json, txt) - defaults to json
        storage_svc: Injected storage service

    Returns:
        Response with exported content and appropriate content-type header

    Raises:
        HTTPException: If transcript not found
    """
    import json as json_lib

    # Get raw metadata via injected service (includes file_path)
    metadata_dict = storage_svc.get_transcript_raw(transcript_id)
    if not metadata_dict:
        raise HTTPException(status_code=404, detail="Transcript not found")

    # Load the transcript JSON file
    json_path = Path(metadata_dict["file_path"]).with_suffix(".json")
    if not json_path.exists():
        # Fallback: Create minimal transcript from text file
        txt_path = Path(metadata_dict["file_path"])
        if not txt_path.exists():
            raise HTTPException(status_code=404, detail="Transcript file not found")

        from datetime import datetime

        created_at_str = metadata_dict.get("created_at", "")
        created_at = (
            datetime.fromisoformat(created_at_str) if created_at_str else datetime.now()
        )

        transcript = Transcript(
            id=transcript_id,
            source=metadata_dict.get("original_source", ""),
            source_type=metadata_dict.get("source_type", "local_file"),
            text=txt_path.read_text(encoding="utf-8"),
            duration=float(metadata_dict.get("duration", 0.0)),
            created_at=created_at,
        )
    else:
        # Load from JSON file
        transcript_data = json_lib.loads(json_path.read_text(encoding="utf-8"))
        transcript = Transcript.model_validate(transcript_data)

    # Export to requested format
    exporter = TranscriptExporter()
    if format == "srt":
        content = exporter.export_srt(transcript)
        media_type = "application/x-subrip"
        extension = "srt"
    elif format == "vtt":
        content = exporter.export_vtt(transcript)
        media_type = "text/vtt"
        extension = "vtt"
    elif format == "json":
        content = exporter.export_json(transcript)
        media_type = "application/json"
        extension = "json"
    elif format == "txt":
        content = exporter.export_txt(transcript)
        media_type = "text/plain"
        extension = "txt"
    else:
        # Should never reach here due to Query regex validation
        raise HTTPException(status_code=400, detail="Invalid format")

    # Generate filename
    filename = f"{transcript_id}.{extension}"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    # Get raw metadata via injected service (includes file_path)
    metadata_dict = storage_svc.get_transcript_raw(transcript_id)
    if not metadata_dict:
        raise HTTPException(status_code=404, detail="Transcript not found")

    file_path = Path(metadata_dict["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=metadata_dict["filename"],
        media_type="text/plain",
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
