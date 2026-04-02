"""Shared pytest fixtures for the entity resolution test suite."""

from __future__ import annotations

import pytest

from entity_resolution.core.config import Settings
from entity_resolution.db.database import Database


@pytest.fixture
def settings() -> Settings:
    """Return settings configured with an in-memory database."""
    return Settings(database_path=":memory:")


@pytest.fixture
async def db(settings: Settings) -> Database:
    """Provide a connected in-memory Database, closed after the test."""
    database = Database(settings.database_path)
    await database.connect()
    yield database  # type: ignore[misc]
    await database.close()


@pytest.fixture
def anyio_backend() -> str:
    """Tell pytest-asyncio / anyio to use asyncio."""
    return "asyncio"
