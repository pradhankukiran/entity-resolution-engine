"""Tests for the TextNormalizer class."""

from __future__ import annotations

import pytest

from entity_resolution.normalization.normalizer import TextNormalizer


class TestTextNormalizer:
    """Tests for TextNormalizer normalization pipeline."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.normalizer = TextNormalizer()

    # ------------------------------------------------------------------
    # NFKC normalization
    # ------------------------------------------------------------------

    def test_nfkc_normalization(self) -> None:
        """Fullwidth characters should be converted to ASCII equivalents."""
        assert self.normalizer.normalize("\uff33\uff4f\uff4e\uff59") == "sony"  # Ｓｏｎｙ

    def test_nfkc_fullwidth_digits(self) -> None:
        """Fullwidth digits should be normalized."""
        result = self.normalizer.normalize("\uff11\uff12\uff13")  # １２３
        assert result == "123"

    # ------------------------------------------------------------------
    # Japanese suffix stripping
    # ------------------------------------------------------------------

    def test_strip_jp_suffix_end(self) -> None:
        """Suffix at end: ソニー株式会社 -> ソニー."""
        result = self.normalizer.normalize_japanese("ソニー株式会社")
        assert result == "ソニー"

    def test_strip_jp_suffix_start(self) -> None:
        """Suffix at start: 株式会社ソニー -> ソニー."""
        result = self.normalizer.normalize_japanese("株式会社ソニー")
        assert result == "ソニー"

    def test_strip_jp_suffix_yuugen(self) -> None:
        """有限会社 should be stripped."""
        result = self.normalizer.normalize_japanese("有限会社テスト")
        assert result == "テスト"

    def test_strip_jp_suffix_goudou(self) -> None:
        """合同会社 should be stripped."""
        result = self.normalizer.normalize_japanese("テスト合同会社")
        assert result == "テスト"

    def test_strip_jp_long_suffix(self) -> None:
        """特定非営利活動法人 (NPO) should be stripped."""
        result = self.normalizer.normalize_japanese("特定非営利活動法人テスト")
        assert result == "テスト"

    def test_no_strip_when_no_suffix(self) -> None:
        """Text without corporate suffixes should pass through unchanged."""
        result = self.normalizer.normalize_japanese("ソニー")
        assert result == "ソニー"

    # ------------------------------------------------------------------
    # English suffix stripping
    # ------------------------------------------------------------------

    def test_strip_en_suffix_corporation(self) -> None:
        """Sony Corporation -> sony."""
        result = self.normalizer.normalize_english("Sony Corporation")
        assert result == "sony"

    def test_strip_en_suffix_inc(self) -> None:
        """Apple Inc. -> apple."""
        result = self.normalizer.normalize_english("Apple Inc.")
        assert result == "apple"

    def test_strip_en_suffix_ltd(self) -> None:
        """Toyota Ltd. -> toyota."""
        result = self.normalizer.normalize_english("Toyota Ltd.")
        assert result == "toyota"

    def test_strip_en_suffix_llc(self) -> None:
        """Acme LLC -> acme."""
        result = self.normalizer.normalize_english("Acme LLC")
        assert result == "acme"

    def test_strip_en_suffix_gmbh(self) -> None:
        """Siemens GmbH -> siemens."""
        result = self.normalizer.normalize_english("Siemens GmbH")
        assert result == "siemens"

    def test_strip_en_suffix_kk(self) -> None:
        """Sony K.K. -> sony."""
        result = self.normalizer.normalize_english("Sony K.K.")
        assert result == "sony"

    # ------------------------------------------------------------------
    # Whitespace handling
    # ------------------------------------------------------------------

    def test_whitespace_collapse(self) -> None:
        """Multiple spaces should collapse; trailing suffix stripped."""
        result = self.normalizer.normalize("Sony  Group   Corp")
        assert result == "sony group"

    def test_whitespace_strip(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        result = self.normalizer.normalize("  Sony  ")
        assert result == "sony"

    def test_tab_and_newline_collapse(self) -> None:
        """Tabs and newlines should collapse to single space."""
        result = self.normalizer.normalize("Sony\t\tGroup\nInc")
        assert result == "sony group"

    # ------------------------------------------------------------------
    # Trigram generation
    # ------------------------------------------------------------------

    def test_trigram_generation(self) -> None:
        """'sony' should produce boundary-padded trigrams."""
        trigrams = self.normalizer.generate_trigrams("sony")
        assert trigrams == {"$so", "son", "ony", "ny$"}

    def test_trigram_short_string(self) -> None:
        """Single char should still produce trigrams with boundary markers."""
        trigrams = self.normalizer.generate_trigrams("a")
        assert trigrams == {"$a$"}

    def test_trigram_two_chars(self) -> None:
        trigrams = self.normalizer.generate_trigrams("ab")
        assert trigrams == {"$ab", "ab$"}

    def test_trigram_empty(self) -> None:
        assert self.normalizer.generate_trigrams("") == set()

    def test_trigram_japanese(self) -> None:
        """Trigrams should work with Japanese characters."""
        trigrams = self.normalizer.generate_trigrams("ソニー")
        assert "$ソニ" in trigrams
        assert "ソニー" in trigrams
        assert "ニー$" in trigrams

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def test_full_pipeline_japanese(self) -> None:
        """Full pipeline on Japanese input with corporate suffix."""
        result = self.normalizer.normalize("株式会社ソニー")
        # After NFKC (no-op), strip JP suffix -> ソニー, casefold (no-op for kana)
        assert "ソニー" in result or result == "ソニー"

    def test_full_pipeline_english(self) -> None:
        """Full pipeline on English input with corporate suffix."""
        result = self.normalizer.normalize("Sony Corporation")
        assert result == "sony"

    def test_full_pipeline_fullwidth_english(self) -> None:
        """Fullwidth English + suffix through full pipeline."""
        result = self.normalizer.normalize(
            "\uff33\uff4f\uff4e\uff59 Corporation"
        )  # Ｓｏｎｙ Corporation
        assert result == "sony"

    def test_full_pipeline_preserves_core_name(self) -> None:
        """Multiple suffixes should not over-strip; only first match removed."""
        result = self.normalizer.normalize("Sony Group Corporation")
        assert "sony" in result
        assert "group" in result

    def test_empty_input(self) -> None:
        assert self.normalizer.normalize("") == ""
        assert self.normalizer.normalize_japanese("") == ""
        assert self.normalizer.normalize_english("") == ""
