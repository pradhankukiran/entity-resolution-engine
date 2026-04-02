"""Normalized Levenshtein distance strategy for entity matching."""

from __future__ import annotations

from rapidfuzz.distance import Levenshtein

from entity_resolution.matching.base import MatchStrategy, StrategyResult


class LevenshteinStrategy(MatchStrategy):
    """Normalized Levenshtein distance -- good for edit-distance-based matching.

    Computes the minimum number of single-character edits (insertions,
    deletions, substitutions) required to turn one string into the other,
    then normalizes by the length of the longer string to yield a similarity
    score between 0.0 and 1.0.
    """

    @property
    def name(self) -> str:
        return "levenshtein"

    @property
    def weight(self) -> float:
        return 0.25

    def score(self, query: str, candidate: str) -> StrategyResult:
        """Compute normalized Levenshtein similarity.

        Both strings are lowercased before comparison.

        Returns:
            StrategyResult with score in [0.0, 1.0], plus ``edit_distance``
            and ``normalized_similarity`` in details.
        """
        q = query.lower()
        c = candidate.lower()

        edit_distance = Levenshtein.distance(q, c)
        normalized_similarity = Levenshtein.normalized_similarity(q, c)

        return StrategyResult(
            strategy_name=self.name,
            score=normalized_similarity,
            query_form=query,
            candidate_form=candidate,
            details={
                "edit_distance": edit_distance,
                "normalized_similarity": normalized_similarity,
            },
        )
