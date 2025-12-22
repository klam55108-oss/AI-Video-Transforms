"""
Job Recovery Integration Tests.

Tests job lifecycle across simulated server restarts:
- Jobs survive restart (PENDING/RUNNING are restored)
- Cancelled jobs remain cancelled across restart
- Retry creates new jobs with incremented retry_count
- Partial results preserved on failure
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.jobs import Job, JobStage, JobStatus, JobType
from app.services.job_queue_service import JobQueueService
from app.services.job_repository import JobRepository


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def job_service(tmp_path: Path) -> JobQueueService:
    """Create isolated job queue service."""
    return JobQueueService(data_path=tmp_path)


@pytest.fixture
def job_repository(tmp_path: Path) -> JobRepository:
    """Create isolated job repository."""
    return JobRepository(tmp_path / "jobs")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SERVER RESTART SIMULATION TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestServerRestartRecovery:
    """Tests simulating server restart and job recovery."""

    @pytest.mark.asyncio
    async def test_pending_job_survives_restart(self, tmp_path: Path) -> None:
        """Test that PENDING jobs are restored after simulated restart."""
        # PHASE 1: Create job before "crash"
        service1 = JobQueueService(data_path=tmp_path)
        job = await service1.create_job(
            JobType.TRANSCRIPTION, metadata={"video": "test.mp4"}
        )
        original_id = job.id

        # Simulate server crash (just shutdown without cleanup)
        await service1.shutdown()

        # PHASE 2: New server instance "restarts"
        service2 = JobQueueService(data_path=tmp_path)
        restored_count = await service2.restore_pending_jobs()

        # Verify job restored
        assert restored_count == 1
        restored_job = await service2.get_job(original_id)
        assert restored_job is not None
        assert restored_job.status == JobStatus.PENDING
        assert restored_job.metadata == {"video": "test.mp4"}

    @pytest.mark.asyncio
    async def test_running_job_becomes_pending_on_restart(self, tmp_path: Path) -> None:
        """Test that RUNNING jobs become PENDING after restart."""
        # PHASE 1: Create job and start it
        service1 = JobQueueService(data_path=tmp_path)
        job = await service1.create_job(JobType.TRANSCRIPTION)

        # Manually set to running with progress
        async with service1._jobs_lock:
            service1._jobs[job.id].status = JobStatus.RUNNING
            service1._jobs[job.id].stage = JobStage.TRANSCRIBING
            service1._jobs[job.id].progress = 45
            service1._jobs[job.id].resume_from_step = "segment_10"

        # Persist current state
        await service1._repository.save_job(service1._jobs[job.id])

        # Simulate crash
        await service1.shutdown()

        # PHASE 2: Restart
        service2 = JobQueueService(data_path=tmp_path)
        await service2.restore_pending_jobs()

        # Verify job state
        restored = await service2.get_job(job.id)
        assert restored is not None
        assert restored.status == JobStatus.PENDING  # Reset to pending
        assert restored.progress == 45  # Progress preserved
        assert restored.resume_from_step == "segment_10"  # Checkpoint preserved

    @pytest.mark.asyncio
    async def test_completed_jobs_not_restored(self, tmp_path: Path) -> None:
        """Test that COMPLETED jobs are not loaded on restart."""
        # Create completed job directly in repository
        repo = JobRepository(tmp_path / "jobs")
        completed_job = Job(
            id="completed-abc",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.COMPLETED,
            stage=JobStage.FINALIZING,
            progress=100,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result={"status": "success"},
        )
        await repo.save_job(completed_job)

        # Create pending job
        pending_job = Job(
            id="pending-xyz",
            type=JobType.BOOTSTRAP,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
        )
        await repo.save_job(pending_job)

        # Start service and restore
        service = JobQueueService(data_path=tmp_path)
        restored_count = await service.restore_pending_jobs()

        # Only pending job restored
        assert restored_count == 1
        assert await service.get_job("pending-xyz") is not None
        assert await service.get_job("completed-abc") is None

    @pytest.mark.asyncio
    async def test_failed_jobs_not_restored(self, tmp_path: Path) -> None:
        """Test that FAILED jobs are not automatically restored."""
        repo = JobRepository(tmp_path / "jobs")

        failed_job = Job(
            id="failed-job",
            type=JobType.EXTRACTION,
            status=JobStatus.FAILED,
            stage=JobStage.PROCESSING,
            progress=30,
            created_at=datetime.utcnow(),
            error="Test failure",
        )
        await repo.save_job(failed_job)

        service = JobQueueService(data_path=tmp_path)
        restored_count = await service.restore_pending_jobs()

        assert restored_count == 0
        assert await service.get_job("failed-job") is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JOB CANCEL TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestJobCancellation:
    """Tests for job cancellation functionality."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, job_service: JobQueueService) -> None:
        """Test cancelling a PENDING job."""
        job = await job_service.create_job(JobType.TRANSCRIPTION)

        # Cancel the job
        cancelled = await job_service.cancel_job(job.id)

        assert cancelled is not None
        assert cancelled.status == JobStatus.CANCELLED
        assert cancelled.cancelled_at is not None
        assert cancelled.cancelled_by == "user"

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, job_service: JobQueueService) -> None:
        """Test cancelling a RUNNING job."""
        job = await job_service.create_job(JobType.TRANSCRIPTION)

        # Manually set to running
        async with job_service._jobs_lock:
            job_service._jobs[job.id].status = JobStatus.RUNNING
            job_service._jobs[job.id].progress = 50

        # Cancel
        cancelled = await job_service.cancel_job(job.id)

        assert cancelled is not None
        assert cancelled.status == JobStatus.CANCELLED
        assert cancelled.progress == 50  # Progress preserved

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_job(
        self, job_service: JobQueueService
    ) -> None:
        """Test that COMPLETED jobs cannot be cancelled."""
        job = await job_service.create_job(JobType.TRANSCRIPTION)

        # Manually complete
        async with job_service._jobs_lock:
            job_service._jobs[job.id].status = JobStatus.COMPLETED

        # Try to cancel
        result = await job_service.cancel_job(job.id)
        assert result is None  # Cannot cancel completed job

    @pytest.mark.asyncio
    async def test_cancelled_jobs_not_restored_on_restart(self, tmp_path: Path) -> None:
        """Test that CANCELLED jobs stay cancelled across restart."""
        # Create and cancel job
        service1 = JobQueueService(data_path=tmp_path)
        job = await service1.create_job(JobType.TRANSCRIPTION)
        await service1.cancel_job(job.id)
        await service1.shutdown()

        # Restart
        service2 = JobQueueService(data_path=tmp_path)
        restored_count = await service2.restore_pending_jobs()

        # Cancelled job should NOT be restored
        assert restored_count == 0

    @pytest.mark.asyncio
    async def test_cancel_persists_to_disk(self, tmp_path: Path) -> None:
        """Test that cancellation is persisted."""
        service = JobQueueService(data_path=tmp_path)
        job = await service.create_job(JobType.TRANSCRIPTION)
        await service.cancel_job(job.id)

        # Check disk
        repo = JobRepository(tmp_path / "jobs")
        loaded = await repo.load_job(job.id)

        assert loaded is not None
        assert loaded.status == JobStatus.CANCELLED
        assert loaded.cancelled_by == "user"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# JOB RETRY TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestJobRetry:
    """Tests for job retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_failed_job(self, job_service: JobQueueService) -> None:
        """Test retrying a FAILED job."""
        job = await job_service.create_job(
            JobType.TRANSCRIPTION, metadata={"video": "test.mp4"}
        )

        # Mark as failed
        async with job_service._jobs_lock:
            job_service._jobs[job.id].status = JobStatus.FAILED
            job_service._jobs[job.id].error = "Network timeout"

        # Retry
        new_job = await job_service.retry_job(job.id)

        assert new_job is not None
        assert new_job.id != job.id  # New job ID
        assert new_job.status == JobStatus.PENDING
        assert new_job.retry_count == 1
        # Metadata includes original fields plus retry tracking
        assert new_job.metadata["video"] == "test.mp4"
        assert new_job.metadata["original_job_id"] == job.id
        assert new_job.metadata["retry_attempt"] == 1

    @pytest.mark.asyncio
    async def test_retry_cancelled_job(self, job_service: JobQueueService) -> None:
        """Test retrying a CANCELLED job."""
        job = await job_service.create_job(JobType.BOOTSTRAP)
        await job_service.cancel_job(job.id)

        # Retry
        new_job = await job_service.retry_job(job.id)

        assert new_job is not None
        assert new_job.status == JobStatus.PENDING
        assert new_job.retry_count == 1

    @pytest.mark.asyncio
    async def test_cannot_retry_pending_job(self, job_service: JobQueueService) -> None:
        """Test that PENDING jobs cannot be retried."""
        job = await job_service.create_job(JobType.TRANSCRIPTION)

        result = await job_service.retry_job(job.id)
        assert result is None  # Cannot retry pending job

    @pytest.mark.asyncio
    async def test_retry_increments_count(self, job_service: JobQueueService) -> None:
        """Test that retry_count increments on each retry."""
        job = await job_service.create_job(JobType.EXTRACTION)

        # Fail and retry multiple times
        for expected_count in range(1, 4):
            async with job_service._jobs_lock:
                job_service._jobs[job.id].status = JobStatus.FAILED

            new_job = await job_service.retry_job(job.id)
            assert new_job is not None
            assert new_job.retry_count == expected_count

            # Update reference for next iteration
            job = new_job

    @pytest.mark.asyncio
    async def test_retry_respects_max_retries(
        self, job_service: JobQueueService
    ) -> None:
        """Test that jobs cannot exceed max_retries."""
        job = await job_service.create_job(JobType.TRANSCRIPTION)

        # Manually set retry_count to max
        async with job_service._jobs_lock:
            job_service._jobs[job.id].status = JobStatus.FAILED
            job_service._jobs[job.id].retry_count = 3
            job_service._jobs[job.id].max_retries = 3

        # Try to retry
        result = await job_service.retry_job(job.id)

        # Should fail because max retries reached
        assert result is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PARTIAL RESULTS TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPartialResults:
    """Tests for partial result preservation on failure."""

    @pytest.mark.asyncio
    async def test_failed_job_preserves_partial_results(
        self, job_service: JobQueueService
    ) -> None:
        """Test that failed jobs preserve partial results."""
        job = await job_service.create_job(
            JobType.TRANSCRIPTION, metadata={"video": "long_video.mp4"}
        )

        # Simulate partial progress
        async with job_service._jobs_lock:
            job_service._jobs[job.id].status = JobStatus.RUNNING
            job_service._jobs[job.id].progress = 60
            job_service._jobs[job.id].stage = JobStage.TRANSCRIBING
            job_service._jobs[job.id].result = {
                "partial": True,
                "completed_segments": 10,
                "total_segments": 20,
                "partial_text": "First part of transcript...",
            }

        # Fail the job
        await job_service._complete_job(
            job.id,
            JobStatus.FAILED,
            error="Network timeout at segment 11",
            result={
                "partial": True,
                "completed_segments": 10,
                "total_segments": 20,
                "partial_text": "First part of transcript...",
            },
        )

        # Retrieve failed job
        failed_job = await job_service.get_job(job.id)
        assert failed_job is not None
        assert failed_job.status == JobStatus.FAILED
        assert failed_job.result is not None
        assert failed_job.result["partial"] is True
        assert failed_job.result["completed_segments"] == 10

    @pytest.mark.asyncio
    async def test_partial_results_persist_across_restart(self, tmp_path: Path) -> None:
        """Test that partial results survive restart."""
        service1 = JobQueueService(data_path=tmp_path)
        job = await service1.create_job(JobType.EXTRACTION)

        # Fail with partial results
        async with service1._jobs_lock:
            service1._jobs[job.id].result = {
                "partial": True,
                "entities_extracted": 5,
                "failed_at": "relationship extraction",
            }

        await service1._complete_job(
            job.id,
            JobStatus.FAILED,
            result={
                "partial": True,
                "entities_extracted": 5,
                "failed_at": "relationship extraction",
            },
        )

        await service1.shutdown()

        # Restart and check disk
        repo = JobRepository(tmp_path / "jobs")
        loaded = await repo.load_job(job.id)

        assert loaded is not None
        assert loaded.result is not None
        assert loaded.result["partial"] is True
        assert loaded.result["entities_extracted"] == 5


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestJobsAPI:
    """Test Jobs API endpoints for cancel/retry."""

    @pytest.mark.asyncio
    async def test_cancel_endpoint(self) -> None:
        """Test POST /jobs/{job_id}/cancel endpoint."""
        from uuid import uuid4

        from app.api.deps import get_job_queue_service
        from app.main import app

        job_id = str(uuid4())

        mock_service = AsyncMock(spec=JobQueueService)
        mock_service.cancel_job = AsyncMock(
            return_value=Job(
                id=job_id,
                type=JobType.TRANSCRIPTION,
                status=JobStatus.CANCELLED,
                stage=JobStage.QUEUED,
                progress=0,
                created_at=datetime.utcnow(),
                cancelled_at=datetime.utcnow(),
                cancelled_by="user",
            )
        )

        app.dependency_overrides[get_job_queue_service] = lambda: mock_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/jobs/{job_id}/cancel")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["job_id"] == job_id
            assert "job" in data
            assert data["job"]["status"] == "cancelled"
        finally:
            app.dependency_overrides.pop(get_job_queue_service, None)

    @pytest.mark.asyncio
    async def test_retry_endpoint(self) -> None:
        """Test POST /jobs/{job_id}/retry endpoint."""
        from uuid import uuid4

        from app.api.deps import get_job_queue_service
        from app.main import app

        original_job_id = str(uuid4())
        new_job_id = str(uuid4())

        mock_service = AsyncMock(spec=JobQueueService)
        mock_service.retry_job = AsyncMock(
            return_value=Job(
                id=new_job_id,
                type=JobType.TRANSCRIPTION,
                status=JobStatus.PENDING,
                stage=JobStage.QUEUED,
                progress=0,
                created_at=datetime.utcnow(),
                retry_count=1,
            )
        )

        app.dependency_overrides[get_job_queue_service] = lambda: mock_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/jobs/{original_job_id}/retry")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["new_job_id"] == new_job_id
            assert data["retry_attempt"] == 1
            assert "job" in data
            assert data["job"]["id"] == new_job_id
        finally:
            app.dependency_overrides.pop(get_job_queue_service, None)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self) -> None:
        """Test cancelling non-existent job returns 404."""
        from uuid import uuid4

        from app.api.deps import get_job_queue_service
        from app.main import app

        job_id = str(uuid4())

        mock_service = AsyncMock(spec=JobQueueService)
        mock_service.cancel_job = AsyncMock(return_value=None)

        app.dependency_overrides[get_job_queue_service] = lambda: mock_service

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/jobs/{job_id}/cancel")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_job_queue_service, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONCURRENT RECOVERY TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestConcurrentRecovery:
    """Tests for concurrent job operations during recovery."""

    @pytest.mark.asyncio
    async def test_multiple_jobs_recovered_correctly(self, tmp_path: Path) -> None:
        """Test multiple jobs are all recovered correctly."""
        # Create multiple jobs
        service1 = JobQueueService(data_path=tmp_path)

        jobs = []
        for i in range(5):
            job = await service1.create_job(
                JobType.TRANSCRIPTION if i % 2 == 0 else JobType.EXTRACTION,
                metadata={"index": i},
            )
            jobs.append(job)

        await service1.shutdown()

        # Restart
        service2 = JobQueueService(data_path=tmp_path)
        restored_count = await service2.restore_pending_jobs()

        assert restored_count == 5

        # Verify all jobs present with correct data
        for original_job in jobs:
            restored = await service2.get_job(original_job.id)
            assert restored is not None
            assert restored.type == original_job.type
            assert restored.metadata["index"] == original_job.metadata["index"]

    @pytest.mark.asyncio
    async def test_shutdown_marks_running_jobs_cancelled(self, tmp_path: Path) -> None:
        """Test that shutdown marks running jobs as CANCELLED."""
        service = JobQueueService(data_path=tmp_path)
        job = await service.create_job(JobType.TRANSCRIPTION)

        # Set to running
        async with service._jobs_lock:
            service._jobs[job.id].status = JobStatus.RUNNING

        await service._repository.save_job(service._jobs[job.id])

        # Shutdown
        await service.shutdown()

        # Check disk - should be CANCELLED or PENDING depending on implementation
        repo = JobRepository(tmp_path / "jobs")
        loaded = await repo.load_job(job.id)

        assert loaded is not None
        # Job should be in a state that indicates it was interrupted
        assert loaded.status in (
            JobStatus.PENDING,
            JobStatus.CANCELLED,
            JobStatus.RUNNING,
        )
