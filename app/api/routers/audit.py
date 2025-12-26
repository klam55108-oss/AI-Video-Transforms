"""
Audit router - handles audit log retrieval and statistics.

Provides endpoints for viewing agent tool usage, session lifecycle events,
and aggregate audit statistics captured by SDK hooks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_audit_service, validate_uuid
from app.models.audit import AuditEventType, AuditLogResponse, AuditStats
from app.services import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/stats")
async def get_audit_stats(
    audit_svc: AuditService = Depends(get_audit_service),
) -> AuditStats:
    """
    Get aggregate audit statistics.

    Returns high-level metrics for monitoring agent activity:
    - Total events captured
    - Tools invoked, blocked, succeeded, and failed
    - Session and subagent stop counts
    - Average tool duration

    Returns:
        AuditStats with aggregate metrics
    """
    return await audit_svc.get_stats()


@router.get("/sessions")
async def list_audit_sessions(
    limit: int = Query(50, ge=1, le=200, description="Max sessions to return"),
    audit_svc: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """
    List sessions that have audit logs.

    Returns sessions with audit events, sorted by most recently active.
    Useful for finding sessions to inspect.

    Args:
        limit: Maximum number of sessions to return
        audit_svc: Injected audit service

    Returns:
        List of session info with event counts
    """
    sessions = await audit_svc.list_sessions_with_audits(limit=limit)
    return {
        "sessions": sessions,
        "total": len(sessions),
    }


@router.get("/sessions/{session_id}")
async def get_session_audit_log(
    session_id: str,
    limit: int = Query(100, ge=1, le=500, description="Max entries to return"),
    offset: int = Query(0, ge=0, description="Entries to skip"),
    event_type: str | None = Query(
        None,
        description="Filter by event type",
        enum=[e.value for e in AuditEventType],
    ),
    audit_svc: AuditService = Depends(get_audit_service),
) -> AuditLogResponse:
    """
    Get audit log for a specific session.

    Returns detailed audit events for a session with pagination and
    optional filtering by event type. Events are ordered newest first.

    Args:
        session_id: UUID of the session
        limit: Maximum entries to return
        offset: Number of entries to skip (for pagination)
        event_type: Optional event type filter
        audit_svc: Injected audit service

    Returns:
        AuditLogResponse with paginated entries
    """
    # Validate session ID format
    validate_uuid(session_id, "session ID")

    return await audit_svc.get_session_audit_log(
        session_id=session_id,
        limit=limit,
        offset=offset,
        event_type=event_type,
    )


@router.post("/cleanup")
async def cleanup_old_logs(
    audit_svc: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """
    Manually trigger cleanup of old audit logs.

    Removes audit logs older than the retention period (default 7 days).
    This is also done automatically during scheduled cleanups.

    Security Note:
        This endpoint is unauthenticated. In production deployments with
        multi-user access, consider adding authentication/authorization
        (e.g., admin-only access via a dependency like `Depends(require_admin)`).
        For single-user local deployments, this is acceptable.

    Returns:
        Number of sessions cleaned up
    """
    cleaned = await audit_svc.cleanup_old_logs()
    return {
        "success": True,
        "sessions_cleaned": cleaned,
        "message": f"Cleaned up {cleaned} old audit sessions",
    }
