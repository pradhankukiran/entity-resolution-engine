"""Batch processing for entity resolution jobs."""

from entity_resolution.batch.manager import (
    BatchJob,
    BatchManager,
    BatchQuery,
    JobStatus,
)

__all__ = [
    "BatchJob",
    "BatchManager",
    "BatchQuery",
    "JobStatus",
]
