"""Text normalization for entity resolution across English and Japanese."""

from __future__ import annotations

import re
import unicodedata


class TextNormalizer:
    """Normalize entity names for cross-language resolution.

    The pipeline applies: NFKC unicode normalization, suffix stripping,
    case folding, and whitespace collapsing.

    Suffix lists are injectable per entity type.  When not provided, the
    default corporate suffixes are used for backward compatibility.
    """

    # Default corporate suffixes (kept for backward compat; canonical
    # versions now live in entity_types/company.py).
    JP_SUFFIXES: list[str] = [
        "特定非営利活動法人",
        "公益社団法人",
        "公益財団法人",
        "一般社団法人",
        "一般財団法人",
        "社会福祉法人",
        "株式会社",
        "有限会社",
        "合同会社",
        "合資会社",
        "合名会社",
        "医療法人",
    ]

    EN_SUFFIXES: list[str] = [
        "kabushiki kaisha",
        "incorporated",
        "corporation",
        "l.l.c.",
        "company",
        "limited",
        "corp.",
        "corp",
        "inc.",
        "inc",
        "ltd.",
        "ltd",
        "gmbh",
        "k.k.",
        "llc",
        "plc",
        "co.",
        "co",
        "ag",
        "bv",
        "kk",
        "nv",
        "sa",
    ]

    # Pre-compiled pattern for collapsing whitespace
    _ws_re = re.compile(r"\s+")

    def __init__(
        self,
        jp_suffixes: list[str] | None = None,
        en_suffixes: list[str] | None = None,
    ) -> None:
        self._jp_suffixes = jp_suffixes if jp_suffixes is not None else self.JP_SUFFIXES
        self._en_suffixes = en_suffixes if en_suffixes is not None else self.EN_SUFFIXES

    def normalize(self, text: str) -> str:
        """Full normalization pipeline.

        Steps:
            1. NFKC unicode normalization (fullwidth -> ASCII, etc.)
            2. Strip Japanese corporate suffixes (prefix and suffix positions)
            3. Case fold to lowercase
            4. Strip English corporate suffixes
            5. Collapse and strip whitespace

        Returns:
            The normalized text string.
        """
        if not text:
            return ""

        # Step 1: NFKC normalization (Ｓｏｎｙ -> Sony, etc.)
        result = unicodedata.normalize("NFKC", text)

        # Step 2: Strip Japanese suffixes
        result = self.strip_suffixes(result, self._jp_suffixes)

        # Step 3: Case fold
        result = result.casefold()

        # Step 4: Strip English suffixes (after casefolding)
        result = self.strip_suffixes(result, self._en_suffixes)

        # Step 5: Whitespace collapse and strip
        result = self._ws_re.sub(" ", result).strip()

        return result

    def normalize_japanese(self, text: str) -> str:
        """Japanese-specific normalization.

        Steps:
            1. NFKC normalization
            2. Strip Japanese corporate suffixes (both prefix and suffix positions)
            3. Strip all whitespace
        """
        if not text:
            return ""

        result = unicodedata.normalize("NFKC", text)
        result = self.strip_suffixes(result, self._jp_suffixes)
        # For Japanese text, strip all whitespace (JP doesn't use word spaces)
        result = self._ws_re.sub("", result).strip()

        return result

    def normalize_english(self, text: str) -> str:
        """English-specific normalization.

        Steps:
            1. Case fold to lowercase
            2. Strip English corporate suffixes
            3. Collapse whitespace
        """
        if not text:
            return ""

        result = text.casefold()
        result = self.strip_suffixes(result, self._en_suffixes)
        result = self._ws_re.sub(" ", result).strip()

        return result

    def strip_suffixes(self, text: str, suffixes: list[str]) -> str:
        """Remove corporate suffixes from text.

        Handles both prefix and suffix positions. For example, Japanese
        corporate forms can appear as either '株式会社ソニー' (prefix) or
        'ソニー株式会社' (suffix).

        The method iterates suffixes (ordered longest-first) and removes
        the first match found at either end of the string.

        Args:
            text: The input text to strip.
            suffixes: List of suffixes to remove.

        Returns:
            Text with the first matching suffix removed, stripped of surrounding whitespace.
        """
        if not text:
            return ""

        stripped = text.strip()
        lower = stripped.casefold()

        for suffix in suffixes:
            sf_lower = suffix.casefold()
            sf_len = len(sf_lower)

            # Check suffix position (end of string)
            if lower.endswith(sf_lower):
                candidate = stripped[: len(stripped) - sf_len].strip()
                if candidate:
                    return candidate

            # Check prefix position (start of string)
            if lower.startswith(sf_lower):
                candidate = stripped[sf_len:].strip()
                if candidate:
                    return candidate

        return stripped

    def generate_trigrams(self, text: str) -> set[str]:
        """Generate character trigrams from normalized text.

        Pads the text with '$' boundary markers so that the start and end
        of the string produce distinctive trigrams.

        Example:
            'sony' -> {'$so', 'son', 'ony', 'ny$'}

        Args:
            text: Input text (should be pre-normalized for best results).

        Returns:
            A set of 3-character trigram strings.
        """
        if not text:
            return set()

        padded = f"${text}$"
        return {padded[i : i + 3] for i in range(len(padded) - 2)}
