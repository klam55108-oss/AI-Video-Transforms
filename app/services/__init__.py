"""
Service Container and Lifecycle Management.

Provides a centralized container for all service instances with proper
startup/shutdown lifecycle management for FastAPI integration.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.services.audit_service import AuditService
from app.services.job_queue_service import JobQueueService
from app.services.kg_service import KnowledgeGraphService
from app.services.session_service import SessionService
from app.services.storage_service import StorageService
from app.services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Dependency injection container for all services.

    Manages service lifecycle with startup/shutdown hooks for proper
    resource management in FastAPI applications.
    """

    def __init__(self) -> None:
        """Initialize container with empty service references."""
        self._storage: StorageService | None = None
        self._session: SessionService | None = None
        self._transcription: TranscriptionService | None = None
        self._kg: KnowledgeGraphService | None = None
        self._job_queue: JobQueueService | None = None
        self._audit: AuditService | None = None
        self._cleanup_task: asyncio.Task[None] | None = None
        self._job_processor_task: asyncio.Task[None] | None = None

    @property
    def storage(self) -> StorageService:
        """Get storage service instance."""
        if self._storage is None:
            raise RuntimeError(
                "ServiceContainer not initialized - call startup() first"
            )
        return self._storage

    @property
    def session(self) -> SessionService:
        """Get session service instance."""
        if self._session is None:
            raise RuntimeError(
                "ServiceContainer not initialized - call startup() first"
            )
        return self._session

    @property
    def transcription(self) -> TranscriptionService:
        """Get transcription service instance."""
        if self._transcription is None:
            raise RuntimeError(
                "ServiceContainer not initialized - call startup() first"
            )
        return self._transcription

    @property
    def kg(self) -> KnowledgeGraphService:
        """Get knowledge graph service instance."""
        if self._kg is None:
            raise RuntimeError(
                "ServiceContainer not initialized - call startup() first"
            )
        return self._kg

    @property
    def job_queue(self) -> JobQueueService:
        """Get job queue service instance."""
        if self._job_queue is None:
            raise RuntimeError(
                "ServiceContainer not initialized - call startup() first"
            )
        return self._job_queue

    @property
    def audit(self) -> AuditService:
        """Get audit service instance."""
        if self._audit is None:
            raise RuntimeError(
                "ServiceContainer not initialized - call startup() first"
            )
        return self._audit

    async def startup(self) -> None:
        """
        Initialize all services and start background tasks.

        Creates service instances in dependency order and starts the
        session cleanup loop as a background task.
        """
        from pathlib import Path

        logger.info("Starting service container")

        # Initialize services in dependency order
        self._storage = StorageService()
        self._audit = AuditService(data_path=Path("data"))
        self._session = SessionService(audit_service=self._audit)
        self._transcription = TranscriptionService(self._storage)
        self._kg = KnowledgeGraphService(
            data_path=Path("data"), audit_service=self._audit
        )
        self._job_queue = JobQueueService()

        # Restore persisted jobs before starting background tasks
        restored_count = await self._job_queue.restore_pending_jobs()
        if restored_count > 0:
            logger.info(f"Restored {restored_count} pending jobs from disk")

        # Start background tasks
        self._cleanup_task = asyncio.create_task(self._session.run_cleanup_loop())
        self._job_processor_task = asyncio.create_task(
            self._job_queue.run_job_processor_loop(num_workers=2)
        )

        logger.info("Service container started")

    async def shutdown(self) -> None:
        """
        Gracefully shutdown all services.

        Stops background tasks and closes all active sessions before
        cleaning up service references.
        """
        logger.info("Shutting down service container")

        # Shutdown job queue
        if self._job_queue:
            await self._job_queue.shutdown()

        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._job_processor_task:
            self._job_processor_task.cancel()
            try:
                await self._job_processor_task
            except asyncio.CancelledError:
                pass

        # Close all sessions
        if self._session:
            await self._session.close_all_sessions()

        # Clear service references
        self._storage = None
        self._session = None
        self._transcription = None
        self._kg = None
        self._job_queue = None
        self._audit = None

        logger.info("Service container shutdown complete")


# Global service container instance
_services: ServiceContainer | None = None


def get_services() -> ServiceContainer:
    """
    Get the global service container instance.

    Returns:
        Global ServiceContainer singleton

    Raises:
        RuntimeError: If container hasn't been initialized
    """
    if _services is None:
        raise RuntimeError(
            "Services not initialized - ensure services_lifespan() is used"
        )
    return _services


@asynccontextmanager
async def services_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan context manager for service initialization.

    Manages service container startup and shutdown during FastAPI
    application lifecycle. Use with app.router.lifespan_context.

    Example:
        app = FastAPI()
        app.router.lifespan_context = services_lifespan

    Args:
        app: FastAPI application instance

    Yields:
        None (context manager pattern)
    """
    global _services

    # Startup
    _services = ServiceContainer()
    await _services.startup()
    logger.info("FastAPI services initialized")

    try:
        yield
    finally:
        # Shutdown
        if _services:
            await _services.shutdown()
        _services = None
        logger.info("FastAPI services cleaned up")


__all__ = [
    "ServiceContainer",
    "get_services",
    "services_lifespan",
    "AuditService",
    "JobQueueService",
    "KnowledgeGraphService",
    "SessionService",
    "StorageService",
    "TranscriptionService",
]
