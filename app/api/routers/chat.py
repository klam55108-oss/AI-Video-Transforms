"""
Chat router - handles chat session interactions.

Provides endpoints for session initialization, message processing,
session deletion, and status polling.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ValidatedSessionId, get_session_service, get_storage_service
from app.api.errors import handle_endpoint_error
from app.core.validators import UUID_PATTERN
from app.models.api import (
    AgentStatus,
    ChatResponse,
    StatusResponse,
    UsageStats,
)
from app.models.requests import ChatRequest, InitRequest
from app.services import SessionService, StorageService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/init", response_model=ChatResponse)
async def chat_init(
    request: InitRequest,
    session_svc: SessionService = Depends(get_session_service),
    storage_svc: StorageService = Depends(get_storage_service),
) -> ChatResponse:
    """
    Initialize a chat session and return the greeting message.

    Args:
        request: Session initialization request with session_id
        session_svc: Injected session service
        storage_svc: Injected storage service

    Returns:
        ChatResponse with greeting message and usage stats
    """
    try:
        actor = await session_svc.get_or_create(request.session_id)
        response = await actor.get_greeting()

        # Save greeting to storage
        storage_svc.save_message(request.session_id, "agent", response.text)

        return ChatResponse(
            response=response.text,
            session_id=request.session_id,
            usage=UsageStats(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_creation_tokens=response.usage.cache_creation_tokens,
                cache_read_tokens=response.usage.cache_read_tokens,
                total_cost_usd=response.usage.cost_usd,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise handle_endpoint_error(e, f"chat_init session={request.session_id[:8]}...")


@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    session_svc: SessionService = Depends(get_session_service),
    storage_svc: StorageService = Depends(get_storage_service),
) -> ChatResponse:
    """
    Process a chat message and return the response.

    Args:
        request: Chat request with session_id and message
        session_svc: Injected session service
        storage_svc: Injected storage service

    Returns:
        ChatResponse with agent response and usage stats
    """
    try:
        actor = await session_svc.get_or_create(request.session_id)

        # Save user message to storage
        storage_svc.save_message(request.session_id, "user", request.message)

        # Send message to actor and await response
        response = await actor.process_message(request.message)

        # Save agent response to storage
        storage_svc.save_message(request.session_id, "agent", response.text)

        return ChatResponse(
            response=response.text,
            session_id=request.session_id,
            usage=UsageStats(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_creation_tokens=response.usage.cache_creation_tokens,
                cache_read_tokens=response.usage.cache_read_tokens,
                total_cost_usd=response.usage.cost_usd,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise handle_endpoint_error(e, f"chat session={request.session_id[:8]}...")


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    session_svc: SessionService = Depends(get_session_service),
) -> dict[str, str]:
    """
    Delete a chat session.

    Args:
        session_id: UUID of the session to delete
        session_svc: Injected session service

    Returns:
        Success status message
    """
    # Validate session ID format
    if not UUID_PATTERN.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    success = await session_svc.close_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "success", "message": f"Session {session_id} closed"}


# Health check endpoint for Docker/k8s
health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint for monitoring and orchestration.

    Returns:
        Simple status response indicating service is running
    """
    return {"status": "ok"}


# Status endpoint is at /status/{session_id}, not under /chat
status_router = APIRouter(tags=["chat"])


@status_router.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(
    session_id: str = Depends(ValidatedSessionId()),
    session_svc: SessionService = Depends(get_session_service),
) -> StatusResponse:
    """
    Get current status of a session's agent.

    Args:
        session_id: UUID of the session (validated)
        session_svc: Injected session service

    Returns:
        StatusResponse with current session status
    """
    from app.models.service import SessionStatus

    status = session_svc.get_status(session_id)

    # Map service status to API status
    status_map = {
        SessionStatus.INITIALIZING: AgentStatus.INITIALIZING,
        SessionStatus.READY: AgentStatus.READY,
        SessionStatus.PROCESSING: AgentStatus.PROCESSING,
        SessionStatus.ERROR: AgentStatus.ERROR,
        SessionStatus.CLOSED: AgentStatus.INITIALIZING,  # Not yet initialized
    }

    api_status = status_map.get(status, AgentStatus.ERROR)

    message = None
    if status == SessionStatus.CLOSED:
        message = "Session not yet initialized"
    elif status == SessionStatus.ERROR:
        message = "Session worker stopped"

    return StatusResponse(
        status=api_status,
        session_id=session_id,
        message=message,
    )
