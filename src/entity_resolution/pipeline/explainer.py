"""Step-by-step explanation builder for entity resolution pipeline.

Each stage of the pipeline records what it did so that API consumers can
understand *why* a particular match was returned and with what confidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class ExplanationStep:
    """A single recorded step in the resolution pipeline.

    Attributes:
        step: Machine-readable stage identifier, e.g. ``"language_detection"``.
        description: Human-readable summary of what happened.
        input_value: The value fed into this stage (may be ``None``).
        output_value: The value produced by this stage (may be ``None``).
        details: Arbitrary key/value metadata specific to the stage.
    """

    step: str
    description: str
    input_value: str | None = None
    output_value: str | None = None
    details: dict = field(default_factory=dict)


class ExplanationBuilder:
    """Accumulates :class:`ExplanationStep` instances as the pipeline runs.

    Usage::

        builder = ExplanationBuilder()
        builder.add_language_detection("ソニー", "ja", "katakana")
        builder.add_normalization("ソニー株式会社", "ソニー", ["株式会社"])
        steps = builder.build()
    """

    def __init__(self) -> None:
        self._steps: list[ExplanationStep] = []

    # ------------------------------------------------------------------
    # Generic step
    # ------------------------------------------------------------------

    def add_step(
        self,
        step: str,
        description: str,
        input_value: str | None = None,
        output_value: str | None = None,
        **details: object,
    ) -> None:
        """Add an arbitrary explanation step."""
        self._steps.append(
            ExplanationStep(
                step=step,
                description=description,
                input_value=input_value,
                output_value=output_value,
                details=dict(details),
            )
        )

    # ------------------------------------------------------------------
    # Domain-specific convenience methods
    # ------------------------------------------------------------------

    def add_language_detection(self, query: str, detected_lang: str, script: str) -> None:
        """Record language detection result."""
        self._steps.append(
            ExplanationStep(
                step="language_detection",
                description=f"Detected language '{detected_lang}' (script: {script})",
                input_value=query,
                output_value=detected_lang,
                details={"script": script},
            )
        )

    def add_normalization(
        self, original: str, normalized: str, suffixes_removed: list[str]
    ) -> None:
        """Record normalization result."""
        suffix_info = f", removed suffixes: {suffixes_removed}" if suffixes_removed else ""
        self._steps.append(
            ExplanationStep(
                step="normalization",
                description=f"Normalized text{suffix_info}",
                input_value=original,
                output_value=normalized,
                details={"suffixes_removed": suffixes_removed},
            )
        )

    def add_transliteration(self, original: str, romaji: str, variants: list[str]) -> None:
        """Record transliteration result."""
        self._steps.append(
            ExplanationStep(
                step="transliteration",
                description=f"Transliterated to romaji with {len(variants)} variant(s)",
                input_value=original,
                output_value=romaji,
                details={"variants": variants},
            )
        )

    def add_phonetic_encoding(self, text: str, phonetic_key: str) -> None:
        """Record phonetic encoding result."""
        self._steps.append(
            ExplanationStep(
                step="phonetic_encoding",
                description=f"Generated phonetic key '{phonetic_key}'",
                input_value=text,
                output_value=phonetic_key,
                details={},
            )
        )

    def add_blocking(
        self,
        trigram_candidates: int,
        phonetic_candidates: int,
        total_unique: int,
    ) -> None:
        """Record candidate blocking results."""
        self._steps.append(
            ExplanationStep(
                step="blocking",
                description=(
                    f"Blocking retrieved {total_unique} unique candidates "
                    f"(trigram: {trigram_candidates}, phonetic: {phonetic_candidates})"
                ),
                input_value=None,
                output_value=str(total_unique),
                details={
                    "trigram_candidates": trigram_candidates,
                    "phonetic_candidates": phonetic_candidates,
                    "total_unique": total_unique,
                },
            )
        )

    def add_scoring(
        self,
        candidate_name: str,
        final_score: float,
        strategy_scores: dict[str, float],
    ) -> None:
        """Record scoring for a candidate."""
        self._steps.append(
            ExplanationStep(
                step="scoring",
                description=(f"Scored '{candidate_name}' -> {final_score:.4f}"),
                input_value=candidate_name,
                output_value=f"{final_score:.4f}",
                details={"strategy_scores": strategy_scores},
            )
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def build(self) -> list[ExplanationStep]:
        """Return a copy of all accumulated steps."""
        return list(self._steps)

    def to_dict_list(self) -> list[dict]:
        """Convert to a list of plain dicts suitable for JSON serialization."""
        return [asdict(s) for s in self._steps]
