"""Batch processing endpoints — submit and poll batch resolution jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from entity_resolution.api.schemas import BatchRequest, BatchStatusResponse
from entity_resolution.batch.manager import BatchManager, BatchQuery
from entity_resolution.core.dependencies import get_batch_manager

router = APIRouter()


@router.post("", response_model=BatchStatusResponse)
async def submit_batch(
    request: BatchRequest,
    batch_manager: BatchManager = Depends(get_batch_manager),
) -> BatchStatusResponse:
    """Submit a batch of search queries for asynchronous processing.

    ``BatchManager.submit()`` returns a job_id string and schedules
    background processing.  We look up the freshly-created ``BatchJob``
    to return its initial status.
    """
    queries = [
        BatchQuery(query=q.query, limit=q.limit)
        for q in request.queries
    ]

    job_id = await batch_manager.submit(queries)
    job = batch_manager.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=500, detail="Failed to create batch job")

    return BatchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        results=None,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )


@router.get("/{job_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    job_id: str,
    batch_manager: BatchManager = Depends(get_batch_manager),
) -> BatchStatusResponse:
    """Poll the status of a previously submitted batch job."""
    job = batch_manager.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Batch job '{job_id}' not found")

    # Results are already plain dicts from the BatchManager
    results: list[dict] | None = job.results if job.results else None

    return BatchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        results=results,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )
