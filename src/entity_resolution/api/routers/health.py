"""Health and statistics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from entity_resolution.api.schemas import HealthResponse, StatsResponse
from entity_resolution.core.dependencies import get_db, get_settings
from entity_resolution.core.config import Settings
from entity_resolution.db.database import Database
from entity_resolution.db.queries import GET_STATS

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check -- always returns healthy if the process is running."""
    return HealthResponse(status="healthy", version="1.0.0")


@router.get("/stats", response_model=StatsResponse)
async def stats(
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StatsResponse:
    """Return database statistics (company and ngram counts)."""
    row = await db.fetch_one(GET_STATS)

    company_count = 0
    ngram_count = 0
    if row is not None:
        company_count = row.get("company_count", 0)
        ngram_count = row.get("ngram_count", 0)

    return StatsResponse(
        total_companies=company_count,
        total_ngrams=ngram_count,
        database_path=settings.database_path,
    )
