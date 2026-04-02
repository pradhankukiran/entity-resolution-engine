"""Search endpoint — resolve a company name query against the database."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from entity_resolution.api.schemas import (
    MatchResultResponse,
    SearchRequest,
    SearchResponse,
    StrategyScore,
)
from entity_resolution.core.dependencies import get_pipeline
from entity_resolution.pipeline.pipeline import ResolutionPipeline

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    pipeline: ResolutionPipeline = Depends(get_pipeline),
) -> SearchResponse:
    """Resolve a company name query and return ranked matches."""
    start = time.time()

    result = await pipeline.resolve(request.query, request.limit)

    matches: list[MatchResultResponse] = []
    for m in result.matches:
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
        matches.append(
            MatchResultResponse(
                rank=m.rank,
                company_name=m.company.name,
                en_name=m.company.en_name,
                corporate_number=m.company.corporate_number,
                score=m.score,
                strategy_scores=strategy_scores,
            )
        )

    processing_time_ms = (time.time() - start) * 1000

    return SearchResponse(
        query=request.query,
        detected_language=result.detected_language,
        query_forms=result.query_forms,
        total_candidates=result.total_candidates,
        matches=matches,
        processing_steps=result.processing_steps,
        processing_time_ms=round(processing_time_ms, 2),
    )
