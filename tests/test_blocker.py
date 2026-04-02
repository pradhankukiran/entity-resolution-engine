"""Tests for the candidate blocker."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from entity_resolution.pipeline.blocker import CandidateBlocker


class TestCandidateBlocker:
    """Tests for CandidateBlocker trigram and phonetic blocking."""

    @pytest.mark.asyncio
    async def test_trigram_block_queries_db(self):
        """Should query DB with trigrams and return company IDs."""
        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            return_value=[
                {"company_id": 1, "match_count": 5},
                {"company_id": 2, "match_count": 3},
                {"company_id": 3, "match_count": 2},
            ]
        )

        blocker = CandidateBlocker(mock_db)
        ids = await blocker._trigram_block("sony")

        assert mock_db.fetch_all.called
        assert ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_trigram_block_empty_text(self):
        """Empty text should return no candidates."""
        mock_db = AsyncMock()
        blocker = CandidateBlocker(mock_db)

        ids = await blocker._trigram_block("")

        assert ids == []
        mock_db.fetch_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_phonetic_block_queries_db(self):
        """Should query DB by phonetic key and return company IDs."""
        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            return_value=[
                {"company_id": 4},
                {"company_id": 5},
            ]
        )

        blocker = CandidateBlocker(mock_db)
        ids = await blocker._phonetic_block("S50000")

        assert mock_db.fetch_all.called
        assert ids == [4, 5]

    @pytest.mark.asyncio
    async def test_phonetic_block_empty_key(self):
        """Empty phonetic key should return no candidates."""
        mock_db = AsyncMock()
        blocker = CandidateBlocker(mock_db)

        ids = await blocker._phonetic_block("")

        assert ids == []
        mock_db.fetch_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_candidates_deduplicates(self):
        """Combined results should be deduplicated while preserving order."""
        mock_db = AsyncMock()
        # First call: trigram block for 'normalized' -> IDs 1, 2, 3
        # Second call: trigram block for 'romaji' -> IDs 2, 4
        # Third call: phonetic block -> IDs 3, 5
        mock_db.fetch_all = AsyncMock(
            side_effect=[
                [
                    {"company_id": 1, "match_count": 5},
                    {"company_id": 2, "match_count": 3},
                    {"company_id": 3, "match_count": 2},
                ],
                [
                    {"company_id": 2, "match_count": 4},
                    {"company_id": 4, "match_count": 2},
                ],
                [
                    {"company_id": 3},
                    {"company_id": 5},
                ],
            ]
        )

        blocker = CandidateBlocker(mock_db)
        ids = await blocker.get_candidates(
            {
                "normalized": "sony",
                "romaji": "sonii",
                "phonetic": "S50000",
            }
        )

        # Should be deduplicated: 1, 2, 3 from first; 4 from second; 5 from third
        assert len(ids) == len(set(ids))
        assert set(ids) == {1, 2, 3, 4, 5}

    @pytest.mark.asyncio
    async def test_get_candidates_preserves_order(self):
        """First-seen order should be preserved across blocking strategies."""
        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            side_effect=[
                [
                    {"company_id": 10, "match_count": 8},
                    {"company_id": 20, "match_count": 5},
                ],
                [
                    {"company_id": 30},
                ],
            ]
        )

        blocker = CandidateBlocker(mock_db)
        ids = await blocker.get_candidates(
            {
                "normalized": "test",
                "romaji": "test",  # same as normalized, second trigram skipped
                "phonetic": "T23000",
            }
        )

        assert ids == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_get_candidates_skips_duplicate_trigram_call(self):
        """When romaji == normalized, only one trigram query should run."""
        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(
            side_effect=[
                [{"company_id": 1, "match_count": 3}],  # trigram for normalized
                [{"company_id": 2}],  # phonetic
            ]
        )

        blocker = CandidateBlocker(mock_db)
        ids = await blocker.get_candidates(
            {
                "normalized": "honda",
                "romaji": "honda",  # identical to normalized
                "phonetic": "H53000",
            }
        )

        # fetch_all called 2 times: trigram + phonetic (not 3)
        assert mock_db.fetch_all.call_count == 2
        assert set(ids) == {1, 2}

    @pytest.mark.asyncio
    async def test_get_candidates_empty_forms(self):
        """Empty query forms should return no candidates."""
        mock_db = AsyncMock()
        blocker = CandidateBlocker(mock_db)

        ids = await blocker.get_candidates({})

        assert ids == []
        mock_db.fetch_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_limits(self):
        """Custom trigram and phonetic limits should be passed through."""
        mock_db = AsyncMock()
        mock_db.fetch_all = AsyncMock(return_value=[])

        blocker = CandidateBlocker(mock_db, trigram_limit=50, phonetic_limit=25)

        await blocker.get_candidates(
            {"normalized": "test", "romaji": "test", "phonetic": "T23000"}
        )

        # First call is the trigram query; last param is the limit
        first_call_args = mock_db.fetch_all.call_args_list[0]
        params = first_call_args[0][1]  # second positional arg = parameters
        assert params[-1] == 50  # trigram limit

        # Second call is the phonetic query
        second_call_args = mock_db.fetch_all.call_args_list[1]
        params = second_call_args[0][1]
        assert params[-1] == 25  # phonetic limit
