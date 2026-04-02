"""Main entity resolution pipeline orchestrator.

The :class:`ResolutionPipeline` ties together every stage of the resolution
flow -- language detection, normalization, transliteration, phonetic encoding,
blocking, and ensemble scoring -- into a single ``resolve()`` call that accepts
a query string and returns ranked, explained matches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from entity_resolution.core.config import Settings
from entity_resolution.db.database import Database
from entity_resolution.db.models import Company
from entity_resolution.db import queries
from entity_resolution.matching.base import StrategyResult
from entity_resolution.matching.ensemble import EnsembleResult, EnsembleScorer
from entity_resolution.matching.registry import StrategyRegistry
from entity_resolution.normalization.language import LanguageDetector
from entity_resolution.normalization.normalizer import TextNormalizer
from entity_resolution.normalization.phonetic import PhoneticEncoder
from entity_resolution.normalization.transliterator import Transliterator
from entity_resolution.pipeline.blocker import CandidateBlocker
from entity_resolution.pipeline.explainer import ExplanationBuilder


# ------------------------------------------------------------------
# Result data classes
# ------------------------------------------------------------------


@dataclass
class MatchResult:
    """A single scored match returned by the pipeline."""

    company: Company
    score: float
    rank: int
    ensemble_result: EnsembleResult
    explanations: list[dict] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Full pipeline output for a resolution query."""

    query: str
    detected_language: str
    query_forms: dict[str, str]
    matches: list[MatchResult]
    total_candidates: int
    processing_steps: list[dict]


# ------------------------------------------------------------------
# Pipeline
# ------------------------------------------------------------------


