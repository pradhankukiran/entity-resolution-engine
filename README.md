<p align="center">
  <h1 align="center">Entity Resolution Engine</h1>
  <p align="center">
    Cross-language entity resolution with pluggable entity types, multi-strategy ensemble scoring, and explainable results.
  </p>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/SQLite-async-003B57?style=flat&logo=sqlite&logoColor=white" alt="SQLite"></a>
  <a href="https://pydantic.dev"><img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=flat&logo=pydantic&logoColor=white" alt="Pydantic v2"></a>
  <a href="https://docs.astral.sh/ruff/"><img src="https://img.shields.io/badge/linting-Ruff-D7FF64?style=flat&logo=ruff&logoColor=black" alt="Ruff"></a>
  <a href="https://mypy-lang.org/"><img src="https://img.shields.io/badge/typing-mypy-blue?style=flat" alt="mypy"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat" alt="License: MIT"></a>
</p>

---

## What is this?

A production-grade entity resolution service that determines whether two entity names refer to the same real-world thing -- even when they're written in different languages, scripts, or formats.

**Example:** Is `株式会社ソニー` the same as `Sony Corporation`? The engine says yes, with a confidence score, strategy breakdown, and step-by-step explanation of how it got there.

### Key Capabilities

| Capability | Details |
|---|---|
| **Pluggable entity types** | Company, person, product -- add new types with a single config file |
| **Cross-language** | Japanese ↔ English via transliteration, NFKC normalization, phonetic encoding |
| **4 scoring strategies** | Jaro-Winkler, Levenshtein, Token Sort, Phonetic -- combined via weighted ensemble |
| **Trigram blocking** | Sub-linear candidate retrieval from 100k+ entities |
| **Explainable** | Every match includes a full processing trace: language detection → normalization → scoring |
| **Batch processing** | Async job queue with concurrency control and progress tracking |
| **Production-ready** | Structured logging, CORS, security headers, health checks, Docker multi-stage build |

---

## Architecture

```
                          ┌─────────────────────────────────┐
                          │         Query: "ソニー"          │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │      Language Detection          │
                          │      (Unicode + langdetect)      │
                          └──────────────┬──────────────────┘
                                         │
                   ┌─────────────────────┼─────────────────────┐
                   ▼                     ▼                     ▼
          ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
          │ Normalization   │  │ Transliteration  │  │ Phonetic Encoding│
          │ (NFKC, suffix   │  │ (pykakasi →      │  │ (Soundex-style   │
          │  stripping)     │  │  romaji)         │  │  key generation) │
          └────────┬───────┘  └────────┬─────────┘  └────────┬─────────┘
                   └─────────────────────┼─────────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │      Candidate Blocking          │
                          │  (trigram overlap + phonetic key) │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │       Ensemble Scoring           │
                          │  ┌────────┬────────┬──────────┐ │
                          │  │Jaro-   │Leven-  │Token     │ │
                          │  │Winkler │shtein  │Sort      │ │
                          │  │(0.30)  │(0.25)  │(0.25)    │ │
                          │  └────────┴────────┴──────────┘ │
                          │  ┌────────────────────────────┐ │
                          │  │Phonetic Match (0.20)       │ │
                          │  └────────────────────────────┘ │
                          └──────────────┬──────────────────┘
                                         │
                          ┌──────────────▼──────────────────┐
                          │     Ranked Results + Explain     │
                          └─────────────────────────────────┘
```

---

## Quick Start

### Local

```bash
# Clone
git clone https://github.com/pradhankukiran/entity-resolution-engine.git
cd entity-resolution-engine

# Install
make install

# Seed the database with Japanese corporate registry data
make seed

# Start the dev server
make dev
```

Open `http://localhost:8000` for the UI, or `http://localhost:8000/docs` for the interactive API docs.

### Docker

```bash
docker compose up --build
```

---

## API

### Endpoints

All entity types are accessible under `/v1/{entity_type}/`:

```
POST  /v1/{entity_type}/search          Search entities by name
POST  /v1/{entity_type}/match           Compare two names directly
POST  /v1/{entity_type}/batch           Submit batch search job
GET   /v1/{entity_type}/batch/{job_id}  Poll batch job status

GET   /health                            Liveness check
GET   /stats                             Database statistics
```

Backward-compatible routes (`/search`, `/match`, `/batch`) default to the `company` entity type.

### Usage

**Search:**

```bash
curl -s -X POST http://localhost:8000/v1/company/search \
  -H "Content-Type: application/json" \
  -d '{"query": "ソニー", "limit": 5}'
```

```json
{
  "query": "ソニー",
  "entity_type": "company",
  "detected_language": "ja",
  "matches": [
    {
      "rank": 1,
      "entity_name": "ソニーグループ株式会社",
      "score": 0.87,
      "strategy_scores": [...]
    }
  ]
}
```

**Compare two names:**

```bash
curl -s -X POST http://localhost:8000/v1/company/match \
  -H "Content-Type: application/json" \
  -d '{"name_a": "Sony Corporation", "name_b": "ソニー株式会社"}'
```

```json
{
  "name_a": "Sony Corporation",
  "name_b": "ソニー株式会社",
  "final_score": 0.72,
  "strategy_scores": [
    {"strategy_name": "jaro_winkler", "score": 0.68},
    {"strategy_name": "levenshtein", "score": 0.55},
    {"strategy_name": "token_sort", "score": 0.65},
    {"strategy_name": "phonetic", "score": 1.0}
  ]
}
```

