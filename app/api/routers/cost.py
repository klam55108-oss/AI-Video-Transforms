"""
Cost router - handles usage and cost tracking.

Provides endpoints for session-specific and global cost statistics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ValidatedSessionId, get_storage_service
from app.models.api import GlobalCostResponse, SessionCostResponse
from app.services import StorageService

router = APIRouter(prefix="/cost", tags=["cost"])


@router.get("/{session_id}", response_model=SessionCostResponse)
async def get_session_cost(
    session_id: str = Depends(ValidatedSessionId()),
    storage_svc: StorageService = Depends(get_storage_service),
) -> SessionCostResponse:
    """
    Get cost tracking data for a specific session.

    Args:
        session_id: UUID of the session (validated)
        storage_svc: Injected storage service

    Returns:
        SessionCostResponse with usage statistics

    Raises:
        HTTPException: If cost data not found for session
    """
    usage = storage_svc.get_session_cost(session_id)
    if not usage:
        raise HTTPException(status_code=404, detail="Cost data not found for session")

    return SessionCostResponse(session_id=session_id, usage=usage)


@router.get("", response_model=GlobalCostResponse)
async def get_global_cost(
    storage_svc: StorageService = Depends(get_storage_service),
) -> GlobalCostResponse:
    """
    Get aggregated cost statistics across all sessions.

    Args:
        storage_svc: Injected storage service

    Returns:
        GlobalCostResponse with total costs and session count
    """
    return storage_svc.get_global_cost()
