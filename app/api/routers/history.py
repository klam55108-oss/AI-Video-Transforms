"""
History router - handles chat session history.

Provides endpoints for listing sessions and retrieving full chat history.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ValidatedSessionId, get_storage_service
from app.models.api import HistoryListResponse, SessionDetail
from app.services import StorageService

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryListResponse)
async def list_history(
    limit: int = 50,
    storage_svc: StorageService = Depends(get_storage_service),
) -> HistoryListResponse:
    """
    List all chat sessions with previews.

    Args:
        limit: Maximum number of sessions to return (default 50)
        storage_svc: Injected storage service

    Returns:
        HistoryListResponse with session summaries
    """
    sessions = storage_svc.list_sessions(limit=limit)
    return HistoryListResponse(sessions=sessions, total=len(sessions))


@router.get("/{session_id}", response_model=SessionDetail)
async def get_history(
    session_id: str = Depends(ValidatedSessionId()),
    storage_svc: StorageService = Depends(get_storage_service),
) -> SessionDetail:
    """
    Get full chat history for a session.

    Args:
        session_id: UUID of the session (validated)
        storage_svc: Injected storage service

    Returns:
        SessionDetail with full message history

    Raises:
        HTTPException: If session not found
    """
    session = storage_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session history not found")
    return session


@router.delete("/{session_id}")
async def delete_history(
    session_id: str = Depends(ValidatedSessionId()),
    storage_svc: StorageService = Depends(get_storage_service),
) -> dict[str, bool]:
    """
    Delete a session's history.

    Args:
        session_id: UUID of the session (validated)
        storage_svc: Injected storage service

    Returns:
        Success status
    """
    success = storage_svc.delete_session(session_id)
    return {"success": success}
