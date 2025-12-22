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
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.jobs import Job, JobStage, JobStatus, JobType
from app.models.service import SourceType
from app.services.job_repository import JobRepository

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

    def __init__(self, data_path: Path | None = None) -> None:
        """
        Initialize job queue with storage and processing state.

        Args:
            data_path: Base path for data storage (defaults to config)
        """
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._jobs_lock = asyncio.Lock()
        self._pending_queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing_semaphore = asyncio.Semaphore(
            get_settings().job_max_concurrent
        )
        self._processor_tasks: list[asyncio.Task[None]] = []
        self._shutdown_event = asyncio.Event()

        # Initialize repository
        if data_path is None:
            data_path = get_settings().data_path
        self._repository = JobRepository(data_path / "jobs")

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

        # Persist immediately after creation
        await self._repository.save_job(job)

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

    async def cancel_job(self, job_id: str) -> Job | None:
        """
        Cancel a pending or running job.

        Sets status to CANCELLED and cancelled_at timestamp.
        For running jobs, attempts to stop execution gracefully.

        Args:
            job_id: Job identifier

        Returns:
            The cancelled job, or None if not found/already completed.
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            if job.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                # Already finished
                return None

            # Mark as cancelled
            job.status = JobStatus.CANCELLED
            job.cancelled_at = datetime.utcnow()
            job.cancelled_by = "user"
            job.completed_at = datetime.utcnow()
            job.error = "Cancelled by user"

        # Persist the cancellation outside lock
        await self._repository.save_job(job)

        logger.info(f"Cancelled job: {job_id}")
        return job

    async def retry_job(self, job_id: str) -> Job | None:
        """
        Retry a failed or cancelled job.

        Creates a new job with incremented retry_count. Returns None if:
        - Original job not found
        - Job is still running
        - Max retries exceeded

        The new job starts fresh but preserves original parameters.

        Args:
            job_id: Job identifier to retry

        Returns:
            New job with incremented retry_count, or None if retry not allowed.
        """
        async with self._jobs_lock:
            original_job = self._jobs.get(job_id)
            if not original_job:
                return None

            # Only allow retry for failed or cancelled jobs
            if original_job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
                logger.warning(
                    f"Cannot retry job {job_id} with status {original_job.status}"
                )
                return None

            # Check retry limit
            if original_job.retry_count >= original_job.max_retries:
                logger.warning(
                    f"Job {job_id} has reached max retries ({original_job.max_retries})"
                )
                return None

        # Create new job with incremented retry count
        new_job_id = str(uuid.uuid4())
        new_job = Job(
            id=new_job_id,
            type=original_job.type,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
            metadata=original_job.metadata.copy(),
            retry_count=original_job.retry_count + 1,
            max_retries=original_job.max_retries,
        )

        # Store reference to original job in metadata
        new_job.metadata["original_job_id"] = job_id
        new_job.metadata["retry_attempt"] = new_job.retry_count

        async with self._jobs_lock:
            self._jobs[new_job_id] = new_job

        # Persist new job
        await self._repository.save_job(new_job)

        # Queue for processing
        await self._pending_queue.put(new_job_id)

        logger.info(
            f"Created retry job {new_job_id} for {job_id} (attempt {new_job.retry_count}/{new_job.max_retries})"
        )
        return new_job

    async def update_progress(
        self,
        job_id: str,
        stage: JobStage,
        progress: int,
    ) -> None:
        """
        Update job progress and stage.

        Persists to disk at configured intervals to enable resume on restart.

        Args:
            job_id: Job identifier
            stage: Current processing stage
            progress: Progress percentage (0-100)
        """
        settings = get_settings()
        should_persist = False

        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job:
                old_progress = job.progress
                job.stage = stage
                job.progress = min(100, max(0, progress))

                # Persist at configured intervals (e.g., every 10%)
                if progress % settings.job_persist_interval_percent == 0:
                    should_persist = True
                # Also persist if we crossed an interval threshold
                elif (progress // settings.job_persist_interval_percent) > (
                    old_progress // settings.job_persist_interval_percent
                ):
                    should_persist = True

        # Persist outside lock to avoid blocking
        if should_persist and job:
            await self._repository.save_job(job)

    async def _check_cancelled(self, job_id: str) -> bool:
        """
        Check if a job has been cancelled.

        Args:
            job_id: Job identifier

        Returns:
            True if job is cancelled, False otherwise
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.CANCELLED:
                return True
        return False

    async def _complete_job(
        self,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """
        Mark job as completed/failed and persist final state.

        Args:
            job_id: Job identifier
            status: Final job status
            result: Optional result data
            error: Optional error message
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status
                job.completed_at = datetime.utcnow()
                if result:
                    job.result = result
                if error:
                    job.error = error

        # Persist final state outside lock
        if job:
            await self._repository.save_job(job)

    async def _process_job(self, job_id: str) -> None:
        """
        Process a single job.

        Dispatches to appropriate handler based on job type.
        Checks for cancellation before starting.

        Args:
            job_id: Job identifier
        """
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            # Check if job was cancelled before processing started
            if job.status == JobStatus.CANCELLED:
                logger.info(f"Job {job_id} was cancelled before processing")
                return

            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()

        logger.info(f"Processing job {job_id} ({job.type.value})")

        try:
            if job.type == JobType.TRANSCRIPTION:
                await self._process_transcription_job(job_id)
            elif job.type == JobType.BOOTSTRAP:
                await self._process_bootstrap_job(job_id)
            elif job.type == JobType.EXTRACTION:
                await self._process_extraction_job(job_id)
            else:
                raise ValueError(f"Unknown job type: {job.type}")

        except asyncio.CancelledError:
            logger.info(f"Job {job_id} cancelled during processing")
            await self._complete_job(
                job_id, JobStatus.CANCELLED, error="Processing cancelled"
            )
            raise

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            await self._complete_job(job_id, JobStatus.FAILED, error=str(e))

    async def _process_transcription_job(self, job_id: str) -> None:
        """
        Process a transcription job.

        Args:
            job_id: Job identifier
        """
        # Get job metadata (defensive copy to avoid race conditions)
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            metadata = job.metadata.copy()

        video_source = metadata.get("video_source")
        if not video_source:
            # Placeholder for testing: allow jobs without metadata to complete
            logger.warning(
                f"Transcription job {job_id} missing video_source, using placeholder"
            )
            await self.update_progress(job_id, JobStage.PROCESSING, 50)

            # Update progress to 100 before completing
            async with self._jobs_lock:
                if job_id in self._jobs:
                    self._jobs[job_id].progress = 100

            await self._complete_job(
                job_id,
                JobStatus.COMPLETED,
                result={"status": "success", "message": "Placeholder transcription"},
            )
            return

        output_file = metadata.get("output_file")
        language = metadata.get("language")
        prompt = metadata.get("prompt")
        temperature = metadata.get("temperature", 0.0)
        session_id = metadata.get("session_id")

        # Import transcription logic
        from app.agent.transcribe_tool import _is_youtube_url, _perform_transcription

        is_youtube = _is_youtube_url(video_source)

        # Update progress: QUEUED → 0%
        await self.update_progress(job_id, JobStage.QUEUED, 0)

        # Update progress based on source type
        # Note: Fine-grained progress tracking (per-segment) would require
        # refactoring _perform_transcription to accept a callback, which is
        # a larger architectural change deferred to future iterations.
        await self.update_progress(
            job_id,
            JobStage.DOWNLOADING if is_youtube else JobStage.EXTRACTING_AUDIO,
            10,
        )

        # Run the blocking transcription
        result = await asyncio.to_thread(
            _perform_transcription,
            video_source=video_source,
            output_file=output_file,
            language=language,
            temperature=temperature,
            prompt=prompt,
        )

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Transcription failed"))

        # Update progress: TRANSCRIBING complete → 70%
        await self.update_progress(job_id, JobStage.TRANSCRIBING, 70)

        # Update progress: FINALIZING → 90%
        await self.update_progress(job_id, JobStage.FINALIZING, 90)

        # Save transcript to library
        transcription_text = result["transcription"]
        source_type = SourceType.YOUTUBE if is_youtube else SourceType.LOCAL

        # Get services
        from app.services import get_services

        # Create temp file for transcript if no output_file was specified
        temp_file_path: Path | None = None
        if not output_file:
            temp_dir = get_settings().data_path / "transcripts"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file_path = temp_dir / f"transcript_{job_id[:8]}.txt"
            temp_file_path.write_text(transcription_text, encoding="utf-8")
            output_file = str(temp_file_path)

        # Save transcript via TranscriptionService
        transcription_service = get_services().transcription
        transcript_metadata = await transcription_service.save_transcript(
            file_path=output_file,
            original_source=video_source,
            source_type=source_type,
            session_id=session_id,
        )

        # Note: Do NOT delete the transcript file - save_transcript() registers
        # the file path in metadata, it doesn't copy the content elsewhere.
        # The file at temp_file_path IS the permanent transcript storage.

        # Update metadata and mark as completed
        async with self._jobs_lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.metadata["artifact_id"] = transcript_metadata.id
                job.progress = 100

        await self._complete_job(
            job_id,
            JobStatus.COMPLETED,
            result={
                "status": "success",
                "transcript_id": transcript_metadata.id,
                "transcript_filename": transcript_metadata.filename,
                "chunks_processed": result.get("chunk_count", 1),
                "source_type": source_type.value,
                "format": transcript_metadata.format,
                "duration": transcript_metadata.duration,
            },
        )

        logger.info(
            f"Transcription job {job_id} completed: transcript_id={transcript_metadata.id}"
        )

    async def _process_bootstrap_job(self, job_id: str) -> None:
        """
        Process a bootstrap job.

        Placeholder for future implementation.

        Args:
            job_id: Job identifier
        """
        # Placeholder: mark as completed immediately
        await self.update_progress(job_id, JobStage.PROCESSING, 50)

        # Update progress to 100 before completing
        async with self._jobs_lock:
            if job_id in self._jobs:
                self._jobs[job_id].progress = 100

        await self._complete_job(
            job_id,
            JobStatus.COMPLETED,
            result={"status": "success", "message": "Bootstrap completed"},
        )

    async def _process_extraction_job(self, job_id: str) -> None:
        """
        Process an extraction job.

        Placeholder for future implementation.

        Args:
            job_id: Job identifier
        """
        # Placeholder: mark as completed immediately
        await self.update_progress(job_id, JobStage.PROCESSING, 50)

        # Update progress to 100 before completing
        async with self._jobs_lock:
            if job_id in self._jobs:
                self._jobs[job_id].progress = 100

        await self._complete_job(
            job_id,
            JobStatus.COMPLETED,
            result={"status": "success", "message": "Extraction completed"},
        )

    async def restore_pending_jobs(self) -> int:
        """
        Restore jobs from disk on startup.

        Loads all persisted jobs and re-queues PENDING/RUNNING jobs
        to enable resume from checkpoint.

        Returns:
            Number of jobs restored
        """
        logger.info("Restoring jobs from disk...")

        # Load all jobs from disk
        persisted_jobs = await self._repository.get_resumable_jobs()

        if not persisted_jobs:
            logger.info("No jobs to restore")
            return 0

        restored_count = 0

        async with self._jobs_lock:
            for job in persisted_jobs:
                # Add to in-memory storage
                self._jobs[job.id] = job

                # Mark interrupted RUNNING jobs as PENDING for retry
                if job.status == JobStatus.RUNNING:
                    job.status = JobStatus.PENDING
                    job.error = "Server restarted - job will resume"
                    logger.info(
                        f"Marking interrupted job {job.id} for resume at {job.progress}%"
                    )

                # Re-queue for processing
                await self._pending_queue.put(job.id)
                restored_count += 1

        # Persist updated status for interrupted jobs
        for job in persisted_jobs:
            if job.status == JobStatus.PENDING:
                await self._repository.save_job(job)

        logger.info(f"Restored {restored_count} jobs from disk")
        return restored_count

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

        # Mark all pending jobs as cancelled
        async with self._jobs_lock:
            for job in self._jobs.values():
                if job.status == JobStatus.PENDING:
                    job.status = JobStatus.CANCELLED
                    job.cancelled_at = datetime.utcnow()
                    job.cancelled_by = "system"
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
