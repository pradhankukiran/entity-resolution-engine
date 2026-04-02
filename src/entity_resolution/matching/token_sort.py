"""Token sort ratio strategy for entity matching."""

from __future__ import annotations

from rapidfuzz import fuzz

from entity_resolution.matching.base import MatchStrategy, StrategyResult


class TokenSortStrategy(MatchStrategy):
    """Token sort ratio -- good for word reordering.

    Sorts tokens alphabetically in both strings before computing a similarity
    ratio, so ``'Sony Group'`` and ``'Group Sony'`` score very high.  This is
    particularly useful for company names that may appear in different word
    orders across languages (e.g., Japanese ``X株式会社`` vs English
    ``Company X``).
    """

    @property
    def name(self) -> str:
        return "token_sort"

    @property
    def weight(self) -> float:
        return 0.25

    def score(self, query: str, candidate: str) -> StrategyResult:
        """Compute token-sort similarity between *query* and *candidate*.

        Uses ``rapidfuzz.fuzz.token_sort_ratio`` which internally lowercases,
        then divides by 100 to normalize into the [0.0, 1.0] range.

        Returns:
            StrategyResult with score in [0.0, 1.0] and ``raw_ratio`` (0-100)
            in details.
        """
        raw_ratio = fuzz.token_sort_ratio(query, candidate)
        normalized_score = raw_ratio / 100.0

        return StrategyResult(
            strategy_name=self.name,
            score=normalized_score,
            query_form=query,
            candidate_form=candidate,
            details={"raw_ratio": raw_ratio},
        )
