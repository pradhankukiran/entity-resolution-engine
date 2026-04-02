"""Application entry point -- FastAPI app factory and uvicorn runner."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from entity_resolution.core.config import get_settings
from entity_resolution.core.dependencies import shutdown
from entity_resolution.core.logging import get_logger, setup_logging
from entity_resolution.api.middleware import LoggingMiddleware
from entity_resolution.api.routers import search, match, batch, health
from entity_resolution.api.routers import entity as entity_router

_STATIC_DIR = Path(__file__).parent / "static"

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown of shared resources."""
    setup_logging()
    logger.info("application.started")
    yield
    await shutdown()
    logger.info("application.stopped")


def create_app() -> FastAPI:
    """Construct and return the FastAPI application with all routers wired."""
    settings = get_settings()

    app = FastAPI(
        title="Entity Resolution Engine",
        description="Cross-language entity resolution for any entity type",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.add_middleware(LoggingMiddleware)

    # v1 generic entity routes
    app.include_router(entity_router.router, prefix="/v1", tags=["Entity Resolution"])

    # Backward-compatible routes (default to company entity type)
    app.include_router(health.router, tags=["Health"])
    app.include_router(search.router, tags=["Search"])
    app.include_router(match.router, tags=["Match"])
    app.include_router(batch.router, prefix="/batch", tags=["Batch"])

    # Serve the UI
    @app.get("/", include_in_schema=False)
    async def ui():
        return FileResponse(_STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


app = create_app()


def run() -> None:
    """Entry point used by the ``entity-resolution`` console script."""
    settings = get_settings()
    uvicorn.run(
        "entity_resolution.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
