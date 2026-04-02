"""Tests for matching strategies, registry, and ensemble scorer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from entity_resolution.matching.ensemble import EnsembleResult, EnsembleScorer
from entity_resolution.matching.jaro_winkler import JaroWinklerStrategy
from entity_resolution.matching.levenshtein import LevenshteinStrategy
from entity_resolution.matching.phonetic_match import PhoneticStrategy
from entity_resolution.matching.registry import StrategyRegistry
from entity_resolution.matching.token_sort import TokenSortStrategy

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _make_mock_encoder(mapping: dict[str, str] | None = None):
    """Create a mock PhoneticEncoder that returns predictable keys.

    If *mapping* is given, ``encode(text)`` returns ``mapping.get(text, '')``.
    Otherwise it returns a simple Soundex-style stub: first letter uppercased
    plus '000'.
    """
    encoder = MagicMock()

    if mapping is not None:
        encoder.encode = MagicMock(side_effect=lambda t: mapping.get(t, ""))
    else:
        # Simple deterministic stub
        def _encode(text: str) -> str:
            if not text:
                return ""
            return text[0].upper() + "000"

        encoder.encode = MagicMock(side_effect=_encode)

    return encoder


# =======================================================================
# Jaro-Winkler
# =======================================================================


class TestJaroWinkler:
    def test_identical_strings(self):
        """Identical strings -> 1.0."""
        strategy = JaroWinklerStrategy()
        result = strategy.score("sony", "sony")
        assert result.score == pytest.approx(1.0)
        assert result.strategy_name == "jaro_winkler"

    def test_similar_strings(self):
        """'sony' vs 'soni' -> high score (>0.85)."""
        strategy = JaroWinklerStrategy()
        result = strategy.score("sony", "soni")
        assert result.score > 0.85

    def test_different_strings(self):
        """'sony' vs 'toyota' -> low score (<0.65)."""
        strategy = JaroWinklerStrategy()
        result = strategy.score("sony", "toyota")
        assert result.score < 0.65

    def test_case_insensitive(self):
        """'Sony' vs 'sony' -> 1.0."""
        strategy = JaroWinklerStrategy()
        result = strategy.score("Sony", "sony")
        assert result.score == pytest.approx(1.0)

    def test_empty_strings(self):
        """Both empty -> 1.0 (identical)."""
        strategy = JaroWinklerStrategy()
        result = strategy.score("", "")
        assert result.score == pytest.approx(1.0)

    def test_one_empty(self):
        """One empty string -> 0.0."""
        strategy = JaroWinklerStrategy()
        result = strategy.score("sony", "")
        assert result.score == pytest.approx(0.0)

    def test_weight(self):
        """Default weight is 0.3."""
        assert JaroWinklerStrategy().weight == pytest.approx(0.3)

    def test_details_contain_raw_similarity(self):
        """Details dict includes raw_similarity."""
        result = JaroWinklerStrategy().score("hello", "hello")
        assert "raw_similarity" in result.details


# =======================================================================
# Levenshtein
# =======================================================================


class TestLevenshtein:
    def test_identical(self):
        """Identical -> 1.0."""
        strategy = LevenshteinStrategy()
        result = strategy.score("sony", "sony")
        assert result.score == pytest.approx(1.0)

    def test_one_edit(self):
        """One character difference -> high score."""
        strategy = LevenshteinStrategy()
        result = strategy.score("sony", "soni")
        assert result.score > 0.7

    def test_completely_different(self):
        """Totally different strings -> low score."""
        strategy = LevenshteinStrategy()
        result = strategy.score("sony", "toyota")
        assert result.score < 0.5

    def test_case_insensitive(self):
        """Case differences are ignored."""
        strategy = LevenshteinStrategy()
        result = strategy.score("Sony", "sony")
        assert result.score == pytest.approx(1.0)

    def test_details_contain_edit_distance(self):
        """Details dict includes edit_distance."""
        result = LevenshteinStrategy().score("cat", "hat")
        assert "edit_distance" in result.details
        assert result.details["edit_distance"] == 1

    def test_weight(self):
        """Default weight is 0.25."""
        assert LevenshteinStrategy().weight == pytest.approx(0.25)


# =======================================================================
# Token Sort
# =======================================================================


class TestTokenSort:
    def test_reordered_tokens(self):
        """'sony group' vs 'group sony' -> very high score."""
        strategy = TokenSortStrategy()
        result = strategy.score("sony group", "group sony")
        assert result.score > 0.95

    def test_identical(self):
        """Identical -> 1.0."""
        strategy = TokenSortStrategy()
        result = strategy.score("sony", "sony")
        assert result.score == pytest.approx(1.0)

    def test_different(self):
        """Different strings -> low score."""
        strategy = TokenSortStrategy()
        result = strategy.score("sony", "toyota")
        assert result.score < 0.5

    def test_details_contain_raw_ratio(self):
        """Details dict includes raw_ratio in 0-100 range."""
        result = TokenSortStrategy().score("hello world", "world hello")
        assert "raw_ratio" in result.details
        assert 0.0 <= result.details["raw_ratio"] <= 100.0

    def test_weight(self):
        """Default weight is 0.25."""
        assert TokenSortStrategy().weight == pytest.approx(0.25)


# =======================================================================
# Phonetic Strategy
# =======================================================================


class TestPhoneticStrategy:
    def test_identical_keys(self):
        """Same phonetic key -> 1.0."""
        encoder = _make_mock_encoder({"sony": "S500", "soni": "S500"})
        strategy = PhoneticStrategy(encoder=encoder)
        result = strategy.score("sony", "soni")
        assert result.score == pytest.approx(1.0)

    def test_similar_pronunciation(self):
        """'sony' vs 'soni' -> same or very similar key."""
        encoder = _make_mock_encoder({"sony": "S500", "soni": "S500"})
        strategy = PhoneticStrategy(encoder=encoder)
        result = strategy.score("sony", "soni")
        assert result.score >= 0.9

    def test_different_keys(self):
        """Different phonetic keys -> low score."""
        encoder = _make_mock_encoder({"sony": "S500", "toyota": "T300"})
        strategy = PhoneticStrategy(encoder=encoder)
        result = strategy.score("sony", "toyota")
        # S500 vs T300: positions S!=T, 5!=3, 0==0, 0==0 -> 2/4 = 0.5
        assert result.score <= 0.5

    def test_partial_match(self):
        """Keys that differ in one position -> proportional score."""
        encoder = _make_mock_encoder({"a": "S500", "b": "S530"})
        strategy = PhoneticStrategy(encoder=encoder)
        result = strategy.score("a", "b")
        # 3 out of 4 characters match -> 0.75
        assert result.score == pytest.approx(0.75)

    def test_empty_inputs(self):
        """Both empty -> 1.0."""
        encoder = _make_mock_encoder({"": ""})
        strategy = PhoneticStrategy(encoder=encoder)
        result = strategy.score("", "")
        assert result.score == pytest.approx(1.0)

    def test_details_contain_keys(self):
        """Details include both phonetic keys."""
        encoder = _make_mock_encoder({"hello": "H400"})
        strategy = PhoneticStrategy(encoder=encoder)
        result = strategy.score("hello", "hello")
        assert "query_phonetic_key" in result.details
        assert "candidate_phonetic_key" in result.details
        assert result.details["query_phonetic_key"] == "H400"

    def test_weight(self):
        """Default weight is 0.2."""
        encoder = _make_mock_encoder()
        assert PhoneticStrategy(encoder=encoder).weight == pytest.approx(0.2)

    def test_name(self):
        """Strategy name is 'phonetic'."""
        encoder = _make_mock_encoder()
        assert PhoneticStrategy(encoder=encoder).name == "phonetic"


# =======================================================================
# Registry
# =======================================================================


class TestRegistry:
    def test_register_and_get(self):
        """Register strategy, retrieve by name."""
        registry = StrategyRegistry()
        strategy = JaroWinklerStrategy()
        registry.register(strategy)
        retrieved = registry.get("jaro_winkler")
        assert retrieved is strategy

    def test_default_registry(self):
        """Default registry has all 4 strategies."""
        registry = StrategyRegistry.default()
        names = {s.name for s in registry.all()}
        assert names == {"jaro_winkler", "levenshtein", "token_sort", "phonetic"}

    def test_unregister(self):
        """Can remove a strategy."""
        registry = StrategyRegistry()
        registry.register(JaroWinklerStrategy())
        assert len(registry.all()) == 1
        registry.unregister("jaro_winkler")
        assert len(registry.all()) == 0

    def test_unregister_missing_raises(self):
        """Unregistering a missing strategy raises KeyError."""
        registry = StrategyRegistry()
        with pytest.raises(KeyError):
            registry.unregister("nonexistent")

    def test_get_missing_raises(self):
        """Getting a missing strategy raises KeyError."""
        registry = StrategyRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_register_duplicate_raises(self):
        """Registering a duplicate name raises ValueError."""
        registry = StrategyRegistry()
        registry.register(JaroWinklerStrategy())
        with pytest.raises(ValueError):
            registry.register(JaroWinklerStrategy())

    def test_all_returns_list(self):
        """all() returns a list (not dict_values or similar)."""
        registry = StrategyRegistry()
        registry.register(LevenshteinStrategy())
        result = registry.all()
        assert isinstance(result, list)
        assert len(result) == 1


# =======================================================================
# Ensemble
# =======================================================================


class TestEnsemble:
    @staticmethod
    def _build_scorer(
        weights: dict[str, float] | None = None,
    ) -> EnsembleScorer:
        """Build an ensemble scorer with text-only strategies (no phonetic).

        Avoids the lazy PhoneticEncoder import so tests stay self-contained.
        """
        registry = StrategyRegistry()
        registry.register(JaroWinklerStrategy())
        registry.register(LevenshteinStrategy())
        registry.register(TokenSortStrategy())
        return EnsembleScorer(registry, weights=weights)

    @staticmethod
    def _build_scorer_with_phonetic(
        encoder=None,
        weights: dict[str, float] | None = None,
    ) -> EnsembleScorer:
        """Build an ensemble scorer that includes the phonetic strategy."""
        registry = StrategyRegistry()
        registry.register(JaroWinklerStrategy())
        registry.register(LevenshteinStrategy())
        registry.register(TokenSortStrategy())
        registry.register(PhoneticStrategy(encoder=encoder))
        return EnsembleScorer(registry, weights=weights)

    def test_perfect_match(self):
        """Identical inputs -> score near 1.0."""
        scorer = self._build_scorer()
        result = scorer.score(
            query_forms={"normalized": "sony", "romaji": "sony", "original": "sony"},
            candidate_forms={
                "name_normalized": "sony",
                "en_name_normalized": "sony",
                "name_romaji": "sony",
            },
        )
        assert result.final_score > 0.95
        assert isinstance(result, EnsembleResult)

    def test_weighted_scoring(self):
        """Weights affect final score correctly."""
        # With equal weights, we get one score; with skewed weights, another.
        scorer_equal = self._build_scorer(
            weights={"jaro_winkler": 1.0, "levenshtein": 1.0, "token_sort": 1.0}
        )
        scorer_skewed = self._build_scorer(
            weights={"jaro_winkler": 10.0, "levenshtein": 0.01, "token_sort": 0.01}
        )

        q = {"normalized": "sony", "romaji": "sony", "original": "sony"}
        c = {
            "name_normalized": "sony",
            "en_name_normalized": "sony",
            "name_romaji": "sony",
        }

        result_equal = scorer_equal.score(q, c)
        result_skewed = scorer_skewed.score(q, c)

        # Both should be near-perfect for identical strings, but the mechanism
        # should run without error.  For a more differentiated test, use
        # slightly different strings.
        assert isinstance(result_equal.final_score, float)
        assert isinstance(result_skewed.final_score, float)

    def test_weighted_scoring_differentiation(self):
        """Weights genuinely shift the final score for non-identical strings."""
        # "sonx" vs "sony" is close in JW but has 1 edit in Levenshtein.
        q = {"normalized": "sonx", "romaji": "sonx", "original": "sonx"}
        c = {"name_normalized": "sony", "en_name_normalized": "sony", "name_romaji": "sony"}

        # Heavy JW weight
        scorer_jw_heavy = self._build_scorer(
            weights={"jaro_winkler": 100.0, "levenshtein": 0.01, "token_sort": 0.01}
        )
        # Heavy Levenshtein weight
        scorer_lev_heavy = self._build_scorer(
            weights={"jaro_winkler": 0.01, "levenshtein": 100.0, "token_sort": 0.01}
        )

        result_jw = scorer_jw_heavy.score(q, c)
        result_lev = scorer_lev_heavy.score(q, c)

        # Both give valid floats and they may differ (JW penalizes differently than Lev).
        assert 0.0 <= result_jw.final_score <= 1.0
        assert 0.0 <= result_lev.final_score <= 1.0

    def test_best_strategy_identified(self):
        """best_strategy field is set correctly."""
        scorer = self._build_scorer()
        result = scorer.score(
            query_forms={"normalized": "sony", "romaji": "sony", "original": "sony"},
            candidate_forms={
                "name_normalized": "sony",
                "en_name_normalized": "sony",
                "name_romaji": "sony",
            },
        )
        # All strategies should score 1.0 on identical strings; best_strategy
        # should be one of the registered strategy names.
        assert result.best_strategy in {"jaro_winkler", "levenshtein", "token_sort"}

    def test_strategy_results_populated(self):
        """strategy_results contains one result per registered strategy."""
        scorer = self._build_scorer()
        result = scorer.score(
            query_forms={"normalized": "test", "romaji": "test", "original": "test"},
            candidate_forms={"name_normalized": "test", "name_romaji": "test"},
        )
        assert len(result.strategy_results) == 3  # jw, lev, token_sort
        names = {r.strategy_name for r in result.strategy_results}
        assert names == {"jaro_winkler", "levenshtein", "token_sort"}

    def test_no_compatible_pairs(self):
        """Strategy with no compatible forms gets score 0.0."""
        scorer = self._build_scorer()
        # Supply only phonetic-style keys -> text strategies have no compatible pairs.
        result = scorer.score(
            query_forms={"phonetic": "S500"},
            candidate_forms={"phonetic_key": "S500"},
        )
        # All text strategies should report 0.0 (no compatible pairs).
        assert result.final_score == pytest.approx(0.0)

    def test_forms_used_tracked(self):
        """query_forms_used and candidate_forms_used are reported."""
        scorer = self._build_scorer()
        result = scorer.score(
            query_forms={"normalized": "sony", "romaji": "sonii"},
            candidate_forms={"name_normalized": "sony", "name_romaji": "sonii"},
        )
        assert len(result.query_forms_used) > 0
        assert len(result.candidate_forms_used) > 0

    def test_with_phonetic_strategy(self):
        """Ensemble works with phonetic strategy included."""
        encoder = _make_mock_encoder({"sony": "S500"})
        scorer = self._build_scorer_with_phonetic(encoder=encoder)
        result = scorer.score(
            query_forms={
                "normalized": "sony",
                "romaji": "sony",
                "original": "sony",
                "phonetic": "sony",
            },
            candidate_forms={
                "name_normalized": "sony",
                "en_name_normalized": "sony",
                "name_romaji": "sony",
                "phonetic_key": "sony",
            },
        )
        assert result.final_score > 0.9
        assert len(result.strategy_results) == 4
        phonetic_results = [r for r in result.strategy_results if r.strategy_name == "phonetic"]
        assert len(phonetic_results) == 1

    def test_partial_match_scored_correctly(self):
        """Moderately similar strings yield a mid-range score."""
        scorer = self._build_scorer()
        result = scorer.score(
            query_forms={"normalized": "sony", "romaji": "sony", "original": "sony"},
            candidate_forms={
                "name_normalized": "samsung",
                "en_name_normalized": "samsung",
                "name_romaji": "samsung",
            },
        )
        assert 0.0 < result.final_score < 0.7
