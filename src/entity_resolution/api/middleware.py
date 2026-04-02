"""Request/response logging middleware using structlog."""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Logs every incoming request and its response timing via structlog."""

    async def dispatch(self, request: Request, call_next) -> Response:
        logger = structlog.get_logger("entity_resolution.api.middleware")
        start_time = time.time()

        # Log request start
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query_string=str(request.url.query) if request.url.query else None,
        )

        response: Response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Timing and security headers
        response.headers["X-Processing-Time-Ms"] = str(round(duration_ms, 2))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
