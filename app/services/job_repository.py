"""
Job Repository - JSON-based persistence for background jobs.

Provides atomic read/write operations for job state with:
- Individual job files: data/jobs/{job_id}.json
- Recovery of interrupted jobs on startup
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.jobs import Job, JobStatus

logger = logging.getLogger(__name__)


class JobRepository:
    """File-based job persistence using atomic writes."""

    def __init__(self, jobs_path: Path) -> None:
        """
        Initialize repository with storage path.

        Args:
            jobs_path: Directory path for storing job files
        """
        self.jobs_path = jobs_path
        self.jobs_path.mkdir(parents=True, exist_ok=True)

    async def save_job(self, job: Job) -> None:
        """
        Atomically save job state to disk.

        Uses atomic write pattern (write to temp, then rename) to prevent
        corruption on server crashes.

        Args:
            job: Job instance to persist
        """
        job_file = self.jobs_path / f"{job.id}.json"
        temp_file = self.jobs_path / f"{job.id}.tmp"

        data = job.to_dict()
        data["last_persisted_at"] = datetime.utcnow().isoformat()

        # Run file I/O in thread pool to avoid blocking event loop
        await asyncio.to_thread(self._atomic_write, temp_file, job_file, data)

    def _atomic_write(
        self, temp_file: Path, job_file: Path, data: dict[str, Any]
    ) -> None:
        """
        Perform atomic file write (blocking operation).

        Args:
            temp_file: Temporary file path
            job_file: Final file path
            data: JSON-serializable data
        """
        # Write to temp file first
        temp_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

        # Atomic rename (POSIX guarantees atomicity)
        temp_file.rename(job_file)

    async def load_job(self, job_id: str) -> Job | None:
        """
        Load job from disk.

        Args:
            job_id: Job identifier

        Returns:
            Job instance or None if not found
        """
        job_file = self.jobs_path / f"{job_id}.json"
        if not job_file.exists():
            return None

        try:
            data = await asyncio.to_thread(self._read_json, job_file)
            return Job.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load job {job_id}: {e}")
            return None

    def _read_json(self, file_path: Path) -> dict[str, Any]:
        """
        Read JSON file (blocking operation).

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed JSON data
        """
        return json.loads(file_path.read_text(encoding="utf-8"))

    async def delete_job(self, job_id: str) -> bool:
        """
        Remove job file from disk.

        Args:
            job_id: Job identifier

        Returns:
            True if job was deleted, False if not found
        """
        job_file = self.jobs_path / f"{job_id}.json"
        if job_file.exists():
            await asyncio.to_thread(job_file.unlink)
            return True
        return False

    async def list_all_jobs(self) -> list[Job]:
        """
        List all persisted jobs.

        Returns:
            List of all jobs in storage
        """
        jobs: list[Job] = []

        # Get all job files
        job_files = await asyncio.to_thread(self._list_job_files)

        # Load each job
        for job_file in job_files:
            if job_file.name.startswith("_"):
                continue  # Skip index/metadata files

            try:
                data = await asyncio.to_thread(self._read_json, job_file)
                jobs.append(Job.from_dict(data))
            except Exception as e:
                logger.warning(f"Skipping corrupted job file {job_file}: {e}")

        return jobs

    def _list_job_files(self) -> list[Path]:
        """
        List all job JSON files (blocking operation).

        Returns:
            List of job file paths
        """
        return list(self.jobs_path.glob("*.json"))

    async def get_resumable_jobs(self) -> list[Job]:
        """
        Get jobs that were running or pending when server stopped.

        Returns:
            List of jobs that should be resumed
        """
        resumable: list[Job] = []

        for job in await self.list_all_jobs():
            if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                resumable.append(job)

        return resumable
