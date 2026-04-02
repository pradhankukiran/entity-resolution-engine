"""Phonetic key generation for blocking in entity resolution.

Implements a Soundex-inspired encoding adapted for romanized Japanese company
names.  The encoding groups phonetically similar consonants together so that
minor transliteration differences (e.g., 'sony' vs 'soni') produce the same
blocking key.
"""

from __future__ import annotations

import re


class PhoneticEncoder:
    """Generate fixed-length phonetic keys for entity blocking."""

    # Consonant-to-digit mapping, adapted from Soundex but tuned for
    # romanized Japanese.  Vowels and H/W/Y are dropped (mapped to '0').
    _CHAR_MAP: dict[str, str] = {
        "b": "1",
        "f": "1",
        "p": "1",
        "v": "1",
        "c": "2",
        "g": "2",
        "j": "2",
        "k": "2",
        "q": "2",
        "s": "2",
        "x": "2",
        "z": "2",
        "d": "3",
        "t": "3",
        "l": "4",
        "r": "4",
        "m": "5",
        "n": "5",
        # Dropped (treated like vowels)
        "h": "0",
        "w": "0",
        "y": "0",
    }

    # Fixed output length for the phonetic key
    KEY_LENGTH: int = 6

    def encode(self, text: str) -> str:
        """Generate a phonetic key for *text*.

        Steps:
            1. Lowercase and strip non-alphabetic characters.
            2. Keep the first letter (uppercased) as-is.
            3. Map remaining characters to digit groups; drop vowels and H/W/Y.
            4. Collapse adjacent duplicate digits.
            5. Pad with '0' or truncate to ``KEY_LENGTH`` characters.

        Args:
            text: Input text (expected to be Latin/romanized).

        Returns:
            A fixed-length phonetic key string (e.g. ``'S500xx'``).
        """
        if not text:
            return ""

        # Step 1: lowercase and keep only alphabetic chars
        cleaned = re.sub(r"[^a-zA-Z]", "", text).lower()
        if not cleaned:
            return ""

        # Step 2: keep first letter (uppercased)
        first = cleaned[0].upper()

        # Step 3: map remaining chars to digit codes
        codes: list[str] = []
        for ch in cleaned[1:]:
            if ch in "aeiou":
                codes.append("0")  # vowels map to 0 (will be stripped)
            else:
                codes.append(self._CHAR_MAP.get(ch, "0"))

        # Step 4: collapse adjacent duplicates and drop zeros
        collapsed: list[str] = []
        prev = self._CHAR_MAP.get(cleaned[0], "0")  # code of the first letter
        for code in codes:
            if code == "0":
                prev = "0"  # reset adjacency on vowel/h/w/y
                continue
            if code != prev:
                collapsed.append(code)
            prev = code

        # Step 5: assemble, pad/truncate
        raw = first + "".join(collapsed)
        key = raw[: self.KEY_LENGTH].ljust(self.KEY_LENGTH, "0")

        return key

    def encode_japanese(self, text: str, transliterator: object) -> str:
        """Transliterate Japanese text to romaji, then generate a phonetic key.

        Args:
            text: Japanese text (kanji, kana, or mixed).
            transliterator: A ``Transliterator`` instance with a ``to_romaji`` method.

        Returns:
            A fixed-length phonetic key derived from the romanized text.
        """
        romaji = transliterator.to_romaji(text)  # type: ignore[union-attr]
        return self.encode(romaji)
