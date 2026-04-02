"""Async batch job manager for entity resolution.

Supports submitting a list of queries as a batch, tracking progress, and
retrieving results.  Concurrency is bounded by an :class:`asyncio.Semaphore`
so that the database and scoring pipeline are not overwhelmed.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from entity_resolution.pipeline.pipeline import ResolutionPipeline

# ------------------------------------------------------------------
# Data types
# ------------------------------------------------------------------


class JobStatus(StrEnum):
    """Lifecycle states for a batch job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BatchQuery:
    """A single query within a batch job."""

    query: str
    limit: int = 10


@dataclass
class BatchJob:
    """Tracks the state and results of a batch entity resolution job.

    Attributes:
        job_id: Unique identifier (UUID4).
        status: Current lifecycle state.
        queries: The list of queries submitted.
        results: List of dicts, one per completed query.
        created_at: Timestamp when the job was created.
        completed_at: Timestamp when the job finished (success or failure).
        progress: Number of queries processed so far.
        total: Total number of queries in the batch.
        error: Error message if the job failed.
    """

    job_id: str
    status: JobStatus
    queries: list[BatchQuery]
    results: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    progress: int = 0
    total: int = 0
    error: str | None = None


# ------------------------------------------------------------------
# Manager
# ------------------------------------------------------------------


class BatchManager:
    """Manages async batch entity resolution jobs.

    Jobs are processed in the background.  The caller can poll for status
    and results via :meth:`get_job`.

    Args:
        pipeline: The resolution pipeline to use for scoring.
        max_workers: Maximum number of concurrent queries within a single
            batch (controls the asyncio semaphore).
    """

    def __init__(self, pipeline: ResolutionPipeline, max_workers: int = 4) -> None:
        self._pipeline = pipeline
        self._max_workers = max_workers
        self._jobs: dict[str, BatchJob] = {}
        self._semaphore = asyncio.Semaphore(max_workers)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(self, queries: list[BatchQuery]) -> str:
        """Submit a batch job for background processing.

        Args:
            queries: List of :class:`BatchQuery` to resolve.

        Returns:
            The ``job_id`` (UUID4 string) for tracking.
        """
        job_id = str(uuid.uuid4())
        job = BatchJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            queries=queries,
            total=len(queries),
        )
        self._jobs[job_id] = job

        # Fire-and-forget: schedule background processing
        asyncio.create_task(self._process_job(job))

        return job_id

    def get_job(self, job_id: str) -> BatchJob | None:
        """Retrieve a job by its ID, or ``None`` if not found."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[BatchJob]:
        """Return all tracked jobs, newest first."""
        return sorted(
            self._jobs.values(),
            key=lambda j: j.created_at,
            reverse=True,
        )

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    async def _process_job(self, job: BatchJob) -> None:
        """Process all queries in a batch job with concurrency control.

        On success the job transitions to ``COMPLETED``; on any unhandled
        exception it transitions to ``FAILED`` with the error message stored.
        """
        job.status = JobStatus.PROCESSING
        try:
            # Pre-allocate a results list so indices stay stable even with
            # concurrent writes.
            job.results = [{}] * job.total

            tasks = [self._process_query(job, i, q) for i, q in enumerate(job.queries)]
            await asyncio.gather(*tasks)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(UTC)

    async def _process_query(self, job: BatchJob, index: int, query: BatchQuery) -> None:
        """Process a single query within a batch, respecting the semaphore.

        The result dict is stored at ``job.results[index]`` so that order
        is preserved even when queries complete out of order.
        """
        async with self._semaphore:
            try:
                result = await self._pipeline.resolve(query.query, limit=query.limit)
                job.results[index] = {
                    "index": index,
                    "query": query.query,
                    "matches": [
                        {
                            "entity_name": m.entity.name,
                            "entity_type": m.entity.type_name,
                            "entity_data": m.entity.data,
                            "score": m.score,
                            "rank": m.rank,
                        }
                        for m in result.matches
                    ],
                    "total_candidates": result.total_candidates,
                    "status": "ok",
                }
            except Exception as exc:
                job.results[index] = {
                    "index": index,
                    "query": query.query,
                    "matches": [],
                    "total_candidates": 0,
                    "status": "error",
                    "error": str(exc),
                }
            finally:
                job.progress += 1
