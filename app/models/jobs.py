"""
Job queue models and types.

Defines data structures for asynchronous job processing, including job types,
states, progress tracking, and metadata storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobType(str, Enum):
    """Job types that can be queued and processed."""

    TRANSCRIPTION = "transcription"
    BOOTSTRAP = "bootstrap"
    EXTRACTION = "extraction"


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStage(str, Enum):
    """Detailed progress stages for jobs."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    PROCESSING = "processing"
    FINALIZING = "finalizing"


@dataclass
class Job:
    """
    Job representation with persistence support.

    Tracks the full lifecycle of an async job from creation to completion/failure.
    Persisted to disk for recovery on server restart.
    """

    id: str
    type: JobType
    status: JobStatus
    stage: JobStage
    progress: int  # 0-100
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    last_persisted_at: datetime | None = None
    resume_from_step: str | None = None  # e.g., "segment_3" for transcription
    retry_count: int = 0
    max_retries: int = 3
    cancelled_at: datetime | None = None
    cancelled_by: str | None = None  # "user" or "system"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert job to dictionary for API responses and persistence.

        Returns:
            Dictionary representation of job state
        """
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "stage": self.stage.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
            "last_persisted_at": (
                self.last_persisted_at.isoformat() if self.last_persisted_at else None
            ),
            "resume_from_step": self.resume_from_step,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "cancelled_at": (
                self.cancelled_at.isoformat() if self.cancelled_at else None
            ),
            "cancelled_by": self.cancelled_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """
        Create Job instance from dictionary (for deserialization).

        Args:
            data: Dictionary representation of job

        Returns:
            Job instance
        """
        return cls(
            id=data["id"],
            type=JobType(data["type"]),
            status=JobStatus(data["status"]),
            stage=JobStage(data["stage"]),
            progress=data["progress"],
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            result=data.get("result"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            last_persisted_at=(
                datetime.fromisoformat(data["last_persisted_at"])
                if data.get("last_persisted_at")
                else None
            ),
            resume_from_step=data.get("resume_from_step"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            cancelled_at=(
                datetime.fromisoformat(data["cancelled_at"])
                if data.get("cancelled_at")
                else None
            ),
            cancelled_by=data.get("cancelled_by"),
        )
