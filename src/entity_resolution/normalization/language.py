"""Language detection with CJK character-set fallback.

The ``langdetect`` library is unreliable on very short strings (< 10 chars) and
on strings that mix scripts. This module wraps langdetect with deterministic
Unicode-range heuristics so that any text containing hiragana or katakana is
always identified as Japanese.
"""

from __future__ import annotations

import unicodedata


class LanguageDetector:
    """Detect the language / script of short entity names."""

    # Unicode block boundaries (inclusive start, inclusive end)
    _HIRAGANA_RANGE = (0x3040, 0x309F)
    _KATAKANA_RANGE = (0x30A0, 0x30FF)
    _KATAKANA_EXT_RANGE = (0x31F0, 0x31FF)
    _CJK_UNIFIED_RANGE = (0x4E00, 0x9FFF)
    _CJK_EXT_A_RANGE = (0x3400, 0x4DBF)
    _CJK_EXT_B_RANGE = (0x20000, 0x2A6DF)
    _CJK_COMPAT_RANGE = (0xF900, 0xFAFF)
    _HALFWIDTH_KATAKANA_RANGE = (0xFF65, 0xFF9F)

    def detect(self, text: str) -> str:
        """Detect the primary language of *text*.

        Returns:
            ``'ja'`` for Japanese, ``'en'`` for English, or ``'unknown'``.

        Strategy:
            1. If the text contains **any** hiragana or katakana -> ``'ja'``.
            2. If the text contains CJK ideographs (kanji) but no kana, use
               ``langdetect`` to disambiguate Chinese vs Japanese; fall back
               to ``'ja'`` if langdetect is inconclusive.
            3. If the text is entirely Latin script, run ``langdetect`` and
               default to ``'en'`` on failure.
            4. Otherwise return ``'unknown'``.
        """
        if not text or not text.strip():
            return "unknown"

        has_kana = False
        has_cjk = False
        has_latin = False

        for ch in text:
            if self._is_hiragana(ch) or self._is_katakana(ch):
                has_kana = True
                break  # kana is conclusive
            if self.is_cjk(ch):
                has_cjk = True
            cat = unicodedata.category(ch)
            if cat.startswith("L") and self._is_latin(ch):
                has_latin = True

        # Rule 1: any kana -> Japanese
        if has_kana:
            return "ja"

        # Rule 2: CJK ideographs without kana
        if has_cjk:
            lang = self._try_langdetect(text)
            if lang in ("ja", "zh-cn", "zh-tw", "ko"):
                return lang if lang == "ja" else "ja"  # treat ambiguous CJK as ja
            return "ja"

        # Rule 3: Latin script – ask langdetect, default to English
        if has_latin:
            lang = self._try_langdetect(text)
            if lang and lang != "unknown":
                return lang
            return "en"

        return "unknown"

    def is_japanese(self, text: str) -> bool:
        """Return ``True`` if *text* contains any Japanese characters.

        Checks for hiragana, katakana, and CJK unified ideographs.
        """
        for ch in text:
            if self._is_hiragana(ch) or self._is_katakana(ch) or self.is_cjk(ch):
                return True
        return False

    def is_cjk(self, char: str) -> bool:
        """Return ``True`` if *char* falls within a CJK Unicode range."""
        cp = ord(char)
        return (
            self._CJK_UNIFIED_RANGE[0] <= cp <= self._CJK_UNIFIED_RANGE[1]
            or self._CJK_EXT_A_RANGE[0] <= cp <= self._CJK_EXT_A_RANGE[1]
            or self._CJK_EXT_B_RANGE[0] <= cp <= self._CJK_EXT_B_RANGE[1]
            or self._CJK_COMPAT_RANGE[0] <= cp <= self._CJK_COMPAT_RANGE[1]
        )

    def get_script(self, text: str) -> str:
        """Return the dominant script in *text*.

        Returns one of:
            ``'kanji'``, ``'hiragana'``, ``'katakana'``, ``'latin'``, ``'mixed'``
        """
        if not text or not text.strip():
            return "latin"

        counts: dict[str, int] = {
            "kanji": 0,
            "hiragana": 0,
            "katakana": 0,
            "latin": 0,
            "other": 0,
        }

        for ch in text:
            if ch.isspace() or unicodedata.category(ch).startswith("P"):
                continue  # skip whitespace and punctuation
            if self._is_hiragana(ch):
                counts["hiragana"] += 1
            elif self._is_katakana(ch):
                counts["katakana"] += 1
            elif self.is_cjk(ch):
                counts["kanji"] += 1
            elif self._is_latin(ch):
                counts["latin"] += 1
            else:
                counts["other"] += 1

        total_significant = sum(counts.values())
        if total_significant == 0:
            return "latin"

        # Find the dominant script
        dominant = max(counts, key=lambda k: counts[k])
        dominant_ratio = counts[dominant] / total_significant

        if dominant_ratio >= 0.8:
            return dominant if dominant != "other" else "mixed"

        return "mixed"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_hiragana(ch: str) -> bool:
        cp = ord(ch)
        return 0x3040 <= cp <= 0x309F

    @staticmethod
    def _is_katakana(ch: str) -> bool:
        cp = ord(ch)
        return (0x30A0 <= cp <= 0x30FF) or (0xFF65 <= cp <= 0xFF9F) or (0x31F0 <= cp <= 0x31FF)

    @staticmethod
    def _is_latin(ch: str) -> bool:
        cp = ord(ch)
        return (
            (0x0041 <= cp <= 0x005A)  # A-Z
            or (0x0061 <= cp <= 0x007A)  # a-z
            or (0x00C0 <= cp <= 0x024F)  # Latin Extended
        )

    @staticmethod
    def _try_langdetect(text: str) -> str:
        """Run langdetect, returning the ISO code or ``'unknown'`` on failure."""
        try:
            from langdetect import detect, DetectorFactory

            # Make langdetect deterministic
            DetectorFactory.seed = 0
            return detect(text)
        except Exception:
            return "unknown"
