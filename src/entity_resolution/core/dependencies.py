"""FastAPI dependency injection for shared singletons.

All expensive resources (database connection, pipeline, batch manager) are
lazily initialized on first use and cleaned up on application shutdown.
"""

from __future__ import annotations

from functools import lru_cache

from entity_resolution.core.config import Settings
from entity_resolution.db.database import Database
from entity_resolution.entity_types.config import EntityTypeRegistry
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
_registry: EntityTypeRegistry | None = None
_pipelines: dict[str, ResolutionPipeline] = {}
_batch_managers: dict[str, BatchManager] = {}


def get_entity_registry() -> EntityTypeRegistry:
    """Return the shared entity type registry, creating it on first call."""
    global _registry
    if _registry is None:
        _registry = EntityTypeRegistry.default()
    return _registry


# ---------------------------------------------------------------------------
# Async dependency providers
# ---------------------------------------------------------------------------


async def get_db() -> Database:
    """Provide the shared :class:`Database` instance, connecting on first call."""
    global _db
    if _db is None:
        settings = get_settings()
        registry = get_entity_registry()
        _db = Database(settings.database_path, entity_registry=registry)
        await _db.connect()
    return _db


async def get_pipeline(entity_type: str = "company") -> ResolutionPipeline:
    """Provide a :class:`ResolutionPipeline` for the given entity type."""
    if entity_type not in _pipelines:
        db = await get_db()
        settings = get_settings()
        registry = get_entity_registry()
        config = registry.get(entity_type)
        _pipelines[entity_type] = ResolutionPipeline(db, settings, entity_config=config)
    return _pipelines[entity_type]


async def get_batch_manager(entity_type: str = "company") -> BatchManager:
    """Provide a :class:`BatchManager` for the given entity type."""
    if entity_type not in _batch_managers:
        pipeline = await get_pipeline(entity_type)
        settings = get_settings()
        _batch_managers[entity_type] = BatchManager(
            pipeline, max_workers=settings.batch_worker_count
        )
    return _batch_managers[entity_type]


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


async def shutdown() -> None:
    """Release all shared resources. Called during application shutdown."""
    global _db, _registry
    if _db is not None:
        await _db.close()
    _db = None
    _registry = None
    _pipelines.clear()
    _batch_managers.clear()
