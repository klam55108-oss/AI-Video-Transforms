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


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    job_queue_svc: JobQueueService = Depends(get_job_queue_service),
) -> dict[str, Any]:
    """
    Cancel a pending or running job.

    Args:
        job_id: UUID of the job to cancel
        job_queue_svc: Injected job queue service

    Returns:
        Cancelled job data
    """
    # Validate job ID format
    validate_uuid(job_id, "job ID")

    cancelled_job = await job_queue_svc.cancel_job(job_id)
    if not cancelled_job:
        raise HTTPException(
            status_code=404,
            detail="Job not found or already completed",
        )

    return {
        "success": True,
        "job_id": job_id,
        "message": f"Job {job_id} cancelled",
        "job": cancelled_job.to_dict(),
    }


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: str,
    job_queue_svc: JobQueueService = Depends(get_job_queue_service),
) -> dict[str, Any]:
    """
    Retry a failed or cancelled job.

    Creates a new job with incremented retry count. Returns error if:
    - Original job not found
    - Job is still running
    - Max retries exceeded

    Args:
        job_id: UUID of the job to retry
        job_queue_svc: Injected job queue service

    Returns:
        New job data or error message
    """
    # Validate job ID format
    validate_uuid(job_id, "job ID")

    new_job = await job_queue_svc.retry_job(job_id)
    if not new_job:
        # Get the original job to provide better error message
        original_job = await job_queue_svc.get_job(job_id)
        if not original_job:
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        if original_job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry job with status {original_job.status.value}",
            )

        if original_job.retry_count >= original_job.max_retries:
            raise HTTPException(
                status_code=400,
                detail=f"Max retries ({original_job.max_retries}) exceeded",
            )

        # Generic error
        raise HTTPException(
            status_code=400,
            detail="Cannot retry job",
        )

    return {
        "success": True,
        "original_job_id": job_id,
        "new_job_id": new_job.id,
        "retry_attempt": new_job.retry_count,
        "max_retries": new_job.max_retries,
        "message": f"Job retry created (attempt {new_job.retry_count}/{new_job.max_retries})",
        "job": new_job.to_dict(),
    }
