"""Jaro-Winkler similarity strategy for entity matching."""

from __future__ import annotations

from rapidfuzz.distance import JaroWinkler

from entity_resolution.matching.base import MatchStrategy, StrategyResult


class JaroWinklerStrategy(MatchStrategy):
    """Jaro-Winkler similarity -- good for short strings, typos, prefix matches.

    Jaro-Winkler gives extra weight to common prefixes, making it especially
    effective for company names that share a root but may have minor
    transliteration differences (e.g., ``'sonii'`` vs ``'sony'``).
    """

    @property
    def name(self) -> str:
        return "jaro_winkler"

    @property
    def weight(self) -> float:
        return 0.3

    def score(self, query: str, candidate: str) -> StrategyResult:
        """Compute Jaro-Winkler similarity between *query* and *candidate*.

        Both strings are lowercased before comparison to ensure
        case-insensitive matching.

        Returns:
            StrategyResult with score in [0.0, 1.0] and ``raw_similarity`` in
            details.
        """
        q = query.lower()
        c = candidate.lower()

        similarity = JaroWinkler.similarity(q, c)

        return StrategyResult(
            strategy_name=self.name,
            score=similarity,
            query_form=query,
            candidate_form=candidate,
            details={"raw_similarity": similarity},
        )
