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
    In-memory job representation.

    Tracks the full lifecycle of an async job from creation to completion/failure.
    NOT persisted to disk (MVP uses in-memory storage).
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

    def to_dict(self) -> dict[str, Any]:
        """
        Convert job to dictionary for API responses.

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
        }
