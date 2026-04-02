"""Candidate blocking for entity resolution.

Blocking is the first coarse-grained filtering step that narrows a potentially
large set of companies (100k+) down to a manageable candidate set (~200) before
the more expensive scoring stage runs.  Two complementary strategies are used:

1. **Trigram overlap** -- query character trigrams are matched against the
   ``company_ngrams`` table.  Companies sharing the most trigrams with the
   query rise to the top.
2. **Phonetic key** -- an exact or prefix match on the Soundex-style phonetic
   key catches candidates that *sound* similar but may differ in spelling.

The results from both strategies are unioned and deduplicated.
"""

from __future__ import annotations

from entity_resolution.db import queries
from entity_resolution.db.database import Database
from entity_resolution.db.query_builder import build_search_by_ngrams, build_search_by_phonetic
from entity_resolution.entity_types.config import EntityTypeConfig
from entity_resolution.normalization.normalizer import TextNormalizer


class CandidateBlocker:
    """Retrieves candidate entities using trigram index and phonetic keys."""

    def __init__(
        self,
        db: Database,
        trigram_limit: int = 200,
        phonetic_limit: int = 100,
        entity_config: EntityTypeConfig | None = None,
    ) -> None:
        self._db = db
        self._trigram_limit = trigram_limit
        self._phonetic_limit = phonetic_limit
        self._normalizer = TextNormalizer()
        self._entity_config = entity_config

    async def get_candidates(self, query_forms: dict[str, str]) -> list[int]:
        """Get candidate company IDs using multiple blocking strategies.

        Args:
            query_forms: Dict with keys like ``'normalized'``, ``'romaji'``,
                ``'phonetic'``.

        Returns:
            Deduplicated list of company IDs ordered by first appearance.

        Strategy:
            1. Generate trigrams from both ``normalized`` and ``romaji`` forms.
            2. Query ``company_ngrams`` for matching trigrams.
            3. Query ``companies`` by phonetic key (exact + prefix).
            4. Union all candidate IDs and deduplicate, preserving order.
        """
        seen: set[int] = set()
        ordered: list[int] = []

        def _extend(ids: list[int]) -> None:
            for cid in ids:
                if cid not in seen:
                    seen.add(cid)
                    ordered.append(cid)

        # Trigram blocking on the normalized form
        normalized = query_forms.get("normalized", "")
        if normalized:
            _extend(await self._trigram_block(normalized))

        # Trigram blocking on the romaji form (may differ from normalized)
        romaji = query_forms.get("romaji", "")
        if romaji and romaji != normalized:
            _extend(await self._trigram_block(romaji))

        # Phonetic key blocking
        phonetic = query_forms.get("phonetic", "")
        if phonetic:
            _extend(await self._phonetic_block(phonetic))

        return ordered

    async def _trigram_block(self, text: str) -> list[int]:
        """Find candidates by trigram overlap."""
        trigrams = self._normalizer.generate_trigrams(text)
        if not trigrams:
            return []

        trigram_list = list(trigrams)

        if self._entity_config is not None:
            sql = build_search_by_ngrams(self._entity_config, len(trigram_list))
            id_col = self._entity_config.id_column
        else:
            placeholders = ", ".join("?" for _ in trigram_list)
            sql = queries.SEARCH_BY_NGRAMS.format(placeholders=placeholders)
            id_col = "company_id"

        params = [*trigram_list, self._trigram_limit]
        rows = await self._db.fetch_all(sql, params)
        return [row[id_col] for row in rows]

    async def _phonetic_block(self, phonetic_key: str) -> list[int]:
        """Find candidates by phonetic key match."""
        if not phonetic_key:
            return []

        prefix = phonetic_key[:4] if len(phonetic_key) >= 4 else phonetic_key
        params = [phonetic_key, prefix, self._phonetic_limit]

        if self._entity_config is not None:
            sql = build_search_by_phonetic(self._entity_config)
            id_col = self._entity_config.id_column
        else:
            sql = queries.SEARCH_BY_PHONETIC_KEY
            id_col = "company_id"

        rows = await self._db.fetch_all(sql, params)
        return [row[id_col] for row in rows]
