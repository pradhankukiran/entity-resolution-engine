"""Match endpoint — compare two company names directly."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from entity_resolution.api.schemas import (
    CompareResponse,
    MatchRequest,
    StrategyScore,
)
from entity_resolution.core.dependencies import get_pipeline
from entity_resolution.pipeline.pipeline import ResolutionPipeline

router = APIRouter()


@router.post("/match", response_model=CompareResponse)
async def match(
    request: MatchRequest,
    pipeline: ResolutionPipeline = Depends(get_pipeline),
) -> CompareResponse:
    """Compare two company names and return a similarity score with explanation.

    The pipeline's ``compare()`` returns a plain dict with keys:
        - ``final_score``
        - ``strategy_scores`` (dict of strategy_name -> score)
        - ``strategy_details`` (list of dicts with per-strategy breakdowns)
        - ``forms_a``, ``forms_b``
    """
    result = await pipeline.compare(request.name_a, request.name_b)

    # Build typed StrategyScore list from the raw strategy_details dicts
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

    # Build an explanation list from the available form information
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
