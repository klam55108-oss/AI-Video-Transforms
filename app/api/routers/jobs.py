"""
Jobs router - handles job queue operations.

Provides endpoints for job creation, status polling, cancellation,
and listing with filtering capabilities.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_job_queue_service, validate_uuid
from app.models.jobs import JobStatus, JobType
from app.services import JobQueueService

router = APIRouter(prefix="/jobs", tags=["jobs"])


# Note: List route must come BEFORE parameterized route to avoid FastAPI
# matching the empty path as a job_id parameter
@router.get("")
async def list_jobs(
    status: JobStatus | None = Query(None, description="Filter by job status"),
    job_type: JobType | None = Query(None, description="Filter by job type"),
    job_queue_svc: JobQueueService = Depends(get_job_queue_service),
) -> dict[str, Any]:
    """
    List all jobs with optional filtering.

    Args:
        status: Optional status filter
        job_type: Optional job type filter
        job_queue_svc: Injected job queue service

    Returns:
        List of jobs matching filters
    """
    jobs = await job_queue_svc.list_jobs(status=status, job_type=job_type)

    return {
        "jobs": [job.to_dict() for job in jobs],
        "total": len(jobs),
    }


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    job_queue_svc: JobQueueService = Depends(get_job_queue_service),
) -> dict[str, Any]:
    """
    Get status and progress of a specific job.

    Args:
        job_id: UUID of the job
        job_queue_svc: Injected job queue service

    Returns:
        Job status with progress information
    """
    # Validate job ID format
    validate_uuid(job_id, "job ID")

    job = await job_queue_svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job.to_dict()


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    job_queue_svc: JobQueueService = Depends(get_job_queue_service),
) -> dict[str, str]:
    """
    Cancel a pending or running job.

    Args:
        job_id: UUID of the job to cancel
        job_queue_svc: Injected job queue service

    Returns:
        Success status message
    """
    # Validate job ID format
    validate_uuid(job_id, "job ID")

    success = await job_queue_svc.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Job not found or already completed",
        )

    return {"status": "success", "message": f"Job {job_id} cancelled"}
