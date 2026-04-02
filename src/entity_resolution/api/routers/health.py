"""Health and statistics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from entity_resolution.api.schemas import HealthResponse, StatsResponse
from entity_resolution.core.dependencies import get_db, get_entity_registry, get_settings
from entity_resolution.core.config import Settings
from entity_resolution.db.database import Database
from entity_resolution.db.query_builder import build_get_stats

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
    """Return database statistics (entity and ngram counts)."""
    registry = get_entity_registry()
    total_entities = 0
    total_ngrams = 0

    for config in registry.all():
        sql = build_get_stats(config)
        row = await db.fetch_one(sql)
        if row is not None:
            total_entities += row.get("entity_count", 0)
            total_ngrams += row.get("ngram_count", 0)

    return StatsResponse(
        total_entities=total_entities,
        total_ngrams=total_ngrams,
        database_path=settings.database_path,
        entity_types=registry.names(),
    )
