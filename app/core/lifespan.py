"""
Application lifespan management.

Handles startup and shutdown events for the FastAPI application,
including background task management and session cleanup.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.session import active_sessions, cleanup_expired_sessions, sessions_lock

logger = logging.getLogger(__name__)

# Background task reference for cleanup
_cleanup_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle with startup and shutdown events.

    Args:
        app: The FastAPI application instance

    Yields:
        None during application runtime
    """
    global _cleanup_task
    # Startup: begin background cleanup task
    _cleanup_task = asyncio.create_task(cleanup_expired_sessions())
    logger.info("Started session cleanup background task")

    yield

    # Shutdown: cancel cleanup and stop all sessions
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass

    # Gracefully stop all active sessions
    async with sessions_lock:
        actors = list(active_sessions.values())
        active_sessions.clear()

    for actor in actors:
        await actor.stop()
    logger.info("Shutdown complete: all sessions closed")
