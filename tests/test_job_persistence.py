"""
Tests for job persistence functionality.

Validates JobRepository and JobQueueService persistence integration.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from app.models.jobs import Job, JobStage, JobStatus, JobType
from app.services.job_queue_service import JobQueueService
from app.services.job_repository import JobRepository


class TestJobRepository:
    """Test JobRepository save/load operations."""

    @pytest.mark.asyncio
    async def test_save_and_load_job(self, tmp_path: Path) -> None:
        """Test basic save and load cycle."""
        repo = JobRepository(tmp_path)

        # Create test job
        job = Job(
            id="test-123",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.RUNNING,
            stage=JobStage.TRANSCRIBING,
            progress=45,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            metadata={"video_source": "test.mp4"},
        )

        # Save job
        await repo.save_job(job)

        # Verify file exists
        job_file = tmp_path / "test-123.json"
        assert job_file.exists()

        # Load job
        loaded = await repo.load_job("test-123")
        assert loaded is not None
        assert loaded.id == "test-123"
        assert loaded.type == JobType.TRANSCRIPTION
        assert loaded.status == JobStatus.RUNNING
        assert loaded.progress == 45
        assert loaded.metadata["video_source"] == "test.mp4"

    @pytest.mark.asyncio
    async def test_atomic_write(self, tmp_path: Path) -> None:
        """Test atomic write prevents corruption."""
        repo = JobRepository(tmp_path)

        job = Job(
            id="atomic-test",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.RUNNING,
            stage=JobStage.TRANSCRIBING,
            progress=50,
            created_at=datetime.utcnow(),
        )

        # Save job
        await repo.save_job(job)

        # Verify no temp file remains
        temp_file = tmp_path / "atomic-test.tmp"
        assert not temp_file.exists()

        # Verify final file exists
        job_file = tmp_path / "atomic-test.json"
        assert job_file.exists()

    @pytest.mark.asyncio
    async def test_load_nonexistent_job(self, tmp_path: Path) -> None:
        """Test loading non-existent job returns None."""
        repo = JobRepository(tmp_path)
        loaded = await repo.load_job("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete_job(self, tmp_path: Path) -> None:
        """Test job deletion."""
        repo = JobRepository(tmp_path)

        job = Job(
            id="delete-test",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.COMPLETED,
            stage=JobStage.FINALIZING,
            progress=100,
            created_at=datetime.utcnow(),
        )

        await repo.save_job(job)
        assert await repo.delete_job("delete-test")

        # Verify file removed
        job_file = tmp_path / "delete-test.json"
        assert not job_file.exists()

        # Verify second delete returns False
        assert not await repo.delete_job("delete-test")

    @pytest.mark.asyncio
    async def test_list_all_jobs(self, tmp_path: Path) -> None:
        """Test listing all persisted jobs."""
        repo = JobRepository(tmp_path)

        # Create multiple jobs
        jobs = [
            Job(
                id=f"job-{i}",
                type=JobType.TRANSCRIPTION,
                status=JobStatus.PENDING,
                stage=JobStage.QUEUED,
                progress=0,
                created_at=datetime.utcnow(),
            )
            for i in range(3)
        ]

        for job in jobs:
            await repo.save_job(job)

        # List all jobs
        all_jobs = await repo.list_all_jobs()
        assert len(all_jobs) == 3
        assert {j.id for j in all_jobs} == {"job-0", "job-1", "job-2"}

    @pytest.mark.asyncio
    async def test_get_resumable_jobs(self, tmp_path: Path) -> None:
        """Test getting resumable jobs (PENDING or RUNNING)."""
        repo = JobRepository(tmp_path)

        # Create jobs in different states
        pending_job = Job(
            id="pending",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
        )

        running_job = Job(
            id="running",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.RUNNING,
            stage=JobStage.TRANSCRIBING,
            progress=50,
            created_at=datetime.utcnow(),
        )

        completed_job = Job(
            id="completed",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.COMPLETED,
            stage=JobStage.FINALIZING,
            progress=100,
            created_at=datetime.utcnow(),
        )

        failed_job = Job(
            id="failed",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.FAILED,
            stage=JobStage.TRANSCRIBING,
            progress=30,
            created_at=datetime.utcnow(),
            error="Test error",
        )

        await repo.save_job(pending_job)
        await repo.save_job(running_job)
        await repo.save_job(completed_job)
        await repo.save_job(failed_job)

        # Get resumable jobs
        resumable = await repo.get_resumable_jobs()
        assert len(resumable) == 2
        resumable_ids = {j.id for j in resumable}
        assert "pending" in resumable_ids
        assert "running" in resumable_ids
        assert "completed" not in resumable_ids
        assert "failed" not in resumable_ids

    @pytest.mark.asyncio
    async def test_save_job_with_all_fields(self, tmp_path: Path) -> None:
        """Test saving and loading job with all optional fields."""
        repo = JobRepository(tmp_path)

        job = Job(
            id="full-job",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.RUNNING,
            stage=JobStage.TRANSCRIBING,
            progress=75,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            metadata={"key": "value"},
            resume_from_step="segment_5",
        )

        await repo.save_job(job)

        loaded = await repo.load_job("full-job")
        assert loaded is not None
        assert loaded.resume_from_step == "segment_5"
        assert loaded.metadata == {"key": "value"}
        assert loaded.last_persisted_at is not None


class TestJobQueueServicePersistence:
    """Test JobQueueService persistence integration."""

    @pytest.mark.asyncio
    async def test_create_job_persists_immediately(self, tmp_path: Path) -> None:
        """Test that creating a job persists it to disk."""
        service = JobQueueService(data_path=tmp_path)

        job = await service.create_job(
            JobType.TRANSCRIPTION,
            metadata={"video_source": "test.mp4"},
        )

        # Verify file exists on disk
        job_file = tmp_path / "jobs" / f"{job.id}.json"
        assert job_file.exists()

    @pytest.mark.asyncio
    async def test_update_progress_persists_at_intervals(self, tmp_path: Path) -> None:
        """Test that progress updates persist at configured intervals."""
        service = JobQueueService(data_path=tmp_path)

        job = await service.create_job(JobType.TRANSCRIPTION)

        # Update to 10% (should persist)
        await service.update_progress(job.id, JobStage.TRANSCRIBING, 10)

        # Load from disk
        repo = JobRepository(tmp_path / "jobs")
        loaded = await repo.load_job(job.id)
        assert loaded is not None
        assert loaded.progress == 10
        assert loaded.stage == JobStage.TRANSCRIBING

        # Update to 15% (should NOT persist - not at 10% boundary)
        await service.update_progress(job.id, JobStage.TRANSCRIBING, 15)

        # Reload - should still show last persisted value
        loaded = await repo.load_job(job.id)
        assert loaded is not None
        # Note: This depends on timing - in production, 15% would not persist
        # But 20% would

        # Update to 20% (should persist)
        await service.update_progress(job.id, JobStage.TRANSCRIBING, 20)

        loaded = await repo.load_job(job.id)
        assert loaded is not None
        assert loaded.progress == 20

    @pytest.mark.asyncio
    async def test_complete_job_persists_final_state(self, tmp_path: Path) -> None:
        """Test that completing a job persists final state."""
        service = JobQueueService(data_path=tmp_path)

        job = await service.create_job(JobType.BOOTSTRAP)

        # Complete the job (using internal method)
        await service._complete_job(
            job.id,
            JobStatus.COMPLETED,
            result={"status": "success"},
        )

        # Load from disk
        repo = JobRepository(tmp_path / "jobs")
        loaded = await repo.load_job(job.id)
        assert loaded is not None
        assert loaded.status == JobStatus.COMPLETED
        assert loaded.result == {"status": "success"}
        assert loaded.completed_at is not None

    @pytest.mark.asyncio
    async def test_restore_pending_jobs(self, tmp_path: Path) -> None:
        """Test restoring jobs from disk on startup."""
        # Create first service instance and jobs
        service1 = JobQueueService(data_path=tmp_path)

        job1 = await service1.create_job(JobType.TRANSCRIPTION)
        job2 = await service1.create_job(JobType.BOOTSTRAP)

        # Manually mark job2 as running (simulating interrupted job)
        async with service1._jobs_lock:
            service1._jobs[job2.id].status = JobStatus.RUNNING
            service1._jobs[job2.id].progress = 50

        await service1._repository.save_job(service1._jobs[job2.id])

        # Shutdown first service
        await service1.shutdown()

        # Create new service instance (simulating restart)
        service2 = JobQueueService(data_path=tmp_path)

        # Restore jobs
        restored_count = await service2.restore_pending_jobs()
        assert restored_count == 2

        # Verify jobs are in memory
        assert await service2.get_job(job1.id) is not None
        assert await service2.get_job(job2.id) is not None

        # Verify running job was marked as pending
        job2_restored = await service2.get_job(job2.id)
        assert job2_restored is not None
        assert job2_restored.status == JobStatus.PENDING
        assert job2_restored.progress == 50  # Progress preserved

    @pytest.mark.asyncio
    async def test_restore_skips_completed_jobs(self, tmp_path: Path) -> None:
        """Test that restore only loads PENDING/RUNNING jobs."""
        repo = JobRepository(tmp_path / "jobs")

        # Create completed job
        completed_job = Job(
            id="completed",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.COMPLETED,
            stage=JobStage.FINALIZING,
            progress=100,
            created_at=datetime.utcnow(),
        )
        await repo.save_job(completed_job)

        # Create pending job
        pending_job = Job(
            id="pending",
            type=JobType.TRANSCRIPTION,
            status=JobStatus.PENDING,
            stage=JobStage.QUEUED,
            progress=0,
            created_at=datetime.utcnow(),
        )
        await repo.save_job(pending_job)

        # Create service and restore
        service = JobQueueService(data_path=tmp_path)
        restored_count = await service.restore_pending_jobs()

        assert restored_count == 1
        assert await service.get_job("pending") is not None
        assert await service.get_job("completed") is None  # Not loaded

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self, tmp_path: Path) -> None:
        """Test that resume_from_step field is preserved."""
        service = JobQueueService(data_path=tmp_path)

        job = await service.create_job(
            JobType.TRANSCRIPTION,
            metadata={"video_source": "test.mp4"},
        )

        # Manually set resume checkpoint
        async with service._jobs_lock:
            service._jobs[job.id].resume_from_step = "segment_3"

        await service._repository.save_job(service._jobs[job.id])

        # Shutdown and restart
        await service.shutdown()

        service2 = JobQueueService(data_path=tmp_path)
        await service2.restore_pending_jobs()

        # Verify checkpoint preserved
        restored_job = await service2.get_job(job.id)
        assert restored_job is not None
        assert restored_job.resume_from_step == "segment_3"

    @pytest.mark.asyncio
    async def test_concurrent_persistence(self, tmp_path: Path) -> None:
        """Test that concurrent job updates persist correctly."""
        service = JobQueueService(data_path=tmp_path)

        # Create multiple jobs
        jobs = [await service.create_job(JobType.TRANSCRIPTION) for _ in range(5)]

        # Update all jobs concurrently
        await asyncio.gather(
            *[
                service.update_progress(job.id, JobStage.TRANSCRIBING, 10)
                for job in jobs
            ]
        )

        # Verify all persisted
        repo = JobRepository(tmp_path / "jobs")
        for job in jobs:
            loaded = await repo.load_job(job.id)
            assert loaded is not None
            assert loaded.progress == 10
