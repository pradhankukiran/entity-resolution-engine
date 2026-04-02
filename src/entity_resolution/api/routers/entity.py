"""Generic entity resolution endpoints parameterized by entity type."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Path

from entity_resolution.api.schemas import (
    BatchRequest,
    BatchStatusResponse,
    CompareResponse,
    MatchRequest,
    MatchResultResponse,
    SearchRequest,
    SearchResponse,
    StrategyScore,
)
from entity_resolution.batch.manager import BatchManager, BatchQuery
from entity_resolution.core.dependencies import (
    get_batch_manager,
    get_entity_registry,
    get_pipeline,
)
from entity_resolution.entity_types.config import EntityTypeRegistry
from entity_resolution.pipeline.pipeline import ResolutionPipeline

router = APIRouter()


def _validate_entity_type(
    entity_type: str = Path(..., description="Entity type (e.g. 'company')"),
) -> str:
    """Validate entity_type path parameter against the registry."""
    registry = get_entity_registry()
    if entity_type not in registry:
        available = ", ".join(registry.names())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown entity type '{entity_type}'. Available: {available}",
        )
    return entity_type


def _build_match_response(m) -> MatchResultResponse:  # noqa: ANN001
    """Convert a pipeline MatchResult into the API response model."""
    strategy_scores = [
        StrategyScore(
            strategy_name=sr.strategy_name,
            score=sr.score,
            query_form=sr.query_form,
            candidate_form=sr.candidate_form,
            details=sr.details,
        )
        for sr in m.ensemble_result.strategy_results
    ]
    return MatchResultResponse(
        rank=m.rank,
        entity_name=m.entity.name,
        entity_type=m.entity.type_name,
        entity_data=m.entity.data,
        score=m.score,
        strategy_scores=strategy_scores,
    )


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------


@router.post("/{entity_type}/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    entity_type: str = Depends(_validate_entity_type),
) -> SearchResponse:
    """Resolve an entity name query and return ranked matches."""
    start = time.time()
    pipeline = await get_pipeline(entity_type)
    result = await pipeline.resolve(request.query, request.limit)

    matches = [_build_match_response(m) for m in result.matches]
    processing_time_ms = (time.time() - start) * 1000

    return SearchResponse(
        query=request.query,
        entity_type=entity_type,
        detected_language=result.detected_language,
        query_forms=result.query_forms,
        total_candidates=result.total_candidates,
        matches=matches,
        processing_steps=result.processing_steps,
        processing_time_ms=round(processing_time_ms, 2),
    )


# ------------------------------------------------------------------
# Match (compare two names)
# ------------------------------------------------------------------


@router.post("/{entity_type}/match", response_model=CompareResponse)
async def match(
    request: MatchRequest,
    entity_type: str = Depends(_validate_entity_type),
) -> CompareResponse:
    """Compare two entity names and return a similarity score."""
    pipeline = await get_pipeline(entity_type)
    result = await pipeline.compare(request.name_a, request.name_b)

    strategy_scores = [
        StrategyScore(
            strategy_name=detail["strategy"],
            score=detail["score"],
            query_form=detail.get("query_form", ""),
            candidate_form=detail.get("candidate_form", ""),
            details=detail.get("details", {}),
        )
        for detail in result.get("strategy_details", [])
    ]

    explanation: list[dict] = []
    if "forms_a" in result:
        explanation.append({
            "step": "normalization_a",
            "description": f"Normalized forms for '{request.name_a}'",
            "details": result["forms_a"],
        })
    if "forms_b" in result:
        explanation.append({
            "step": "normalization_b",
            "description": f"Normalized forms for '{request.name_b}'",
            "details": result["forms_b"],
        })

    return CompareResponse(
        name_a=request.name_a,
        name_b=request.name_b,
        final_score=result["final_score"],
        strategy_scores=strategy_scores,
        explanation=explanation,
    )


# ------------------------------------------------------------------
# Batch
# ------------------------------------------------------------------


@router.post("/{entity_type}/batch", response_model=BatchStatusResponse)
async def submit_batch(
    request: BatchRequest,
    entity_type: str = Depends(_validate_entity_type),
) -> BatchStatusResponse:
    """Submit a batch of search queries for asynchronous processing."""
    batch_manager = await get_batch_manager(entity_type)
    queries = [BatchQuery(query=q.query, limit=q.limit) for q in request.queries]
    job_id = await batch_manager.submit(queries)
    job = batch_manager.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=500, detail="Failed to create batch job")

    return BatchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        results=None,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )


@router.get("/{entity_type}/batch/{job_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    job_id: str,
    entity_type: str = Depends(_validate_entity_type),
) -> BatchStatusResponse:
    """Poll the status of a previously submitted batch job."""
    batch_manager = await get_batch_manager(entity_type)
    job = batch_manager.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Batch job '{job_id}' not found")

    results: list[dict] | None = job.results if job.results else None

    return BatchStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        results=results,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )
