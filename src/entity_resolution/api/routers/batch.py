"""Batch endpoints -- backward-compatible company batch processing.

Delegates to the generic entity router with entity_type='company'.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from entity_resolution.api.schemas import BatchRequest, BatchStatusResponse
from entity_resolution.batch.manager import BatchQuery
from entity_resolution.core.dependencies import get_batch_manager

router = APIRouter()


@router.post("", response_model=BatchStatusResponse)
async def submit_batch(request: BatchRequest) -> BatchStatusResponse:
    """Submit a batch of search queries for asynchronous processing."""
    batch_manager = await get_batch_manager("company")
    queries = [BatchQuery(query=q.query, limit=q.limit) for q in request.queries]
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
async def get_batch_status(job_id: str) -> BatchStatusResponse:
    """Poll the status of a previously submitted batch job."""
    batch_manager = await get_batch_manager("company")
    job = batch_manager.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Batch job '{job_id}' not found")

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
