"""Weighted multi-strategy ensemble scorer."""

from __future__ import annotations

from dataclasses import dataclass

from entity_resolution.matching.base import MatchStrategy, StrategyResult
from entity_resolution.matching.registry import StrategyRegistry


@dataclass
class EnsembleResult:
    """Aggregated result from the ensemble of all matching strategies.

    Attributes:
        final_score: Weighted average of all individual strategy scores.
        strategy_results: Individual StrategyResult from each strategy.
        best_strategy: Name of the strategy that produced the highest score.
        query_forms_used: List of query form names that were actually used.
        candidate_forms_used: List of candidate form names that were actually used.
    """

    final_score: float
    strategy_results: list[StrategyResult]
    best_strategy: str  # name of highest-scoring strategy
    query_forms_used: list[str]
    candidate_forms_used: list[str]


# ---------------------------------------------------------------------------
# Compatible form-pair definitions
# ---------------------------------------------------------------------------

# Text-based strategies compare romanized / normalized forms.
_TEXT_PAIRS: list[tuple[str, str]] = [
    ("normalized", "name_normalized"),
    ("normalized", "en_name_normalized"),
    ("romaji", "name_romaji"),
    ("romaji", "en_name_normalized"),
    ("original", "name_normalized"),
]

# The phonetic strategy only compares pre-computed phonetic keys.
_PHONETIC_PAIRS: list[tuple[str, str]] = [
    ("phonetic", "phonetic_key"),
]


class EnsembleScorer:
    """Combines multiple strategy scores using a weighted average.

    For each registered strategy the scorer tries every *compatible pair* of
    query and candidate forms and keeps the best score.  The final result is a
    weighted average of those per-strategy best scores.
    """

    def __init__(
        self,
        registry: StrategyRegistry,
        weights: dict[str, float] | None = None,
        text_pairs: list[tuple[str, str]] | None = None,
        phonetic_pairs: list[tuple[str, str]] | None = None,
    ):
        """Initialize the ensemble scorer.

        Args:
            registry: Strategy registry with registered strategies.
            weights: Optional weight overrides ``{strategy_name: weight}``.
                If *None*, each strategy's default ``weight`` property is used.
            text_pairs: Form-pair definitions for text-based strategies.
                If *None*, falls back to the module-level ``_TEXT_PAIRS``.
            phonetic_pairs: Form-pair definitions for phonetic strategies.
                If *None*, falls back to the module-level ``_PHONETIC_PAIRS``.
        """
        self._registry = registry
        self._weights = weights
        self._text_pairs = text_pairs if text_pairs is not None else _TEXT_PAIRS
        self._phonetic_pairs = phonetic_pairs if phonetic_pairs is not None else _PHONETIC_PAIRS

    def score(
        self,
        query_forms: dict[str, str],
        candidate_forms: dict[str, str],
    ) -> EnsembleResult:
        """Score a query against a candidate using all registered strategies.

        Args:
            query_forms: Mapping of ``form_name -> text`` for the query entity,
                e.g.::

                    {"original": "ソニー", "normalized": "そにー",
                     "romaji": "sonii", "phonetic": "S500"}

            candidate_forms: Mapping of ``form_name -> text`` for the candidate
                entity, e.g.::

                    {"name_normalized": "sony", "en_name_normalized": "sony",
                     "name_romaji": "sonii", "phonetic_key": "S500"}

        Returns:
            An EnsembleResult containing the weighted final score, individual
            strategy results, and metadata about which forms were used.
        """
        strategies = self._registry.all()
        strategy_results: list[StrategyResult] = []
        query_forms_used: set[str] = set()
        candidate_forms_used: set[str] = set()

        for strategy in strategies:
            pairs = self._get_compatible_pairs(query_forms, candidate_forms, strategy.name)

            best_result: StrategyResult | None = None

            for q_form_name, q_text, c_form_name, c_text in pairs:
                result = strategy.score(q_text, c_text)
                # Override form names with the dict key names (not the raw text)
                result.query_form = q_form_name
                result.candidate_form = c_form_name

                if best_result is None or result.score > best_result.score:
                    best_result = result

            if best_result is not None:
                strategy_results.append(best_result)
                query_forms_used.add(best_result.query_form)
                candidate_forms_used.add(best_result.candidate_form)
            else:
                # No compatible pair exists; record a zero-score result so the
                # strategy still participates in the weighted average.
                strategy_results.append(
                    StrategyResult(
                        strategy_name=strategy.name,
                        score=0.0,
                        query_form="",
                        candidate_form="",
                        details={"note": "no compatible form pairs found"},
                    )
                )

        # Compute weighted average
        total_weight = 0.0
        weighted_sum = 0.0
        for result in strategy_results:
            strategy = self._registry.get(result.strategy_name)
            w = self._get_weight(strategy)
            weighted_sum += result.score * w
            total_weight += w

        final_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Identify the best individual strategy
        best_strategy = ""
        if strategy_results:
            best = max(strategy_results, key=lambda r: r.score)
            best_strategy = best.strategy_name

        return EnsembleResult(
            final_score=final_score,
            strategy_results=strategy_results,
            best_strategy=best_strategy,
            query_forms_used=sorted(query_forms_used),
            candidate_forms_used=sorted(candidate_forms_used),
        )

    def _get_weight(self, strategy: MatchStrategy) -> float:
        """Get weight for strategy, checking overrides first."""
        if self._weights and strategy.name in self._weights:
            return self._weights[strategy.name]
        return strategy.weight

    def _get_compatible_pairs(
        self,
        query_forms: dict[str, str],
        candidate_forms: dict[str, str],
        strategy_name: str,
    ) -> list[tuple[str, str, str, str]]:
        """Return compatible form pairs for the given strategy.

        Returns:
            List of ``(query_form_name, query_text, candidate_form_name,
            candidate_text)`` tuples where both forms are present in their
            respective dictionaries.
        """
        pair_defs = self._phonetic_pairs if strategy_name == "phonetic" else self._text_pairs

        pairs: list[tuple[str, str, str, str]] = []
        for q_key, c_key in pair_defs:
            if q_key in query_forms and c_key in candidate_forms:
                pairs.append((q_key, query_forms[q_key], c_key, candidate_forms[c_key]))

        return pairs
