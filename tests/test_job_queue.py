"""
Tests for job queue service and API.

Covers job lifecycle, progress tracking, concurrency limits,
cancellation, and API endpoint behavior.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.jobs import Job, JobStage, JobStatus, JobType
from app.services.job_queue_service import JobQueueService


class TestJobModel:
    """Tests for Job dataclass."""

    def test_job_creation(self) -> None:
        """Test creating a job instance."""
        job = Job(
            id="test-123",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
            metadata={"video_path": "/tmp/test.mp4"},
        )

        assert job.id == "test-123"
        assert job.type == JobType.TRANSCRIPTION
        assert job.status == JobStatus.PENDING
        assert job.stage == JobStage.QUEUED
        assert job.progress == 0
        assert job.started_at is None
        assert job.completed_at is None
        assert job.result is None
        assert job.error is None
        assert job.metadata["video_path"] == "/tmp/test.mp4"

    def test_job_to_dict(self) -> None:
        """Test job serialization to dictionary."""
        created = datetime.utcnow()
        job = Job(
            id="test-456",
            type=JobType.BOOTSTRAP,
            status=JobStatus.RUNNING,
            stage=JobStage.PROCESSING,
            progress=50,
            created_at=created,
            started_at=created,
            metadata={"project_id": "abc123"},
        )

        data = job.to_dict()

        assert data["id"] == "test-456"
        assert data["type"] == "bootstrap"
        assert data["status"] == "running"
        assert data["stage"] == "processing"
        assert data["progress"] == 50
        assert data["created_at"] == created.isoformat()
        assert data["started_at"] == created.isoformat()
        assert data["completed_at"] is None
        assert data["metadata"]["project_id"] == "abc123"


class TestJobQueueService:
    """Tests for JobQueueService."""

    @pytest.fixture
    async def job_service(self) -> JobQueueService:
        """Create a job queue service for testing."""
        return JobQueueService()

    @pytest.mark.asyncio
    async def test_create_job(self, job_service: JobQueueService) -> None:
        """Test creating a job."""
        job = await job_service.create_job(
            JobType.TRANSCRIPTION,
            metadata={"video_path": "/tmp/video.mp4"},
        )

        assert job.id is not None
        assert job.type == JobType.TRANSCRIPTION
        assert job.status == JobStatus.PENDING
        assert job.stage == JobStage.QUEUED
        assert job.progress == 0
        assert job.metadata["video_path"] == "/tmp/video.mp4"

        # Verify job is in queue
        assert job_service.get_queue_size() > 0
        assert job_service.get_job_count() == 1

    @pytest.mark.asyncio
    async def test_get_job(self, job_service: JobQueueService) -> None:
        """Test retrieving a job by ID."""
        created = await job_service.create_job(JobType.EXTRACTION)

        retrieved = await job_service.get_job(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.type == JobType.EXTRACTION

        # Test non-existent job
        missing = await job_service.get_job("non-existent-id")
        assert missing is None

    @pytest.mark.asyncio
    async def test_list_jobs(self, job_service: JobQueueService) -> None:
        """Test listing jobs with filters."""
        # Create multiple jobs
        _job1 = await job_service.create_job(JobType.TRANSCRIPTION)
        job2 = await job_service.create_job(JobType.BOOTSTRAP)
        _job3 = await job_service.create_job(JobType.TRANSCRIPTION)

        # List all jobs
        all_jobs = await job_service.list_jobs()
        assert len(all_jobs) == 3

        # Filter by type
        transcription_jobs = await job_service.list_jobs(job_type=JobType.TRANSCRIPTION)
        assert len(transcription_jobs) == 2
        assert all(j.type == JobType.TRANSCRIPTION for j in transcription_jobs)

        bootstrap_jobs = await job_service.list_jobs(job_type=JobType.BOOTSTRAP)
        assert len(bootstrap_jobs) == 1
        assert bootstrap_jobs[0].id == job2.id

        # Filter by status
        pending_jobs = await job_service.list_jobs(status=JobStatus.PENDING)
        assert len(pending_jobs) == 3

        # Newest first order
        assert all_jobs[0].created_at >= all_jobs[-1].created_at

    @pytest.mark.asyncio
    async def test_cancel_job(self, job_service: JobQueueService) -> None:
        """Test cancelling a job."""
        job = await job_service.create_job(JobType.TRANSCRIPTION)

        # Cancel the job
        success = await job_service.cancel_job(job.id)
        assert success is True

        # Verify job is marked as failed
        cancelled = await job_service.get_job(job.id)
        assert cancelled is not None
        assert cancelled.status == JobStatus.FAILED
        assert cancelled.error == "Cancelled by user"
        assert cancelled.completed_at is not None

        # Try cancelling again (should fail)
        success = await job_service.cancel_job(job.id)
        assert success is False

        # Try cancelling non-existent job
        success = await job_service.cancel_job("non-existent")
        assert success is False

    @pytest.mark.asyncio
    async def test_update_progress(self, job_service: JobQueueService) -> None:
        """Test updating job progress."""
        job = await job_service.create_job(JobType.EXTRACTION)

        # Update progress
        await job_service.update_progress(job.id, JobStage.DOWNLOADING, 25)

        updated = await job_service.get_job(job.id)
        assert updated is not None
        assert updated.stage == JobStage.DOWNLOADING
        assert updated.progress == 25

        # Test progress clamping
        await job_service.update_progress(job.id, JobStage.PROCESSING, 150)
        clamped = await job_service.get_job(job.id)
        assert clamped is not None
        assert clamped.progress == 100

        await job_service.update_progress(job.id, JobStage.QUEUED, -10)
        clamped = await job_service.get_job(job.id)
        assert clamped is not None
        assert clamped.progress == 0

    @pytest.mark.asyncio
    async def test_job_processing_lifecycle(self, job_service: JobQueueService) -> None:
        """Test full job processing lifecycle."""
        # Start background processor
        processor_task = asyncio.create_task(
            job_service.run_job_processor_loop(num_workers=1)
        )

        try:
            # Create a job
            job = await job_service.create_job(JobType.TRANSCRIPTION)

            # Wait for job to be processed
            for _ in range(50):  # Max 5 seconds
                await asyncio.sleep(0.1)
                current = await job_service.get_job(job.id)
                if current and current.status == JobStatus.COMPLETED:
                    break

            # Verify job completed
            completed = await job_service.get_job(job.id)
            assert completed is not None
            assert completed.status == JobStatus.COMPLETED
            assert completed.progress == 100
            assert completed.started_at is not None
            assert completed.completed_at is not None
            assert completed.result is not None

        finally:
            # Cleanup
            await job_service.shutdown()
            processor_task.cancel()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_concurrent_job_limit(self, job_service: JobQueueService) -> None:
        """Test that concurrent job processing respects limits."""
        # Start background processor with concurrency limit of 1
        job_service._processing_semaphore = asyncio.Semaphore(1)
        processor_task = asyncio.create_task(
            job_service.run_job_processor_loop(num_workers=2)
        )

        try:
            # Create multiple jobs
            _jobs = [
                await job_service.create_job(JobType.TRANSCRIPTION) for _ in range(3)
            ]

            # Give processor time to start
            await asyncio.sleep(0.2)

            # Check that only 1 job is running (concurrency limit)
            all_jobs = await job_service.list_jobs()
            running_count = sum(1 for j in all_jobs if j.status == JobStatus.RUNNING)
            assert running_count <= 1

        finally:
            # Cleanup
            await job_service.shutdown()
            processor_task.cancel()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_shutdown_graceful(self, job_service: JobQueueService) -> None:
        """Test graceful shutdown marks pending jobs as failed."""
        # Create jobs
        job1 = await job_service.create_job(JobType.TRANSCRIPTION)
        job2 = await job_service.create_job(JobType.BOOTSTRAP)

        # Shutdown without processing
        await job_service.shutdown()

        # Verify pending jobs marked as failed
        failed1 = await job_service.get_job(job1.id)
        assert failed1 is not None
        assert failed1.status == JobStatus.FAILED
        assert failed1.error == "Server shutdown"

        failed2 = await job_service.get_job(job2.id)
        assert failed2 is not None
        assert failed2.status == JobStatus.FAILED


class TestJobQueueAPI:
    """Tests for job queue API endpoints."""

    @pytest.mark.asyncio
    async def test_get_job_status(self) -> None:
        """Test GET /jobs/{job_id} endpoint."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create a job via service
            from app.api.deps import get_job_queue_service

            job_service = get_job_queue_service()
            job = await job_service.create_job(
                JobType.TRANSCRIPTION,
                metadata={"test": "data"},
            )

            # Get job status via API
            response = await client.get(f"/jobs/{job.id}")
            assert response.status_code == 200

            data = response.json()
            assert data["id"] == job.id
            assert data["type"] == "transcription"
            assert data["status"] == "pending"
            assert data["metadata"]["test"] == "data"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self) -> None:
        """Test GET /jobs/{job_id} with non-existent job."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Use a valid UUID v4 format that doesn't exist
            response = await client.get("/jobs/12345678-1234-4567-89ab-123456789012")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_job_invalid_id(self) -> None:
        """Test GET /jobs/{job_id} with invalid ID format."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/jobs/invalid-id")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_jobs_endpoint(self) -> None:
        """Test GET /jobs endpoint."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create jobs via service
            from app.api.deps import get_job_queue_service

            job_service = get_job_queue_service()
            await job_service.create_job(JobType.TRANSCRIPTION)
            await job_service.create_job(JobType.BOOTSTRAP)

            # List all jobs
            response = await client.get("/jobs")
            assert response.status_code == 200

            data = response.json()
            assert "jobs" in data
            assert "total" in data
            assert len(data["jobs"]) >= 2

    @pytest.mark.asyncio
    async def test_list_jobs_with_filters(self) -> None:
        """Test GET /jobs with query filters."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Filter by type
            response = await client.get("/jobs?job_type=transcription")
            assert response.status_code == 200

            # Filter by status
            response = await client.get("/jobs?status=pending")
            assert response.status_code == 200

            # Both filters
            response = await client.get("/jobs?job_type=bootstrap&status=completed")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cancel_job_endpoint(self) -> None:
        """Test DELETE /jobs/{job_id} endpoint."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create a job
            from app.api.deps import get_job_queue_service

            job_service = get_job_queue_service()
            job = await job_service.create_job(JobType.EXTRACTION)

            # Cancel via API
            response = await client.delete(f"/jobs/{job.id}")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "success"

            # Verify job is cancelled
            cancelled = await job_service.get_job(job.id)
            assert cancelled is not None
            assert cancelled.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self) -> None:
        """Test DELETE /jobs/{job_id} with non-existent job."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Use a valid UUID v4 format that doesn't exist
            response = await client.delete("/jobs/12345678-1234-4567-89ab-123456789012")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_completed_job(self) -> None:
        """Test that completed jobs cannot be cancelled."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create and manually complete a job
            from app.api.deps import get_job_queue_service

            job_service = get_job_queue_service()
            job = await job_service.create_job(JobType.TRANSCRIPTION)

            # Mark as completed
            async with job_service._jobs_lock:
                if job.id in job_service._jobs:
                    job_service._jobs[job.id].status = JobStatus.COMPLETED

            # Try to cancel
            response = await client.delete(f"/jobs/{job.id}")
            assert response.status_code == 404  # Not found or already completed


class TestJobQueueServiceIntegration:
    """Integration tests for job queue service within ServiceContainer."""

    @pytest.mark.asyncio
    async def test_service_container_integration(self) -> None:
        """Test that job queue service is properly initialized in container."""
        from app.services import get_services

        # Service should be available
        job_service = get_services().job_queue
        assert job_service is not None
        assert isinstance(job_service, JobQueueService)

        # Should be able to create jobs
        job = await job_service.create_job(JobType.TRANSCRIPTION)
        assert job.id is not None

    @pytest.mark.asyncio
    async def test_background_processor_integration(self) -> None:
        """Test that job queue service is integrated with background processing.

        Note: This test verifies the service is properly initialized and can
        create jobs. Full background processing is tested in
        TestJobQueueService.test_job_processing_lifecycle which creates
        its own processor loop for better isolation.
        """
        from app.services import get_services

        job_service = get_services().job_queue

        # Verify service is initialized
        assert job_service is not None

        # Verify we can create jobs
        job = await job_service.create_job(JobType.BOOTSTRAP)
        assert job.id is not None
        assert job.status == JobStatus.PENDING

        # Verify the job is tracked
        retrieved = await job_service.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id

        # Note: We don't wait for processing here because the background
        # processor runs in the service container's lifecycle and may have
        # multiple jobs queued from other tests. The isolated processing
        # test (test_job_processing_lifecycle) validates actual execution.


class TestTranscriptionJobIntegration:
    """Integration tests for transcription job processing."""

    @pytest.mark.asyncio
    async def test_transcription_job_with_valid_metadata(
        self, tmp_path: Path
    ) -> None:
        """Test transcription job with proper metadata creates transcript."""
        from unittest.mock import AsyncMock, MagicMock, Mock, patch

        from app.models.jobs import JobType

        job_service = JobQueueService()

        # Create a mock video file
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video data")

        # Mock the transcription components
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="Test transcription"
        )

        mock_segment = MagicMock()
        mock_segment.__len__ = lambda self: 300000  # 5 min
        mock_segment.__getitem__ = lambda self, key: mock_segment
        mock_segment.export = MagicMock()

        # Mock TranscriptionService.save_transcript (async method)
        mock_transcript_metadata = MagicMock()
        mock_transcript_metadata.id = "test-transcript-id"
        mock_transcript_metadata.filename = "test.txt"

        mock_transcription_service = MagicMock()
        mock_transcription_service.save_transcript = AsyncMock(
            return_value=mock_transcript_metadata
        )

        mock_services = MagicMock()
        mock_services.transcription = mock_transcription_service

        # Start background processor
        processor_task = asyncio.create_task(
            job_service.run_job_processor_loop(num_workers=1)
        )

        try:
            with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                with patch(
                    "subprocess.run", return_value=Mock(returncode=0, stderr=b"")
                ):
                    with patch(
                        "app.agent.transcribe_tool.OpenAI", return_value=mock_client
                    ):
                        with patch(
                            "app.agent.transcribe_tool.AudioSegment.from_mp3",
                            return_value=mock_segment,
                        ):
                            with patch("os.path.getsize", return_value=1024):
                                with patch("builtins.open", MagicMock()):
                                    with patch("os.remove"):
                                        with patch.dict(
                                            "os.environ",
                                            {"OPENAI_API_KEY": "test-key"},
                                        ):
                                            with patch(
                                                "app.services.get_services",
                                                return_value=mock_services,
                                            ):
                                                # Create a transcription job
                                                job = await job_service.create_job(
                                                    JobType.TRANSCRIPTION,
                                                    metadata={
                                                        "video_source": str(video_file),
                                                        "language": "en",
                                                        "temperature": 0.0,
                                                    },
                                                )

                                                # Wait for processing
                                                for _ in range(100):  # Max 10 seconds
                                                    await asyncio.sleep(0.1)
                                                    current = await job_service.get_job(
                                                        job.id
                                                    )
                                                    if (
                                                        current
                                                        and current.status
                                                        == JobStatus.COMPLETED
                                                    ):
                                                        break

                                                # Verify job completed
                                                completed = await job_service.get_job(
                                                    job.id
                                                )
                                                assert completed is not None
                                                assert (
                                                    completed.status
                                                    == JobStatus.COMPLETED
                                                )
                                                assert completed.progress == 100
                                                assert completed.result is not None
                                                assert "transcript_id" in completed.result

        finally:
            # Cleanup
            await job_service.shutdown()
            processor_task.cancel()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_transcription_job_handles_errors_gracefully(self) -> None:
        """Test transcription job handles errors and marks job as failed."""
        from app.models.jobs import JobType

        job_service = JobQueueService()

        # Start background processor
        processor_task = asyncio.create_task(
            job_service.run_job_processor_loop(num_workers=1)
        )

        try:
            # Create a job with invalid video source
            job = await job_service.create_job(
                JobType.TRANSCRIPTION,
                metadata={
                    "video_source": "/nonexistent/file.mp4",
                },
            )

            # Wait for processing
            for _ in range(50):  # Max 5 seconds
                await asyncio.sleep(0.1)
                current = await job_service.get_job(job.id)
                if current and current.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    break

            # Verify job failed with error
            failed = await job_service.get_job(job.id)
            assert failed is not None
            assert failed.status == JobStatus.FAILED
            assert failed.error is not None
            assert "not found" in failed.error.lower()

        finally:
            # Cleanup
            await job_service.shutdown()
            processor_task.cancel()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