---

## Adding a New Entity Type

Adding support for a new entity type (person, product, etc.) requires **one file** -- no changes to the pipeline, scoring, or API layers.

**1. Define the config:**

```python
# src/entity_resolution/entity_types/person.py

from entity_resolution.entity_types.config import EntityTypeConfig, FieldDef

def person_candidate_forms(row):
    forms = {"name_normalized": row.get("name_normalized") or ""}
    if row.get("phonetic_key"):
        forms["phonetic_key"] = row["phonetic_key"]
    return forms

PERSON_CONFIG = EntityTypeConfig(
    type_name="person",
    display_name="Person",
    table_name="persons",
    ngram_table_name="person_ngrams",
    id_column="person_id",
    db_fields=[
        FieldDef("full_name", "TEXT", nullable=False),
        FieldDef("name_normalized", "TEXT", nullable=False),
        FieldDef("given_name", "TEXT"),
        FieldDef("family_name", "TEXT"),
        FieldDef("phonetic_key", "TEXT", indexed=True),
    ],
    display_name_field="full_name",
    ngram_source_fields=["name_normalized"],
    text_form_pairs=[("normalized", "name_normalized")],
    phonetic_form_pairs=[("phonetic", "phonetic_key")],
    candidate_form_extractor=person_candidate_forms,
)
```

**2. Register it** in `EntityTypeRegistry.default()`.

**3. Done.** The engine auto-creates tables and exposes `/v1/person/search`, `/v1/person/match`, etc.

---

## How It Works

### Matching Strategies

| Strategy | Weight | What it measures |
|---|---|---|
| **Jaro-Winkler** | 0.30 | Character-level similarity with prefix bonus |
| **Levenshtein** | 0.25 | Normalized edit distance |
| **Token Sort** | 0.25 | Similarity after alphabetical token reordering |
| **Phonetic** | 0.20 | Soundex-style phonetic key comparison |

The ensemble scorer tries every compatible (query form, candidate form) pair per strategy and takes the best score. The final score is a weighted average across all strategies.

### Blocking

To avoid O(n^2) comparisons, the engine uses a two-phase blocking strategy:

1. **Trigram overlap** -- character trigrams from the query are matched against a prebuilt ngram index
2. **Phonetic key** -- exact and prefix matching on Soundex-style keys

This narrows 100k+ entities to ~200 candidates before scoring.

### Cross-Language Pipeline

For Japanese queries:
```
株式会社ソニー → [strip suffix] → ソニー → [transliterate] → sonii → [phonetic] → S500xx
```

For English queries:
```
Sony Corporation → [strip suffix] → sony → [normalize] → sony → [phonetic] → S500xx
```

Both produce comparable phonetic keys (`S500xx`), enabling cross-language matching.

---

## Tech Stack

| Component | Technology |
|---|---|
| **API** | FastAPI, Pydantic v2, Uvicorn |
| **Database** | SQLite (async via aiosqlite) |
| **Matching** | RapidFuzz, custom phonetic encoder |
| **Japanese NLP** | pykakasi (transliteration), langdetect |
| **Logging** | structlog (JSON) |
| **Linting** | Ruff, mypy |
| **Testing** | pytest, pytest-asyncio |
| **Container** | Docker (multi-stage, non-root) |

---

## Development

```bash
make install      # Install with dev dependencies
make dev          # Start dev server with hot reload
make test         # Run test suite (138 tests)
make lint         # Lint with ruff
make format       # Auto-format with ruff
make typecheck    # Type check with mypy
make check        # All of the above
make coverage     # Tests with HTML coverage report
make seed         # Seed DB with NTA corporate registry
make clean        # Remove build artifacts
```

## Project Structure

```
src/entity_resolution/
    entity_types/       # Pluggable entity type definitions
        config.py       #   EntityTypeConfig, EntityRecord, Registry
        company.py      #   Company entity config (JP corporate registry)
    api/
        routers/
            entity.py   #   Generic /v1/{entity_type}/ routes
            search.py   #   Backward-compat /search
            match.py    #   Backward-compat /match
            batch.py    #   Backward-compat /batch
            health.py   #   /health, /stats
        schemas.py      #   Pydantic request/response models
        middleware.py   #   Logging + security headers
    matching/
        base.py         #   MatchStrategy ABC
        ensemble.py     #   Weighted multi-strategy scorer
        registry.py     #   Strategy registry
        jaro_winkler.py #   Jaro-Winkler strategy
        levenshtein.py  #   Levenshtein strategy
        token_sort.py   #   Token sort strategy
        phonetic_match.py # Phonetic key strategy
    normalization/
        normalizer.py   #   NFKC, suffix stripping, whitespace
        transliterator.py # Japanese → romaji (pykakasi)
        phonetic.py     #   Soundex-style phonetic encoder
        language.py     #   Language/script detection
    pipeline/
        pipeline.py     #   Main orchestrator
        blocker.py      #   Trigram + phonetic candidate blocking
        explainer.py    #   Step-by-step explanation builder
    batch/
        manager.py      #   Async batch job queue
    db/
        database.py     #   Async SQLite wrapper
        query_builder.py #  Dynamic SQL from entity config
        models.py       #   Legacy Company model
        queries.py      #   Legacy hardcoded SQL
    core/
        config.py       #   Pydantic settings
        dependencies.py #   FastAPI DI singletons
        logging.py      #   structlog setup
```

---

## License

[MIT](LICENSE)
