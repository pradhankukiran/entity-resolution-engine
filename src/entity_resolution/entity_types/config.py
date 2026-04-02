"""Entity type configuration and generic entity record.

Each entity type (company, person, product, etc.) is described by an
:class:`EntityTypeConfig` that declares its database schema, form-pair
mappings for the ensemble scorer, suffix lists for normalization, and a
function to extract candidate forms from a raw DB row.

:class:`EntityRecord` is the generic runtime representation of any entity
loaded from the database -- it wraps a ``dict`` and delegates field access
to the underlying row data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, NamedTuple

# ------------------------------------------------------------------
# Field definition for schema generation
# ------------------------------------------------------------------


class FieldDef(NamedTuple):
    """Column definition for an entity table.

    Attributes:
        name: Column name.
        sql_type: SQLite column type (TEXT, INTEGER, etc.).
        nullable: Whether the column allows NULL.
        indexed: Whether to create a standalone index on this column.
        unique: Whether to add a UNIQUE constraint.
    """

    name: str
    sql_type: str = "TEXT"
    nullable: bool = True
    indexed: bool = False
    unique: bool = False


# ------------------------------------------------------------------
# Entity type configuration
# ------------------------------------------------------------------


@dataclass(frozen=True)
class EntityTypeConfig:
    """Declarative description of an entity type.

    All entity-type-specific behaviour is captured here so that the
    pipeline, blocker, scorer, and API layers remain generic.
    """

    # Identity
    type_name: str  # e.g. "company", "person"
    display_name: str  # human-readable, e.g. "Company"

    # Database
    table_name: str  # e.g. "companies"
    ngram_table_name: str  # e.g. "company_ngrams"
    id_column: str  # FK column in the ngram table, e.g. "company_id"
    db_fields: list[FieldDef]  # ordered column definitions (excluding 'id')

    # Which fields are the "primary name" for display / search
    display_name_field: str  # column used as the main display name

    # Ngram indexing: which DB fields get trigram entries
    ngram_source_fields: list[str]

    # Ensemble scorer form-pair mappings
    text_form_pairs: list[tuple[str, str]]
    phonetic_form_pairs: list[tuple[str, str]]

    # Normalization suffix lists keyed by language code
    suffix_lists: dict[str, list[str]] = field(default_factory=dict)

    # Function that converts a raw DB row dict into the candidate_forms
    # dict consumed by the ensemble scorer.
    candidate_form_extractor: Callable[[dict[str, Any]], dict[str, str]] = field(
        default=lambda row: {"name_normalized": row.get("name_normalized", "")}
    )

    # Optional function to remap query-side forms into candidate-side keys
    # for the compare (name-vs-name) API.  If None the pipeline builds a
    # default mapping from *text_form_pairs*.
    query_to_candidate_remapper: Callable[[dict[str, str]], dict[str, str]] | None = field(
        default=None
    )


# ------------------------------------------------------------------
# Generic entity record
# ------------------------------------------------------------------


@dataclass
class EntityRecord:
    """Generic runtime representation of any entity loaded from the DB.

    Instead of per-type dataclasses (``Company``, ``Person``, ...) we use a
    single wrapper that exposes commonly-needed attributes and falls back
    to dict-style access for entity-specific fields.
    """

    type_name: str
    id: int
    name: str  # derived from the entity type's display_name_field
    data: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve an arbitrary field from the underlying row data."""
        return self.data.get(key, default)

    @classmethod
    def from_row(
        cls,
        config: EntityTypeConfig,
        row: dict[str, Any],
    ) -> EntityRecord:
        """Construct an EntityRecord from a raw database row dict."""
        return cls(
            type_name=config.type_name,
            id=row["id"],
            name=row.get(config.display_name_field, ""),
            data=row,
        )


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------


class EntityTypeRegistry:
    """Simple dict-backed registry for entity type configurations."""

    def __init__(self) -> None:
        self._types: dict[str, EntityTypeConfig] = {}

    def register(self, config: EntityTypeConfig) -> None:
        """Register an entity type configuration."""
        self._types[config.type_name] = config

    def get(self, type_name: str) -> EntityTypeConfig:
        """Retrieve a registered entity type by name.

        Raises:
            KeyError: If the entity type is not registered.
        """
        if type_name not in self._types:
            available = ", ".join(sorted(self._types)) or "(none)"
            raise KeyError(f"Unknown entity type '{type_name}'. Registered types: {available}")
        return self._types[type_name]

    def all(self) -> list[EntityTypeConfig]:
        """Return all registered entity type configs."""
        return list(self._types.values())

    def names(self) -> list[str]:
        """Return registered entity type names."""
        return list(self._types.keys())

    def __contains__(self, type_name: str) -> bool:
        return type_name in self._types

    @classmethod
    def default(cls) -> EntityTypeRegistry:
        """Create a registry pre-loaded with built-in entity types."""
        from entity_resolution.entity_types.company import COMPANY_CONFIG

        registry = cls()
        registry.register(COMPANY_CONFIG)
        return registry
