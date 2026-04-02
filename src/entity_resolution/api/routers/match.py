"""Match endpoint -- backward-compatible company name comparison.

Delegates to the generic entity router with entity_type='company'.
"""

from __future__ import annotations

from fastapi import APIRouter

from entity_resolution.api.schemas import (
    CompareResponse,
    MatchRequest,
    StrategyScore,
)
from entity_resolution.core.dependencies import get_pipeline

router = APIRouter()


@router.post("/match", response_model=CompareResponse)
async def match(request: MatchRequest) -> CompareResponse:
    """Compare two company names and return a similarity score."""
    pipeline = await get_pipeline("company")
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
