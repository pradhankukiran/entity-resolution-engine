"""Async SQLite connection manager using aiosqlite."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

import aiosqlite

from entity_resolution.core.config import get_settings
from entity_resolution.core.logging import get_logger

logger = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    """Thin async wrapper around an aiosqlite connection.

    Usage::

        db = Database()
        await db.connect()
        try:
            rows = await db.fetch_all("SELECT * FROM companies")
        finally:
            await db.close()

    Or as an async context manager::

        async with Database() as db:
            rows = await db.fetch_all("SELECT * FROM companies")
    """

    def __init__(
        self,
        db_path: str | None = None,
        entity_registry: Any | None = None,
    ) -> None:
        self._db_path = db_path or get_settings().database_path
        self._conn: aiosqlite.Connection | None = None
        self._entity_registry = entity_registry

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the database connection and ensure the schema exists."""
        # Ensure the parent directory for the database file exists.
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._conn = await aiosqlite.connect(self._db_path)
        # Return rows as sqlite3.Row so callers can access columns by name.
        self._conn.row_factory = aiosqlite.Row
        # Enable WAL mode for better concurrent read performance.
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        await self._initialize_schema()
        logger.info("database.connected", path=self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("database.closed", path=self._db_path)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @property
    def connection(self) -> aiosqlite.Connection:
        """Return the raw connection, raising if not yet connected."""
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn

    async def execute(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> aiosqlite.Cursor:
        """Execute a single SQL statement and return the cursor."""
        cursor = await self.connection.execute(sql, parameters)
        await self.connection.commit()
        return cursor

    async def execute_many(
        self, sql: str, seq_of_parameters: Sequence[Sequence[Any]]
    ) -> None:
        """Execute a SQL statement against all parameter sequences."""
        await self.connection.executemany(sql, seq_of_parameters)
        await self.connection.commit()

    async def fetch_one(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> dict[str, Any] | None:
        """Execute a query and return the first row as a dict, or None."""
        cursor = await self.connection.execute(sql, parameters)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetch_all(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows as a list of dicts."""
        cursor = await self.connection.execute(sql, parameters)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _initialize_schema(self) -> None:
        """Initialize database schema.

        If an entity type registry was provided, generates schema DDL from
        each registered entity type.  Otherwise falls back to the static
        ``schema.sql`` file for backward compatibility.
        """
        if self._entity_registry is not None:
            from entity_resolution.db.query_builder import build_schema

            for config in self._entity_registry.all():
                ddl = build_schema(config)
                await self.connection.executescript(ddl)
        else:
            schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
            await self.connection.executescript(schema_sql)

        await self.connection.commit()
        logger.info("database.schema_initialized")
