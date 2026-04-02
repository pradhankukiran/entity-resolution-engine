"""Matching strategies and ensemble scoring for entity resolution."""

from entity_resolution.matching.base import MatchStrategy, StrategyResult
from entity_resolution.matching.ensemble import EnsembleResult, EnsembleScorer
from entity_resolution.matching.jaro_winkler import JaroWinklerStrategy
from entity_resolution.matching.levenshtein import LevenshteinStrategy
from entity_resolution.matching.phonetic_match import PhoneticStrategy
from entity_resolution.matching.registry import StrategyRegistry
from entity_resolution.matching.token_sort import TokenSortStrategy

__all__ = [
    "EnsembleResult",
    "EnsembleScorer",
    "JaroWinklerStrategy",
    "LevenshteinStrategy",
    "MatchStrategy",
    "PhoneticStrategy",
    "StrategyRegistry",
    "StrategyResult",
    "TokenSortStrategy",
]
