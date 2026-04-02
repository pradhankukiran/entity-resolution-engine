"""Abstract base for matching strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StrategyResult:
    """Result from a single matching strategy evaluation.

    Attributes:
        strategy_name: Unique identifier of the strategy that produced this result.
        score: Similarity score in the range [0.0, 1.0].
        query_form: Which normalized form of the query was used.
        candidate_form: Which normalized form of the candidate was used.
        details: Strategy-specific metadata (raw similarity, edit distance, etc.).
    """

    strategy_name: str
    score: float  # 0.0 to 1.0
    query_form: str  # which form of the query was used
    candidate_form: str  # which form of the candidate was used
    details: dict = field(default_factory=dict)  # strategy-specific info


class MatchStrategy(ABC):
    """Abstract base class for all matching strategies.

    Subclasses must implement :pyattr:`name` and :pymeth:`score`.
    They may optionally override :pyattr:`weight` to influence the default
    weighting in ensemble scoring.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy name."""

    @property
    def weight(self) -> float:
        """Default weight in ensemble. Override as needed."""
        return 1.0

    @abstractmethod
    def score(self, query: str, candidate: str) -> StrategyResult:
        """Score similarity between query and candidate strings.

        Args:
            query: The query string (already normalized to the appropriate form).
            candidate: The candidate string to compare against.

        Returns:
            StrategyResult with score in range [0.0, 1.0].
        """
