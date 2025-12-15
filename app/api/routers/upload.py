"""
Upload router - handles video file uploads.

Provides endpoint for uploading video files for transcription.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.core.validators import UUID_PATTERN
from app.models.api import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])

# Upload configuration
UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    session_id: str = Form(...),
) -> UploadResponse:
    """
    Upload a video file for transcription.

    Args:
        file: The video file to upload
        session_id: UUID of the session making the upload

    Returns:
        UploadResponse with file ID and path, or error message
    """
    # Validate session_id is a valid UUID v4
    if not UUID_PATTERN.match(session_id):
        return UploadResponse(success=False, error="Invalid session ID format")

    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return UploadResponse(
            success=False,
            error=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Sanitize filename - extract only the base name to prevent path traversal
    original_filename = Path(file.filename or "upload").name
    if not original_filename or original_filename.startswith("."):
        original_filename = "upload" + ext

    # Create session upload directory
    session_upload_dir = UPLOAD_DIR / session_id
    session_upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with sanitized original name
    file_id = str(uuid.uuid4())[:8]
    safe_filename = f"{file_id}_{original_filename}"
    file_path = session_upload_dir / safe_filename

    # Stream file to disk with size validation
    try:
        total_size = 0
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    buffer.close()
                    file_path.unlink(missing_ok=True)
                    return UploadResponse(
                        success=False,
                        error=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
                    )
                buffer.write(chunk)

        return UploadResponse(success=True, file_id=file_id)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        # Clean up partial file on error
        file_path.unlink(missing_ok=True)
        return UploadResponse(success=False, error="Upload failed")