class ResolutionPipeline:
    """Orchestrates the full entity resolution flow.

    Usage::

        pipeline = ResolutionPipeline(db, settings)
        result = await pipeline.resolve("ソニー株式会社")
        for m in result.matches:
            print(m.company.name, m.score)
    """

    def __init__(self, db: Database, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._normalizer = TextNormalizer()
        self._detector = LanguageDetector()
        self._transliterator = Transliterator()
        self._encoder = PhoneticEncoder()
        self._registry = StrategyRegistry.default()
        self._scorer = EnsembleScorer(self._registry)
        self._blocker = CandidateBlocker(
            db,
            settings.trigram_candidate_limit,
            settings.phonetic_candidate_limit,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def resolve(self, query: str, limit: int = 10) -> PipelineResult:
        """Execute the full resolution pipeline.

        Steps:
            1. Detect language of the query.
            2. Normalize the query text.
            3. Transliterate to romaji (if Japanese).
            4. Generate a phonetic key.
            5. Build a ``query_forms`` dict for downstream stages.
            6. Retrieve candidate IDs via blocking.
            7. Fetch ``Company`` objects for those IDs.
            8. Score each candidate with the ensemble scorer.
            9. Sort by score descending, apply threshold, limit.
            10. Build per-candidate explanations.
            11. Return :class:`PipelineResult`.

        Args:
            query: The raw company name to resolve.
            limit: Maximum number of matches to return.

        Returns:
            A :class:`PipelineResult` with ranked matches and explanations.
        """
        explanation = ExplanationBuilder()

        # 1-4. Build all query forms (language, normalization, romaji, phonetic)
        query_forms = self._build_query_forms(query, explanation)
        detected_language = query_forms.get("language", "unknown")

        # 5. Blocking: retrieve candidate IDs
        candidate_ids = await self._blocker.get_candidates(query_forms)

        # Track blocking stats for the explanation
        explanation.add_blocking(
            trigram_candidates=len(candidate_ids),  # upper bound
            phonetic_candidates=0,  # not tracked separately here
            total_unique=len(candidate_ids),
        )

        total_candidates = len(candidate_ids)

        # 6. Fetch full Company objects
        companies = await self._fetch_companies(candidate_ids)

        # 7. Score each candidate
        scored: list[tuple[Company, EnsembleResult]] = []
        for company in companies:
            ensemble_result = self._score_candidate(query_forms, company)
            if ensemble_result.final_score >= self._settings.min_score_threshold:
                scored.append((company, ensemble_result))

        # 8. Sort by score descending
        scored.sort(key=lambda pair: pair[1].final_score, reverse=True)

        # 9. Limit
        scored = scored[:limit]

        # 10. Build match results with explanations
        matches: list[MatchResult] = []
        for rank, (company, ensemble_result) in enumerate(scored, start=1):
            strategy_scores = {
                sr.strategy_name: sr.score
                for sr in ensemble_result.strategy_results
            }
            explanation.add_scoring(
                candidate_name=company.name,
                final_score=ensemble_result.final_score,
                strategy_scores=strategy_scores,
            )
            matches.append(
                MatchResult(
                    company=company,
                    score=ensemble_result.final_score,
                    rank=rank,
                    ensemble_result=ensemble_result,
                    explanations=explanation.to_dict_list(),
                )
            )

        return PipelineResult(
            query=query,
            detected_language=detected_language,
            query_forms=query_forms,
            matches=matches,
            total_candidates=total_candidates,
            processing_steps=explanation.to_dict_list(),
        )

    async def compare(self, name_a: str, name_b: str) -> dict:
        """Direct comparison of two names without DB lookup.

        Builds normalized forms for both names, runs the ensemble scorer
        across every registered strategy, and returns a detailed breakdown.
        This is used by the ``/match`` endpoint.

        Args:
            name_a: First name to compare.
            name_b: Second name to compare.

        Returns:
            Dict with ``final_score``, per-strategy scores, and form info.
        """
        explanation_a = ExplanationBuilder()
        explanation_b = ExplanationBuilder()

        forms_a = self._build_query_forms(name_a, explanation_a)
        forms_b = self._build_query_forms(name_b, explanation_b)

        # Build query_forms dict in the schema the EnsembleScorer expects:
        #   query side:     {original, normalized, romaji, phonetic}
        #   candidate side: {name_normalized, en_name_normalized, name_romaji, phonetic_key}
        # We treat name_b as the "candidate" so we remap its forms.
        candidate_forms = self._remap_as_candidate_forms(forms_b)

        result = self._scorer.score(forms_a, candidate_forms)

        strategy_scores = {
            sr.strategy_name: sr.score for sr in result.strategy_results
        }

        return {
            "name_a": name_a,
            "name_b": name_b,
            "forms_a": forms_a,
            "forms_b": forms_b,
            "final_score": result.final_score,
            "strategy_scores": strategy_scores,
            "strategy_details": [
                {
                    "strategy": sr.strategy_name,
                    "score": sr.score,
                    "query_form": sr.query_form,
                    "candidate_form": sr.candidate_form,
                    "details": sr.details,
                }
                for sr in result.strategy_results
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_query_forms(
        self, query: str, explanation: ExplanationBuilder
    ) -> dict[str, str]:
        """Build the query forms dict based on detected language.

        For Japanese:
            - ``original``: raw query
            - ``normalized``: strip JP suffixes, NFKC
            - ``romaji``: transliterate to romaji
            - ``phonetic``: phonetic key from romaji

        For English / other:
            - ``original``: raw query
            - ``normalized``: case fold, strip EN suffixes
            - ``romaji``: same as normalized (already Latin)
            - ``phonetic``: phonetic key from normalized
        """
        # Step 1: Detect language
        lang = self._detector.detect(query)
        script = self._detector.get_script(query)
        explanation.add_language_detection(query, lang, script)

        forms: dict[str, str] = {"original": query, "language": lang}

        if lang == "ja":
            # Japanese path
            normalized = self._normalizer.normalize_japanese(query)
            suffixes_found = self._detect_removed_suffixes(
                query, normalized, self._normalizer.JP_SUFFIXES
            )
            explanation.add_normalization(query, normalized, suffixes_found)
            forms["normalized"] = normalized

            # Transliterate
            romaji = self._transliterator.to_romaji(normalized)
            variants = self._transliterator.to_romaji_variants(normalized)
            explanation.add_transliteration(normalized, romaji, variants)
            forms["romaji"] = romaji
            forms["variants"] = ",".join(variants) if variants else romaji

            # Phonetic key from romaji
            phonetic = self._encoder.encode(romaji)
            explanation.add_phonetic_encoding(romaji, phonetic)
            forms["phonetic"] = phonetic
        else:
            # English / other path
            normalized = self._normalizer.normalize(query)
            suffixes_found = self._detect_removed_suffixes(
                query, normalized, self._normalizer.EN_SUFFIXES
            )
            explanation.add_normalization(query, normalized, suffixes_found)
            forms["normalized"] = normalized

            # No transliteration needed; romaji == normalized
            forms["romaji"] = normalized

            # Phonetic key from normalized
            phonetic = self._encoder.encode(normalized)
            explanation.add_phonetic_encoding(normalized, phonetic)
            forms["phonetic"] = phonetic

        return forms

    def _score_candidate(
        self, query_forms: dict[str, str], company: Company
    ) -> EnsembleResult:
        """Score a single candidate against all query forms.

        Builds a candidate forms dict from the :class:`Company` fields using
        the key names that the :class:`EnsembleScorer` expects, then delegates
        to the scorer which tries all compatible form pairs internally.
        """
        candidate_forms = self._company_to_candidate_forms(company)
        return self._scorer.score(query_forms, candidate_forms)

    @staticmethod
    def _company_to_candidate_forms(company: Company) -> dict[str, str]:
        """Convert a Company into the candidate_forms dict expected by the scorer.

        The ensemble scorer looks for these keys on the candidate side:
            - ``name_normalized``
            - ``en_name_normalized``
            - ``name_romaji``
            - ``phonetic_key``
        """
        forms: dict[str, str] = {
            "name_normalized": company.name_normalized or "",
        }
        if company.en_name_normalized:
            forms["en_name_normalized"] = company.en_name_normalized
        if company.name_romaji:
            forms["name_romaji"] = company.name_romaji
        if company.phonetic_key:
            forms["phonetic_key"] = company.phonetic_key
        return forms

    @staticmethod
    def _remap_as_candidate_forms(forms: dict[str, str]) -> dict[str, str]:
        """Remap a query-style forms dict into the candidate-side key schema.

        Used by :meth:`compare` to treat the second name as a "candidate"
        so the ensemble scorer's form-pair logic works correctly.
        """
        candidate: dict[str, str] = {}
        if "normalized" in forms:
            candidate["name_normalized"] = forms["normalized"]
            candidate["en_name_normalized"] = forms["normalized"]
        if "romaji" in forms:
            candidate["name_romaji"] = forms["romaji"]
        if "phonetic" in forms:
            candidate["phonetic_key"] = forms["phonetic"]
        return candidate

    async def _fetch_companies(self, company_ids: list[int]) -> list[Company]:
        """Fetch :class:`Company` objects by IDs.

        Uses a single ``IN (...)`` query for efficiency and preserves the
        original ordering of *company_ids*.
        """
        if not company_ids:
            return []

        placeholders = ", ".join("?" for _ in company_ids)
        sql = queries.GET_COMPANIES_BY_IDS.format(placeholders=placeholders)
        rows = await self._db.fetch_all(sql, company_ids)

        # Build a lookup so we can re-order to match the input order
        by_id: dict[int, Company] = {}
        for row in rows:
            company = Company.from_row(row)
            by_id[company.id] = company

        return [by_id[cid] for cid in company_ids if cid in by_id]

    @staticmethod
    def _detect_removed_suffixes(
        original: str, normalized: str, suffix_list: list[str]
    ) -> list[str]:
        """Determine which corporate suffixes were removed during normalization.

        Compares the original text against the suffix list to find which ones
        were present and stripped.
        """
        removed: list[str] = []
        lower_original = original.casefold()
        for suffix in suffix_list:
            sf = suffix.casefold()
            if sf in lower_original and sf not in normalized.casefold():
                removed.append(suffix)
        return removed
