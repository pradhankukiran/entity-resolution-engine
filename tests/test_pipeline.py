"""Tests for the entity resolution pipeline and explanation builder."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from entity_resolution.pipeline.explainer import ExplanationBuilder, ExplanationStep
from entity_resolution.pipeline.pipeline import (
    MatchResult,
    PipelineResult,
    ResolutionPipeline,
)
from entity_resolution.matching.base import StrategyResult


# ======================================================================
# ExplanationBuilder
# ======================================================================


class TestExplanationBuilder:
    """Tests for the step-by-step explanation builder."""

    def test_add_language_detection(self) -> None:
        builder = ExplanationBuilder()
        builder.add_language_detection("ソニー", "ja", "katakana")
        steps = builder.build()

        assert len(steps) == 1
        assert steps[0].step == "language_detection"
        assert steps[0].input_value == "ソニー"
        assert steps[0].output_value == "ja"
        assert steps[0].details["script"] == "katakana"

    def test_add_normalization(self) -> None:
        builder = ExplanationBuilder()
        builder.add_normalization("ソニー株式会社", "ソニー", ["株式会社"])
        steps = builder.build()

        assert len(steps) == 1
        assert steps[0].step == "normalization"
        assert steps[0].input_value == "ソニー株式会社"
        assert steps[0].output_value == "ソニー"
        assert steps[0].details["suffixes_removed"] == ["株式会社"]

    def test_add_transliteration(self) -> None:
        builder = ExplanationBuilder()
        builder.add_transliteration("ソニー", "sonii", ["sonii", "soni"])
        steps = builder.build()

        assert len(steps) == 1
        assert steps[0].step == "transliteration"
        assert steps[0].input_value == "ソニー"
        assert steps[0].output_value == "sonii"
        assert steps[0].details["variants"] == ["sonii", "soni"]

    def test_add_phonetic_encoding(self) -> None:
        builder = ExplanationBuilder()
        builder.add_phonetic_encoding("sony", "S500xx")
        steps = builder.build()

        assert len(steps) == 1
        assert steps[0].step == "phonetic_encoding"
        assert steps[0].output_value == "S500xx"

    def test_add_blocking(self) -> None:
        builder = ExplanationBuilder()
        builder.add_blocking(
            trigram_candidates=150, phonetic_candidates=30, total_unique=160
        )
        steps = builder.build()

        assert len(steps) == 1
        assert steps[0].step == "blocking"
        assert steps[0].details["trigram_candidates"] == 150
        assert steps[0].details["phonetic_candidates"] == 30
        assert steps[0].details["total_unique"] == 160

    def test_add_scoring(self) -> None:
        builder = ExplanationBuilder()
        builder.add_scoring(
            "Sony Corp",
            0.92,
            {"jaro_winkler": 0.95, "levenshtein": 0.88},
        )
        steps = builder.build()

        assert len(steps) == 1
        assert steps[0].step == "scoring"
        assert steps[0].input_value == "Sony Corp"
        assert "0.9200" in steps[0].output_value

    def test_add_steps_accumulates(self) -> None:
        builder = ExplanationBuilder()
        builder.add_language_detection("ソニー", "ja", "katakana")
        builder.add_normalization("ソニー株式会社", "ソニー", ["株式会社"])
        steps = builder.build()

        assert len(steps) == 2
        assert steps[0].step == "language_detection"
        assert steps[1].step == "normalization"

    def test_add_generic_step(self) -> None:
        builder = ExplanationBuilder()
        builder.add_step(
            "test", "A test step", input_value="in", output_value="out", foo="bar"
        )
        steps = builder.build()

        assert len(steps) == 1
        assert steps[0].step == "test"
        assert steps[0].input_value == "in"
        assert steps[0].output_value == "out"
        assert steps[0].details == {"foo": "bar"}

    def test_to_dict_list(self) -> None:
        builder = ExplanationBuilder()
        builder.add_step(
            "test", "A test step", input_value="in", output_value="out"
        )
        dicts = builder.to_dict_list()

        assert len(dicts) == 1
        assert dicts[0]["step"] == "test"
        assert dicts[0]["input_value"] == "in"
        assert dicts[0]["output_value"] == "out"
        assert dicts[0]["description"] == "A test step"
        assert isinstance(dicts[0]["details"], dict)

    def test_to_dict_list_is_json_serializable(self) -> None:
        """Ensure the dict list can be fed to json.dumps without error."""
        import json

        builder = ExplanationBuilder()
        builder.add_language_detection("test", "en", "latin")
        builder.add_normalization("Test Corp.", "test", ["Corp."])
        builder.add_phonetic_encoding("test", "T230xx")
        builder.add_blocking(10, 5, 12)
        builder.add_scoring("Test Inc", 0.85, {"jw": 0.9})

        data = builder.to_dict_list()
        serialized = json.dumps(data)
        assert isinstance(serialized, str)

    def test_build_returns_copy(self) -> None:
        """Mutating the returned list should not affect the builder."""
        builder = ExplanationBuilder()
        builder.add_step("a", "step a")
        steps = builder.build()
        steps.clear()

        assert len(builder.build()) == 1


# ======================================================================
# ResolutionPipeline.compare
# ======================================================================


def _make_mock_settings() -> MagicMock:
    """Create a mock Settings object with sensible defaults."""
    mock = MagicMock()
    mock.trigram_candidate_limit = 200
    mock.phonetic_candidate_limit = 100
    mock.min_score_threshold = 0.3
    return mock


class TestPipelineCompare:
    """Test the compare method which doesn't need a real DB."""

    @pytest.mark.asyncio
    async def test_compare_identical(self) -> None:
        """Two identical English names should score very high."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())

        result = await pipeline.compare("Sony", "Sony")

        assert result["final_score"] > 0.9
        assert result["name_a"] == "Sony"
        assert result["name_b"] == "Sony"
        assert "strategy_scores" in result

    @pytest.mark.asyncio
    async def test_compare_similar_english(self) -> None:
        """Similar English names should have a decent score."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())

        result = await pipeline.compare("Sony Corporation", "Sony Corp")

        assert result["final_score"] > 0.5

    @pytest.mark.asyncio
    async def test_compare_cross_language(self) -> None:
        """Japanese and English forms should still get some match via romaji."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())

        result = await pipeline.compare("ソニー", "Sony")

        # The romaji of ソニー is "sonii" (or variant "soni"/"sony"),
        # which should have *some* similarity to "sony".
        assert result["final_score"] > 0.0

    @pytest.mark.asyncio
    async def test_compare_returns_forms(self) -> None:
        """The compare result should include normalized forms for both names."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())

        result = await pipeline.compare("Toyota Motor", "トヨタ自動車")

        assert "forms_a" in result
        assert "forms_b" in result
        assert result["forms_a"]["original"] == "Toyota Motor"
        assert result["forms_b"]["original"] == "トヨタ自動車"

    @pytest.mark.asyncio
    async def test_compare_strategy_details(self) -> None:
        """The result should include per-strategy detail breakdowns."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())

        result = await pipeline.compare("Honda", "Honda")

        assert "strategy_details" in result
        assert len(result["strategy_details"]) > 0
        for detail in result["strategy_details"]:
            assert "strategy" in detail
            assert "score" in detail


# ======================================================================
# ResolutionPipeline._build_query_forms
# ======================================================================


class TestBuildQueryForms:
    """Test the internal _build_query_forms method."""

    def test_english_query_forms(self) -> None:
        """English query should produce normalized, romaji == normalized, phonetic."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())
        explanation = ExplanationBuilder()

        forms = pipeline._build_query_forms("Sony Corporation", explanation)

        assert forms["original"] == "Sony Corporation"
        assert forms["language"] == "en"
        assert forms["normalized"]  # should be non-empty
        assert forms["romaji"] == forms["normalized"]  # Latin text
        assert forms["phonetic"]  # should be non-empty

    def test_japanese_query_forms(self) -> None:
        """Japanese query should produce romaji distinct from normalized."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())
        explanation = ExplanationBuilder()

        forms = pipeline._build_query_forms("ソニー株式会社", explanation)

        assert forms["original"] == "ソニー株式会社"
        assert forms["language"] == "ja"
        assert forms["normalized"]  # stripped of 株式会社
        assert forms["romaji"]  # should be romanized
        assert forms["phonetic"]  # phonetic key

    def test_japanese_suffix_stripped(self) -> None:
        """Japanese corporate suffixes should be removed during normalization."""
        mock_db = AsyncMock()
        pipeline = ResolutionPipeline(mock_db, _make_mock_settings())
        explanation = ExplanationBuilder()

        forms = pipeline._build_query_forms("株式会社ソニー", explanation)

        # The normalized form should not contain 株式会社
        assert "株式会社" not in forms["normalized"]
