"""
Dependency injection providers for API endpoints.

Provides FastAPI dependencies that inject service instances into route
handlers, enabling loose coupling and testability.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.core.validators import PROJECT_ID_PATTERN, SHORT_ID_PATTERN, UUID_PATTERN
from app.services import (
    AuditService,
    JobQueueService,
    KnowledgeGraphService,
    SessionService,
    StorageService,
    TranscriptionService,
    get_services,
)


def get_session_service() -> SessionService:
    """
    Dependency provider for SessionService.

    Returns:
        SessionService instance from the global container
    """
    return get_services().session


def get_storage_service() -> StorageService:
    """
    Dependency provider for StorageService.

    Returns:
        StorageService instance from the global container
    """
    return get_services().storage


def get_transcription_service() -> TranscriptionService:
    """
    Dependency provider for TranscriptionService.

    Returns:
        TranscriptionService instance from the global container
    """
    return get_services().transcription


def validate_uuid(value: str, field_name: str = "ID") -> str:
    """
    Validate that a string is a valid UUID v4 format.

    Args:
        value: The string to validate
        field_name: Name of the field for error messages

    Returns:
        The validated value

    Raises:
        HTTPException: If the value is not a valid UUID v4
    """
    if not UUID_PATTERN.match(value):
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name} format (must be UUID v4)"
        )
    return value


def validate_short_id(value: str, field_name: str = "ID") -> str:
    """
    Validate that a string is a valid short ID (8 hex characters).

    Args:
        value: The string to validate
        field_name: Name of the field for error messages

    Returns:
        The validated value

    Raises:
        HTTPException: If the value is not a valid short ID
    """
    if not SHORT_ID_PATTERN.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")
    return value


def validate_project_id(value: str, field_name: str = "project ID") -> str:
    """
    Validate that a string is a valid project ID (12 hex characters).

    Args:
        value: The string to validate
        field_name: Name of the field for error messages

    Returns:
        The validated value

    Raises:
        HTTPException: If the value is not a valid project ID
    """
    if not PROJECT_ID_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format (must be 12 hex characters)",
        )
    return value


class ValidatedSessionId:
    """
    Dependency class for validated session ID path parameters.

    Usage:
        @router.get("/{session_id}")
        async def endpoint(session_id: str = Depends(ValidatedSessionId())):
            ...
    """

    def __call__(self, session_id: str) -> str:
        """Validate and return the session ID."""
        return validate_uuid(session_id, "session ID")


class ValidatedTranscriptId:
    """
    Dependency class for validated transcript ID path parameters.

    Usage:
        @router.get("/{transcript_id}")
        async def endpoint(transcript_id: str = Depends(ValidatedTranscriptId())):
            ...
    """

    def __call__(self, transcript_id: str) -> str:
        """Validate and return the transcript ID."""
        return validate_short_id(transcript_id, "transcript ID")


class ValidatedProjectId:
    """
    Dependency class for validated KG project ID path parameters.

    Usage:
        @router.get("/projects/{project_id}")
        async def endpoint(project_id: str = Depends(ValidatedProjectId())):
            ...
    """

    def __call__(self, project_id: str) -> str:
        """Validate and return the project ID."""
        return validate_project_id(project_id, "project ID")


def get_kg_service() -> KnowledgeGraphService:
    """
    Dependency provider for KnowledgeGraphService.

    Returns:
        KnowledgeGraphService instance from the global container
    """
    return get_services().kg


def get_job_queue_service() -> JobQueueService:
    """
    Dependency provider for JobQueueService.

    Returns:
        JobQueueService instance from the global container
    """
    return get_services().job_queue


def get_audit_service() -> AuditService:
    """
    Dependency provider for AuditService.

    Returns:
        AuditService instance from the global container
    """
    return get_services().audit
