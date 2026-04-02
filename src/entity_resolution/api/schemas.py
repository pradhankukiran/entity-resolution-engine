"""Pydantic v2 request/response models for the Entity Resolution API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for the /search endpoint."""

    query: str = Field(..., min_length=1, max_length=200, description="Entity name to search for")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class MatchRequest(BaseModel):
    """Request body for the /match endpoint."""

    name_a: str = Field(..., min_length=1, max_length=200)
    name_b: str = Field(..., min_length=1, max_length=200)


class BatchRequest(BaseModel):
    """Request body for the POST /batch endpoint."""

    queries: list[SearchRequest] = Field(..., min_length=1, max_length=100)


class StrategyScore(BaseModel):
    """Individual matching strategy score within a result."""

    strategy_name: str
    score: float
    query_form: str
    candidate_form: str
    details: dict = {}


class MatchResultResponse(BaseModel):
    """A single ranked match result from the resolution pipeline."""

    rank: int
    entity_name: str
    entity_type: str
    entity_data: dict[str, Any]
    score: float
    strategy_scores: list[StrategyScore]


class SearchResponse(BaseModel):
    """Response body for the /search endpoint."""

    query: str
    entity_type: str
    detected_language: str
    query_forms: dict[str, str]
    total_candidates: int
    matches: list[MatchResultResponse]
    processing_steps: list[dict]
    processing_time_ms: float


class CompareResponse(BaseModel):
    """Response body for the /match endpoint."""

    name_a: str
    name_b: str
    final_score: float
    strategy_scores: list[StrategyScore]
    explanation: list[dict]


class BatchStatusResponse(BaseModel):
    """Response body for GET /batch/{job_id}."""

    job_id: str
    status: str
    progress: int
    total: int
    results: list[dict] | None = None
    created_at: str
    completed_at: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Response body for the /health endpoint."""

    status: str = "healthy"
    version: str = "1.0.0"


class StatsResponse(BaseModel):
    """Response body for the /stats endpoint."""

    total_entities: int
    total_ngrams: int
    database_path: str
    entity_types: list[str]
