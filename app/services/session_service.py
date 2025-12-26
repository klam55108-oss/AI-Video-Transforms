"""
Session Service - Manages SessionActor lifecycle.

Wraps the SessionActor pattern with service-level orchestration including:
- Session creation and retrieval
- Status management
- Cleanup of expired sessions
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from app.core.session import (
    CLEANUP_INTERVAL_SECONDS,
    SESSION_TTL_SECONDS,
    SessionActor,
)
from app.models.service import ServiceUnavailableError, SessionStatus

if TYPE_CHECKING:
    from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service layer for session management.

    Manages the lifecycle of SessionActor instances, including creation,
    retrieval, status tracking, and cleanup. Preserves the actor pattern
    by wrapping (not replacing) the existing implementation.
    """

    def __init__(self, audit_service: AuditService | None = None) -> None:
        """Initialize session service with empty session registry.

        Args:
            audit_service: Optional AuditService for hook-based audit logging.
                If provided, enables SDK hooks for tool usage tracking.
        """
        self._active_sessions: dict[str, SessionActor] = {}
        self._sessions_lock = asyncio.Lock()
        self._audit_service = audit_service

    async def get_or_create(self, session_id: str) -> SessionActor:
        """
        Retrieve an existing session or create a new actor.

        Uses double-checked locking pattern to minimize lock contention:
        1. First check with lock to see if session exists
        2. If not, create and start actor outside lock (slow operation)
        3. Re-acquire lock to add to dict, handling race if another created it

        Args:
            session_id: UUID of the session

        Returns:
            Running SessionActor instance

        Raises:
            ServiceUnavailableError: If ANTHROPIC_API_KEY is not configured
        """
        # First check: see if session already exists
        async with self._sessions_lock:
            if session_id in self._active_sessions:
                actor = self._active_sessions[session_id]
                if actor.is_running:
                    return actor
                else:
                    # Clean up dead session
                    del self._active_sessions[session_id]
                    logger.warning(f"Cleaned up dead session: {session_id}")

        # Create and start new actor outside the lock (slow operation)
        logger.info(f"Initializing new session actor: {session_id}")

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ServiceUnavailableError("ANTHROPIC_API_KEY not configured")

        new_actor = SessionActor(session_id, audit_service=self._audit_service)
        await new_actor.start()

        # Second check: add to dict, handling race condition
        async with self._sessions_lock:
            if session_id in self._active_sessions:
                # Another request created the session while we were starting
                existing = self._active_sessions[session_id]
                if existing.is_running:
                    # Stop our actor and use theirs
                    await new_actor.stop()
                    logger.info(
                        f"Session {session_id[:8]} created by another request, reusing"
                    )
                    return existing
                else:
                    # Existing one died, use ours
                    del self._active_sessions[session_id]

            self._active_sessions[session_id] = new_actor
            return new_actor

    def get_actor(self, session_id: str) -> SessionActor | None:
        """
        Get existing actor for a session (does not create new one).

        Used for activity streaming where we need direct access to the
        actor without triggering creation.

        Args:
            session_id: UUID of the session

        Returns:
            SessionActor if exists and running, None otherwise
        """
        actor = self._active_sessions.get(session_id)
        if actor and actor.is_running:
            return actor
        return None

    def get_status(self, session_id: str) -> SessionStatus:
        """
        Get current status of a session.

        Args:
            session_id: UUID of the session

        Returns:
            SessionStatus enum value
        """
        if session_id not in self._active_sessions:
            return SessionStatus.CLOSED

        actor = self._active_sessions[session_id]

        if not actor.is_running:
            return SessionStatus.CLOSED

        if actor.is_processing:
            return SessionStatus.PROCESSING

        # Check if greeting has been sent (session is ready)
        if actor.greeting_queue.empty():
            return SessionStatus.READY
        else:
            return SessionStatus.INITIALIZING

    async def close_session(self, session_id: str) -> bool:
        """
        Close a specific session.

        Args:
            session_id: UUID of the session

        Returns:
            True if session was closed, False if not found
        """
        async with self._sessions_lock:
            if session_id not in self._active_sessions:
                return False

            actor = self._active_sessions.pop(session_id)

        # Stop actor outside lock to avoid blocking
        await actor.stop()
        logger.info(f"Closed session: {session_id}")
        return True

    async def close_all_sessions(self) -> None:
        """
        Close all active sessions gracefully.

        Used during service shutdown to clean up resources.
        """
        # Collect all actors while holding lock
        async with self._sessions_lock:
            actors_to_stop = list(self._active_sessions.values())
            self._active_sessions.clear()

        # Stop all actors concurrently outside lock
        if actors_to_stop:
            logger.info(f"Closing {len(actors_to_stop)} active sessions")
            await asyncio.gather(
                *[actor.stop() for actor in actors_to_stop],
                return_exceptions=True,
            )

    async def run_cleanup_loop(self) -> None:
        """
        Periodically clean up expired sessions.

        Runs as a background task that checks for expired or dead sessions
        every CLEANUP_INTERVAL_SECONDS and stops them gracefully.
        """
        logger.info("Session cleanup loop started")

        try:
            while True:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

                # Collect expired sessions while holding lock
                actors_to_stop: list[SessionActor] = []
                async with self._sessions_lock:
                    expired_ids = [
                        sid
                        for sid, actor in self._active_sessions.items()
                        if actor.is_expired(SESSION_TTL_SECONDS) or not actor.is_running
                    ]
                    for sid in expired_ids:
                        logger.info(f"Cleaning up expired session: {sid}")
                        actors_to_stop.append(self._active_sessions.pop(sid))

                # Stop actors outside lock to avoid blocking
                for actor in actors_to_stop:
                    await actor.stop()

        except asyncio.CancelledError:
            logger.info("Session cleanup loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Session cleanup loop error: {e}", exc_info=True)

    def get_active_session_count(self) -> int:
        """
        Get count of currently active sessions.

        Returns:
            Number of active sessions
        """
        return len(self._active_sessions)

    def get_all_session_ids(self) -> list[str]:
        """
        Get list of all active session IDs.

        Returns:
            List of session ID strings
        """
        return list(self._active_sessions.keys())
