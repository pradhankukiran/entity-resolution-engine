"""Normalization and transliteration utilities for cross-language entity resolution."""

from entity_resolution.normalization.normalizer import TextNormalizer
from entity_resolution.normalization.language import LanguageDetector
from entity_resolution.normalization.transliterator import Transliterator
from entity_resolution.normalization.phonetic import PhoneticEncoder

__all__ = [
    "TextNormalizer",
    "LanguageDetector",
    "Transliterator",
    "PhoneticEncoder",
]
