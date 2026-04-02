"""Shared pytest fixtures for the entity resolution test suite."""

from __future__ import annotations

import pytest

from entity_resolution.core.config import Settings
from entity_resolution.db.database import Database
from entity_resolution.entity_types.config import EntityTypeRegistry


@pytest.fixture
def settings() -> Settings:
    """Return settings configured with an in-memory database."""
    return Settings(database_path=":memory:")


@pytest.fixture
def entity_registry() -> EntityTypeRegistry:
    """Return a default entity type registry with company config loaded."""
    return EntityTypeRegistry.default()


@pytest.fixture
async def db(settings: Settings, entity_registry: EntityTypeRegistry) -> Database:
    """Provide a connected in-memory Database, closed after the test."""
    database = Database(settings.database_path, entity_registry=entity_registry)
    await database.connect()
    yield database  # type: ignore[misc]
    await database.close()


@pytest.fixture
def anyio_backend() -> str:
    """Tell pytest-asyncio / anyio to use asyncio."""
    return "asyncio"
