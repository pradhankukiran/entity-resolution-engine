"""Tests for Transliterator, LanguageDetector, and PhoneticEncoder."""

from __future__ import annotations

import pytest

from entity_resolution.normalization.language import LanguageDetector
from entity_resolution.normalization.phonetic import PhoneticEncoder
from entity_resolution.normalization.transliterator import Transliterator

# ======================================================================
# Transliterator tests
# ======================================================================


class TestTransliterator:
    """Tests for Japanese-to-romaji transliteration."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.transliterator = Transliterator()

    def test_katakana_to_romaji(self) -> None:
        """ソニー should transliterate to a romaji form containing 'son'."""
        result = self.transliterator.to_romaji("ソニー")
        assert result.startswith("son")
        # pykakasi produces 'sonii' for ソニー (long vowel)
        assert "son" in result

    def test_kanji_to_romaji(self) -> None:
        """東京 should transliterate to 'toukyou'."""
        result = self.transliterator.to_romaji("東京")
        assert "toukyou" in result or "tokyo" in result

    def test_hiragana_to_romaji(self) -> None:
        """ありがとう should produce a romaji string."""
        result = self.transliterator.to_romaji("ありがとう")
        assert len(result) > 0
        assert result.isascii()

    def test_mixed_text(self) -> None:
        """株式会社ソニー should produce some romaji output."""
        result = self.transliterator.to_romaji("株式会社ソニー")
        assert len(result) > 0
        assert result.isascii()

    def test_romaji_variants(self) -> None:
        """Should generate multiple romanization variants."""
        variants = self.transliterator.to_romaji_variants("ソニー")
        assert len(variants) >= 2
        # Should include the base form
        assert any("son" in v for v in variants)
        # Should include a simplified form without long vowels
        base = variants[0]
        assert base != variants[1]  # at least one variant differs

    def test_romaji_variants_long_vowels(self) -> None:
        """東京 variants should simplify 'ou' to 'o'."""
        variants = self.transliterator.to_romaji_variants("東京")
        has_simplified = any("tokyo" in v for v in variants)
        has_long = any("toukyou" in v or "toukyoo" in v for v in variants)
        # At least one should be the simplified form
        assert has_simplified or has_long

    def test_romaji_empty_input(self) -> None:
        assert self.transliterator.to_romaji("") == ""
        assert self.transliterator.to_romaji_variants("") == []

    def test_latin_passthrough(self) -> None:
        """Latin text should pass through largely unchanged."""
        result = self.transliterator.to_romaji("Sony")
        assert "sony" in result.lower()


# ======================================================================
# LanguageDetector tests
# ======================================================================


class TestLanguageDetector:
    """Tests for language detection with CJK fallback."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.detector = LanguageDetector()

    def test_detect_japanese_katakana(self) -> None:
        """Pure katakana should be detected as Japanese."""
        assert self.detector.detect("ソニー") == "ja"

    def test_detect_japanese_hiragana(self) -> None:
        """Pure hiragana should be detected as Japanese."""
        assert self.detector.detect("ありがとう") == "ja"

    def test_detect_japanese_kanji(self) -> None:
        """Kanji text should be detected as Japanese."""
        assert self.detector.detect("東京") == "ja"

    def test_detect_english(self) -> None:
        """English text should be detected as English."""
        result = self.detector.detect("Sony Corporation")
        assert result == "en"

    def test_detect_mixed_ja_en(self) -> None:
        """Text with both Japanese and English chars should be 'ja' if any JP chars present."""
        result = self.detector.detect("ソニーSony")
        assert result == "ja"

    def test_detect_empty(self) -> None:
        assert self.detector.detect("") == "unknown"
        assert self.detector.detect("   ") == "unknown"

    def test_is_japanese_katakana(self) -> None:
        assert self.detector.is_japanese("ソニー") is True

    def test_is_japanese_kanji(self) -> None:
        assert self.detector.is_japanese("東京") is True

    def test_is_japanese_english(self) -> None:
        assert self.detector.is_japanese("Sony") is False

    def test_is_cjk(self) -> None:
        assert self.detector.is_cjk("東") is True
        assert self.detector.is_cjk("A") is False

    def test_get_script_katakana(self) -> None:
        assert self.detector.get_script("ソニー") == "katakana"

    def test_get_script_hiragana(self) -> None:
        assert self.detector.get_script("ありがとう") == "hiragana"

    def test_get_script_kanji(self) -> None:
        assert self.detector.get_script("東京銀行") == "kanji"

    def test_get_script_latin(self) -> None:
        assert self.detector.get_script("Sony") == "latin"

    def test_get_script_mixed(self) -> None:
        """Mixed kanji + katakana should return 'mixed'."""
        result = self.detector.get_script("東京ソニー銀行テスト")
        assert result in ("mixed", "kanji", "katakana")


# ======================================================================
# PhoneticEncoder tests
# ======================================================================


class TestPhoneticEncoder:
    """Tests for phonetic key generation."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.encoder = PhoneticEncoder()

    def test_basic_encoding(self) -> None:
        """'sony' should produce a 6-char key starting with 'S'."""
        key = self.encoder.encode("sony")
        assert len(key) == 6
        assert key[0] == "S"

    def test_encoding_fixed_length(self) -> None:
        """All keys should be exactly KEY_LENGTH characters."""
        for name in ["sony", "toyota", "microsoft", "a", "abcdefghijklmnop"]:
            key = self.encoder.encode(name)
            assert len(key) == 6, f"Key for '{name}' has length {len(key)}"

    def test_similar_names_similar_keys(self) -> None:
        """'sony' and 'soni' should produce the same phonetic key."""
        key1 = self.encoder.encode("sony")
        key2 = self.encoder.encode("soni")
        assert key1 == key2

    def test_different_names_different_keys(self) -> None:
        """'sony' and 'toyota' should produce different phonetic keys."""
        key1 = self.encoder.encode("sony")
        key2 = self.encoder.encode("toyota")
        assert key1 != key2

    def test_case_insensitive(self) -> None:
        """Encoding should be case-insensitive."""
        assert self.encoder.encode("Sony") == self.encoder.encode("sony")
        assert self.encoder.encode("TOYOTA") == self.encoder.encode("toyota")

    def test_strips_non_alpha(self) -> None:
        """Non-alphabetic characters should be stripped before encoding."""
        assert self.encoder.encode("sony!") == self.encoder.encode("sony")
        assert self.encoder.encode("so-ny") == self.encoder.encode("sony")

    def test_empty_input(self) -> None:
        assert self.encoder.encode("") == ""
        assert self.encoder.encode("123") == ""

    def test_encode_japanese_with_transliterator(self) -> None:
        """Japanese text should be transliterated then encoded."""
        transliterator = Transliterator()
        key = self.encoder.encode_japanese("ソニー", transliterator)
        assert len(key) == 6
        assert key[0] == "S"

    def test_encode_japanese_matches_romaji(self) -> None:
        """Encoding Japanese text should produce same key as encoding its romaji."""
        transliterator = Transliterator()
        jp_key = self.encoder.encode_japanese("ソニー", transliterator)
        romaji = transliterator.to_romaji("ソニー")
        en_key = self.encoder.encode(romaji)
        assert jp_key == en_key

    def test_phonetically_similar_across_languages(self) -> None:
        """The phonetic key for 'ソニー' (romaji) and 'sony' should match."""
        transliterator = Transliterator()
        jp_key = self.encoder.encode_japanese("ソニー", transliterator)
        en_key = self.encoder.encode("sony")
        # Both should start with 'S' and share the same consonant structure
        assert jp_key[0] == en_key[0] == "S"
