"""Company entity type configuration.

Extracts all company-specific data (field definitions, suffix lists,
form-pair mappings) into a single declarative config.
"""

from __future__ import annotations

from typing import Any

from entity_resolution.entity_types.config import EntityTypeConfig, FieldDef

# ------------------------------------------------------------------
# Corporate suffix lists (moved from normalizer.py)
# ------------------------------------------------------------------

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

# ------------------------------------------------------------------
# Form-pair mappings (moved from ensemble.py)
# ------------------------------------------------------------------

COMPANY_TEXT_PAIRS: list[tuple[str, str]] = [
    ("normalized", "name_normalized"),
    ("normalized", "en_name_normalized"),
    ("romaji", "name_romaji"),
    ("romaji", "en_name_normalized"),
    ("original", "name_normalized"),
]

COMPANY_PHONETIC_PAIRS: list[tuple[str, str]] = [
    ("phonetic", "phonetic_key"),
]


# ------------------------------------------------------------------
# Candidate form extractor
# ------------------------------------------------------------------


def company_candidate_forms(row: dict[str, Any]) -> dict[str, str]:
    """Convert a company DB row into the candidate_forms dict for scoring."""
    forms: dict[str, str] = {
        "name_normalized": row.get("name_normalized") or "",
    }
    if row.get("en_name_normalized"):
        forms["en_name_normalized"] = row["en_name_normalized"]
    if row.get("name_romaji"):
        forms["name_romaji"] = row["name_romaji"]
    if row.get("phonetic_key"):
        forms["phonetic_key"] = row["phonetic_key"]
    return forms


def company_query_to_candidate(forms: dict[str, str]) -> dict[str, str]:
    """Remap query-side forms into candidate-side keys for the compare API."""
    candidate: dict[str, str] = {}
    if "normalized" in forms:
        candidate["name_normalized"] = forms["normalized"]
        candidate["en_name_normalized"] = forms["normalized"]
    if "romaji" in forms:
        candidate["name_romaji"] = forms["romaji"]
    if "phonetic" in forms:
        candidate["phonetic_key"] = forms["phonetic"]
    return candidate


# ------------------------------------------------------------------
# Company entity type config
# ------------------------------------------------------------------

COMPANY_CONFIG = EntityTypeConfig(
    type_name="company",
    display_name="Company",
    table_name="companies",
    ngram_table_name="company_ngrams",
    id_column="company_id",
    db_fields=[
        FieldDef("corporate_number", "TEXT", nullable=False, unique=True),
        FieldDef("name", "TEXT", nullable=False),
        FieldDef("name_normalized", "TEXT", nullable=False),
        FieldDef("furigana", "TEXT"),
        FieldDef("en_name", "TEXT"),
        FieldDef("en_name_normalized", "TEXT"),
        FieldDef("name_romaji", "TEXT"),
        FieldDef("phonetic_key", "TEXT", indexed=True),
        FieldDef("prefecture_code", "TEXT"),
        FieldDef("city", "TEXT"),
        FieldDef("address", "TEXT"),
    ],
    display_name_field="name",
    ngram_source_fields=["name_normalized", "en_name_normalized", "name_romaji"],
    text_form_pairs=COMPANY_TEXT_PAIRS,
    phonetic_form_pairs=COMPANY_PHONETIC_PAIRS,
    suffix_lists={"ja": JP_SUFFIXES, "en": EN_SUFFIXES},
    candidate_form_extractor=company_candidate_forms,
    query_to_candidate_remapper=company_query_to_candidate,
)
