"""Pipeline orchestration for entity resolution."""

from entity_resolution.pipeline.explainer import ExplanationBuilder, ExplanationStep
from entity_resolution.pipeline.blocker import CandidateBlocker
from entity_resolution.pipeline.pipeline import (
    MatchResult,
    PipelineResult,
    ResolutionPipeline,
)

__all__ = [
    "ExplanationBuilder",
    "ExplanationStep",
    "CandidateBlocker",
    "MatchResult",
    "PipelineResult",
    "ResolutionPipeline",
]
