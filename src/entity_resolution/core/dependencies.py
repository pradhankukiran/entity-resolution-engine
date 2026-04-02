"""FastAPI dependency injection for shared singletons.

All expensive resources (database connection, pipeline, batch manager) are
lazily initialized on first use and cleaned up on application shutdown.
"""

from __future__ import annotations

from functools import lru_cache

from entity_resolution.core.config import Settings
from entity_resolution.db.database import Database
from entity_resolution.pipeline.pipeline import ResolutionPipeline
from entity_resolution.batch.manager import BatchManager

# ---------------------------------------------------------------------------
# Settings (synchronous, cached)
# ---------------------------------------------------------------------------


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()


# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------

_db: Database | None = None
_pipeline: ResolutionPipeline | None = None
_batch_manager: BatchManager | None = None


# ---------------------------------------------------------------------------
# Async dependency providers
# ---------------------------------------------------------------------------


async def get_db() -> Database:
    """Provide the shared :class:`Database` instance, connecting on first call."""
    global _db
    if _db is None:
        settings = get_settings()
        _db = Database(settings.database_path)
        await _db.connect()
    return _db


async def get_pipeline() -> ResolutionPipeline:
    """Provide the shared :class:`ResolutionPipeline` instance."""
    global _pipeline
    if _pipeline is None:
        db = await get_db()
        settings = get_settings()
        _pipeline = ResolutionPipeline(db, settings)
    return _pipeline


async def get_batch_manager() -> BatchManager:
    """Provide the shared :class:`BatchManager` instance."""
    global _batch_manager
    if _batch_manager is None:
        pipeline = await get_pipeline()
        settings = get_settings()
        _batch_manager = BatchManager(pipeline, max_workers=settings.batch_worker_count)
    return _batch_manager


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


async def shutdown() -> None:
    """Release all shared resources. Called during application shutdown."""
    global _db, _pipeline, _batch_manager
    if _db is not None:
        await _db.close()
    _db = None
    _pipeline = None
    _batch_manager = None
