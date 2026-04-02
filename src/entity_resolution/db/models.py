"""Data models for database entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Company:
    """Represents a single company record from the database."""

    id: int
    corporate_number: str
    name: str
    name_normalized: str
    furigana: str | None
    en_name: str | None
    en_name_normalized: str | None
    name_romaji: str | None
    phonetic_key: str | None
    prefecture_code: str | None
    city: str | None
    address: str | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Company:
        """Construct a Company from a database row dict."""
        return cls(
            id=row["id"],
            corporate_number=row["corporate_number"],
            name=row["name"],
            name_normalized=row["name_normalized"],
            furigana=row.get("furigana"),
            en_name=row.get("en_name"),
            en_name_normalized=row.get("en_name_normalized"),
            name_romaji=row.get("name_romaji"),
            phonetic_key=row.get("phonetic_key"),
            prefecture_code=row.get("prefecture_code"),
            city=row.get("city"),
            address=row.get("address"),
        )


@dataclass
class CompanyNgram:
    """Represents an ngram entry linked to a company."""

    id: int
    company_id: int
    ngram: str
    source_field: str
