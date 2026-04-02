"""Phonetic key comparison strategy for entity matching."""

from __future__ import annotations

from entity_resolution.matching.base import MatchStrategy, StrategyResult


def _get_phonetic_encoder():
    """Lazy import of PhoneticEncoder to avoid circular dependencies.

    The PhoneticEncoder lives in ``entity_resolution.normalization.phonetic``
    which may import matching components.  Deferring the import to call time
    breaks any potential cycle.
    """
    from entity_resolution.normalization.phonetic import PhoneticEncoder

    return PhoneticEncoder()


class PhoneticStrategy(MatchStrategy):
    """Phonetic key comparison -- good for cross-language matching via romanization.

    Generates a phonetic key (e.g., Soundex) for each input string and then
    compares the keys character by character.  When two names produce identical
    phonetic keys, this strategy gives a perfect 1.0; partial matches yield
    proportional scores based on the fraction of matching positions.
    """

    def __init__(self, encoder=None):
        """Initialize with an optional phonetic encoder.

        Args:
            encoder: A ``PhoneticEncoder`` instance.  If *None*, a default
                encoder will be lazily created on first use.
        """
        self._encoder = encoder

    @property
    def _active_encoder(self):
        """Return the encoder, creating a default one lazily if needed."""
        if self._encoder is None:
            self._encoder = _get_phonetic_encoder()
        return self._encoder

    @property
    def name(self) -> str:
        return "phonetic"

    @property
    def weight(self) -> float:
        return 0.2

    def score(self, query: str, candidate: str) -> StrategyResult:
        """Compare phonetic keys of *query* and *candidate*.

        Both strings are encoded to phonetic keys, then compared position by
        position.  The score is the ratio of matching character positions to the
        total length of the longer key.

        If both keys are empty (e.g., empty inputs), the score is 1.0 for
        identical inputs and 0.0 otherwise.

        Returns:
            StrategyResult with score in [0.0, 1.0] and both phonetic keys in
            details.
        """
        encoder = self._active_encoder
        query_key = encoder.encode(query)
        candidate_key = encoder.encode(candidate)

        similarity = self._compare_keys(query_key, candidate_key)

        return StrategyResult(
            strategy_name=self.name,
            score=similarity,
            query_form=query,
            candidate_form=candidate,
            details={
                "query_phonetic_key": query_key,
                "candidate_phonetic_key": candidate_key,
            },
        )

    @staticmethod
    def _compare_keys(key_a: str, key_b: str) -> float:
        """Compare two phonetic keys character by character.

        Returns the fraction of positions that match, using the longer key's
        length as the denominator.

        Examples:
            ``('S500', 'S500')`` -> 1.0
            ``('S500', 'S530')`` -> 0.75
            ``('', '')`` -> 1.0
        """
        if not key_a and not key_b:
            return 1.0
        if not key_a or not key_b:
            return 0.0

        max_len = max(len(key_a), len(key_b))
        matches = sum(
            a == b for a, b in zip(key_a.ljust(max_len), key_b.ljust(max_len), strict=True)
        )
        return matches / max_len
