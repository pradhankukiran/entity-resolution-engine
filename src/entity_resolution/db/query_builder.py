"""Dynamic SQL generation from EntityTypeConfig.

Replaces the hardcoded query constants in ``queries.py`` with functions
that produce SQL for any registered entity type.
"""

from __future__ import annotations

from entity_resolution.entity_types.config import EntityTypeConfig


# ------------------------------------------------------------------
# Schema DDL
# ------------------------------------------------------------------


def build_schema(config: EntityTypeConfig) -> str:
    """Generate CREATE TABLE + CREATE INDEX DDL for an entity type."""
    lines: list[str] = []

    # Main entity table
    lines.append(f"CREATE TABLE IF NOT EXISTS {config.table_name} (")
    lines.append("    id INTEGER PRIMARY KEY AUTOINCREMENT,")

    for i, f in enumerate(config.db_fields):
        parts = [f"    {f.name} {f.sql_type}"]
        if f.unique:
            parts.append("UNIQUE")
        if not f.nullable:
            parts.append("NOT NULL")
        trail = "," if i < len(config.db_fields) - 1 else ","
        lines.append(" ".join(parts) + trail)

    lines.append("    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    lines.append(");")
    lines.append("")

    # Ngram table
    lines.append(f"CREATE TABLE IF NOT EXISTS {config.ngram_table_name} (")
    lines.append("    id INTEGER PRIMARY KEY AUTOINCREMENT,")
    lines.append(
        f"    {config.id_column} INTEGER NOT NULL "
        f"REFERENCES {config.table_name}(id),"
    )
    lines.append("    ngram TEXT NOT NULL,")
    lines.append("    source_field TEXT NOT NULL")
    lines.append(");")
    lines.append("")

    # Indexes on the entity table
    for f in config.db_fields:
        if f.indexed:
            idx_name = f"idx_{config.table_name}_{f.name}"
            lines.append(
                f"CREATE INDEX IF NOT EXISTS {idx_name} "
                f"ON {config.table_name}({f.name});"
            )
        if f.unique:
            idx_name = f"idx_{config.table_name}_{f.name}"
            lines.append(
                f"CREATE INDEX IF NOT EXISTS {idx_name} "
                f"ON {config.table_name}({f.name});"
            )

    # Indexes on the ngram table
    lines.append(
        f"CREATE INDEX IF NOT EXISTS idx_{config.ngram_table_name}_ngram "
        f"ON {config.ngram_table_name}(ngram);"
    )
    lines.append(
        f"CREATE INDEX IF NOT EXISTS idx_{config.ngram_table_name}_{config.id_column} "
        f"ON {config.ngram_table_name}({config.id_column});"
    )

    return "\n".join(lines)


# ------------------------------------------------------------------
# Insert
# ------------------------------------------------------------------


def build_insert_entity(config: EntityTypeConfig) -> str:
    """Generate an INSERT statement for the entity table."""
    columns = ", ".join(f.name for f in config.db_fields)
    placeholders = ", ".join("?" for _ in config.db_fields)
    return (
        f"INSERT INTO {config.table_name} ({columns})\n"
        f"VALUES ({placeholders})"
    )


def build_insert_ngram(config: EntityTypeConfig) -> str:
    """Generate an INSERT statement for the ngram table."""
    return (
        f"INSERT INTO {config.ngram_table_name} "
        f"({config.id_column}, ngram, source_field)\n"
        f"VALUES (?, ?, ?)"
    )


# ------------------------------------------------------------------
# Search / Candidates
# ------------------------------------------------------------------


def build_search_by_ngrams(config: EntityTypeConfig, count: int) -> str:
    """Generate a trigram search query for *count* ngrams."""
    placeholders = ", ".join("?" for _ in range(count))
    return (
        f"SELECT\n"
        f"    ng.{config.id_column},\n"
        f"    COUNT(ng.ngram) AS match_count\n"
        f"FROM {config.ngram_table_name} ng\n"
        f"WHERE ng.ngram IN ({placeholders})\n"
        f"GROUP BY ng.{config.id_column}\n"
        f"ORDER BY match_count DESC\n"
        f"LIMIT ?"
    )


def build_search_by_phonetic(config: EntityTypeConfig) -> str:
    """Generate a phonetic key search query."""
    return (
        f"SELECT\n"
        f"    e.id AS {config.id_column}\n"
        f"FROM {config.table_name} e\n"
        f"WHERE e.phonetic_key = ?\n"
        f"   OR e.phonetic_key LIKE ? || '%'\n"
        f"ORDER BY e.id\n"
        f"LIMIT ?"
    )


# ------------------------------------------------------------------
# Fetch
# ------------------------------------------------------------------


def _all_columns(config: EntityTypeConfig) -> str:
    """Return a comma-separated list of all columns including id."""
    cols = ["id"] + [f.name for f in config.db_fields]
    return ",\n    ".join(cols)


def build_get_by_id(config: EntityTypeConfig) -> str:
    """Generate a SELECT for a single entity by id."""
    cols = _all_columns(config)
    return (
        f"SELECT\n"
        f"    {cols}\n"
        f"FROM {config.table_name}\n"
        f"WHERE id = ?"
    )


def build_get_by_ids(config: EntityTypeConfig, count: int) -> str:
    """Generate a SELECT for multiple entities by id list."""
    cols = _all_columns(config)
    placeholders = ", ".join("?" for _ in range(count))
    return (
        f"SELECT\n"
        f"    {cols}\n"
        f"FROM {config.table_name}\n"
        f"WHERE id IN ({placeholders})\n"
        f"ORDER BY id"
    )


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------


def build_get_stats(config: EntityTypeConfig) -> str:
    """Generate a statistics query for entity + ngram counts."""
    return (
        f"SELECT\n"
        f"    (SELECT COUNT(*) FROM {config.table_name}) AS entity_count,\n"
        f"    (SELECT COUNT(*) FROM {config.ngram_table_name}) AS ngram_count"
    )
