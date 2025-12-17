"""
Job Queue Service - Manages asynchronous job processing.

Provides in-memory job queue with concurrent processing, progress tracking,
and graceful lifecycle management. Follows the actor pattern to avoid
SessionActor concurrency issues.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.models.jobs import Job, JobStage, JobStatus, JobType

logger = logging.getLogger(__name__)


class JobQueueService:
    """
    In-memory job queue with background processing.

    Manages job lifecycle with:
    - Thread-safe job storage
    - Concurrent job execution (configurable limit)
    - Progress tracking and status updates
    - Graceful cancellation and cleanup
    """

    def __init__(self) -> None:
        """Initialize job queue with empty storage and processing state."""
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._jobs_lock = asyncio.Lock()
        self._pending_queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing_semaphore = asyncio.Semaphore(
            get_settings().job_max_concurrent
        )
        self._processor_tasks: list[asyncio.Task[None]] = []
        self._shutdown_event = asyncio.Event()

    async def create_job(
        self,
        job_type: JobType,
        metadata: dict[str, Any] | None = None,
    ) -> Job:
        """
        Create a new job and add to processing queue.

        Args:
            job_type: Type of job to create
            metadata: Optional job-specific metadata

        Returns:
            Created Job instance
        """
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            type=job_type,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
            metadata=metadata or {},
        )

        async with self._jobs_lock:
            self._jobs[job_id] = job

        # Queue for processing
        await self._pending_queue.put(job_id)

        logger.info(f"Created {job_type.value} job: {job_id}")
        return job

    async def get_job(self, job_id: str) -> Job | None:
        """
        Retrieve a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job instance or None if not found
        """
        async with self._jobs_lock:
            return self._jobs.get(job_id)

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
    ) -> list[Job]:
        """
        List jobs with optional filtering.

        Args:
            status: Filter by job status
            job_type: Filter by job type

        Returns:
            List of matching jobs (newest first)
        """
        async with self._jobs_lock:
            jobs = list(self._jobs.values())

        # Apply filters
        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.type == job_type]

        # Return newest first
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or running job.

        Args:
            job_id: Job identifier

        Returns:
            True if job was cancelled, False if not found or already completed
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                # Already finished
                return False

            # Mark as failed with cancellation message
            job.status = JobStatus.FAILED
            job.error = "Cancelled by user"
            job.completed_at = datetime.utcnow()

        logger.info(f"Cancelled job: {job_id}")
        return True

    async def update_progress(
        self,
        job_id: str,
        stage: JobStage,
        progress: int,
    ) -> None:
        """
        Update job progress and stage.

        Args:
            job_id: Job identifier
            stage: Current processing stage
            progress: Progress percentage (0-100)
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job:
                job.stage = stage
                job.progress = min(100, max(0, progress))

    async def _process_job(self, job_id: str) -> None:
        """
        Process a single job.

        This is a placeholder implementation. Phase 3 will integrate
        actual transcription, bootstrap, and extraction logic.

        Args:
            job_id: Job identifier
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()

        logger.info(f"Processing job {job_id} ({job.type.value})")

        try:
            # Placeholder processing stages
            stages = [
                (JobStage.QUEUED, 0),
                (JobStage.PROCESSING, 25),
                (JobStage.PROCESSING, 50),
                (JobStage.PROCESSING, 75),
                (JobStage.FINALIZING, 90),
            ]

            for stage, progress in stages:
                await self.update_progress(job_id, stage, progress)
                await asyncio.sleep(0.5)  # Simulate work

            # Mark as completed
            async with self._jobs_lock:
                if job_id in self._jobs:
                    job = self._jobs[job_id]
                    job.status = JobStatus.COMPLETED
                    job.progress = 100
                    job.completed_at = datetime.utcnow()
                    job.result = {"status": "success", "message": "Job completed"}

            logger.info(f"Completed job {job_id}")

        except asyncio.CancelledError:
            logger.info(f"Job {job_id} cancelled during processing")
            async with self._jobs_lock:
                if job_id in self._jobs:
                    job = self._jobs[job_id]
                    job.status = JobStatus.FAILED
                    job.error = "Processing cancelled"
                    job.completed_at = datetime.utcnow()
            raise

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            async with self._jobs_lock:
                if job_id in self._jobs:
                    job = self._jobs[job_id]
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.completed_at = datetime.utcnow()

    async def _job_processor_worker(self) -> None:
        """
        Worker coroutine that processes jobs from the queue.

        Runs continuously until shutdown, respecting concurrency limits.
        """
        logger.info("Job processor worker started")

        try:
            while not self._shutdown_event.is_set():
                try:
                    # Get next job with timeout to allow shutdown checks
                    job_id = await asyncio.wait_for(
                        self._pending_queue.get(), timeout=1.0
                    )

                    # Check shutdown before processing
                    if self._shutdown_event.is_set():
                        break

                    # Acquire semaphore to respect concurrency limit
                    async with self._processing_semaphore:
                        await self._process_job(job_id)

                except asyncio.TimeoutError:
                    # No jobs in queue, continue loop
                    continue

        except asyncio.CancelledError:
            logger.info("Job processor worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Job processor worker error: {e}", exc_info=True)

    async def run_job_processor_loop(self, num_workers: int = 2) -> None:
        """
        Start background job processing workers.

        Creates multiple worker tasks to process jobs concurrently
        up to the configured limit.

        Args:
            num_workers: Number of worker tasks to create
        """
        logger.info(f"Starting {num_workers} job processor workers")

        try:
            # Create worker tasks
            self._processor_tasks = [
                asyncio.create_task(self._job_processor_worker())
                for _ in range(num_workers)
            ]

            # Wait for all workers to complete (happens on shutdown)
            await asyncio.gather(*self._processor_tasks, return_exceptions=True)

        except asyncio.CancelledError:
            logger.info("Job processor loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Job processor loop error: {e}", exc_info=True)

    async def shutdown(self) -> None:
        """
        Gracefully shutdown job processing.

        Stops accepting new jobs, cancels pending jobs, and waits
        for running jobs to complete.
        """
        logger.info("Shutting down job queue service")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel all processor tasks
        for task in self._processor_tasks:
            task.cancel()

        # Wait for tasks to finish (with timeout)
        if self._processor_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._processor_tasks, return_exceptions=True),
                    timeout=get_settings().graceful_shutdown_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Job processor tasks did not shutdown gracefully")

        # Mark all pending jobs as failed
        async with self._jobs_lock:
            for job in self._jobs.values():
                if job.status == JobStatus.PENDING:
                    job.status = JobStatus.FAILED
                    job.error = "Server shutdown"
                    job.completed_at = datetime.utcnow()

        logger.info("Job queue service shutdown complete")

    def get_queue_size(self) -> int:
        """
        Get number of pending jobs in queue.

        Returns:
            Number of jobs awaiting processing
        """
        return self._pending_queue.qsize()

    def get_job_count(self) -> int:
        """
        Get total number of tracked jobs.

        Returns:
            Total job count
        """
        return len(self._jobs)
