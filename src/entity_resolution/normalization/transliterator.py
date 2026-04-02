"""Japanese-to-romaji transliteration using pykakasi.

Provides deterministic romanization of kanji, hiragana, and katakana text,
along with variant generation to improve cross-language entity matching.
"""

from __future__ import annotations

import re

import pykakasi


class Transliterator:
    """Convert Japanese text to romaji for cross-language matching."""

    # Long-vowel simplification rules for variant generation.
    # These capture the most common extended-vowel patterns in romanized Japanese.
    _LONG_VOWEL_RULES: list[tuple[str, str]] = [
        ("ou", "o"),
        ("oo", "o"),
        ("uu", "u"),
        ("ii", "i"),
        ("ei", "e"),
        ("ee", "e"),
        ("aa", "a"),
    ]

    def __init__(self) -> None:
        """Initialize the pykakasi converter."""
        self._kakasi = pykakasi.kakasi()

    def to_romaji(self, text: str) -> str:
        """Convert Japanese text to romaji.

        Uses the Hepburn romanization system via pykakasi.  The result is
        lowercased with tokens joined directly (no spaces) to produce a
        compact form suitable for entity matching.

        Args:
            text: Japanese input (kanji, hiragana, katakana, or mixed).

        Returns:
            Lowercased romanized string with no separating spaces.
        """
        if not text:
            return ""

        result = self._kakasi.convert(text)
        # Each item is a dict; 'hepburn' contains the romanized form
        parts: list[str] = []
        for item in result:
            hepburn = item.get("hepburn", item.get("passport", ""))
            if hepburn:
                parts.append(hepburn)

        return "".join(parts).lower()

    def to_romaji_variants(self, text: str) -> list[str]:
        """Generate multiple romanization variants for fuzzy matching.

        The base romanization often contains long-vowel sequences that may
        not appear in the commonly-used English spelling of a company name.
        For example, ``'ソニー'`` romanizes to ``'sonii'`` but is commonly
        written as ``'sony'``.

        This method produces:
            1. The raw Hepburn romanization
            2. A variant with all long-vowel pairs simplified
            3. Additional intermediate variants (one simplification at a time)

        Duplicate variants are removed while preserving order.

        Args:
            text: Japanese input text.

        Returns:
            Deduplicated list of romanization variants (lowercased, no spaces).
        """
        if not text:
            return []

        base = self.to_romaji(text)
        if not base:
            return []

        variants: list[str] = [base]

        # Apply all long-vowel simplifications at once for the "fully simplified" form
        fully_simplified = base
        for pattern, replacement in self._LONG_VOWEL_RULES:
            fully_simplified = fully_simplified.replace(pattern, replacement)

        if fully_simplified != base:
            variants.append(fully_simplified)

        # Generate intermediate variants: apply each rule individually
        for pattern, replacement in self._LONG_VOWEL_RULES:
            if pattern in base:
                single_variant = base.replace(pattern, replacement)
                if single_variant not in variants:
                    variants.append(single_variant)

        # Also strip trailing long vowels (e.g., 'sonii' -> 'soni')
        stripped = re.sub(r"([aiueo])\1+$", r"\1", base)
        if stripped not in variants:
            variants.append(stripped)

        return variants
