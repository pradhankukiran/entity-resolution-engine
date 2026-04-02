# Entity Resolution Engine

[![CI](https://github.com/YOUR_USERNAME/entity-resolution-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/entity-resolution-engine/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Cross-language entity resolution engine with pluggable entity types. Matches entity names across languages and scripts using trigram blocking, phonetic indexing, and multi-strategy ensemble scoring.

## Architecture

```
Query String
    |
    v
Language Detection --> Normalization --> Transliteration --> Phonetic Encoding
    |
    v
Candidate Blocking (trigram + phonetic)
    |
    v
Ensemble Scoring (Jaro-Winkler, Levenshtein, Token Sort, Phonetic)
    |
    v
Ranked Results with Explanations
```

## Features

- **Pluggable entity types** -- company, person, product, etc. via declarative config
- **Cross-language matching** -- Japanese/English with transliteration (pykakasi)
- **4 matching strategies** -- Jaro-Winkler, Levenshtein, Token Sort, Phonetic
- **Ensemble scoring** -- weighted combination with configurable form-pair mappings
- **Trigram blocking** -- fast candidate retrieval from 100k+ entities
- **Explainable results** -- step-by-step processing breakdown per match
- **Batch API** -- async job submission with progress tracking
- **Structured logging** -- JSON output via structlog

## Quick Start

```bash
# Install
make install

# Seed the database with Japanese corporate registry data
make seed

# Start the development server
make dev
```

Visit `http://localhost:8000` for the web UI, or `http://localhost:8000/docs` for the API docs.

## API Endpoints

### Generic (any entity type)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/{entity_type}/search` | Resolve a name against the database |
| POST | `/v1/{entity_type}/match` | Compare two names directly |
| POST | `/v1/{entity_type}/batch` | Submit batch of search queries |
| GET | `/v1/{entity_type}/batch/{job_id}` | Poll batch job status |

### Backward-compatible (defaults to company)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/search` | Search companies |
| POST | `/match` | Compare company names |
| POST | `/batch` | Submit company batch |
| GET | `/batch/{job_id}` | Poll batch status |
| GET | `/health` | Liveness check |
| GET | `/stats` | Database statistics |

### Example

```bash
# Search for a company
curl -X POST http://localhost:8000/v1/company/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Sony", "limit": 5}'

# Compare two names
curl -X POST http://localhost:8000/v1/company/match \
  -H "Content-Type: application/json" \
  -d '{"name_a": "Sony Corporation", "name_b": "Sony"}'
```

## Docker

```bash
# Build and run
docker compose up --build

# Or build manually
docker build -t entity-resolution-engine .
docker run -p 8000:8000 -v ./data:/app/data entity-resolution-engine
```

## Development

```bash
make install      # Install with dev dependencies
make test         # Run tests
make lint         # Check linting (ruff)
make format       # Auto-format code
make typecheck    # Run mypy
make check        # lint + typecheck + test
make coverage     # Tests with coverage report
```

## Adding a New Entity Type

1. Create `src/entity_resolution/entity_types/your_type.py`:

```python
from entity_resolution.entity_types.config import EntityTypeConfig, FieldDef

YOUR_TYPE_CONFIG = EntityTypeConfig(
    type_name="person",
    display_name="Person",
    table_name="persons",
    ngram_table_name="person_ngrams",
    id_column="person_id",
    db_fields=[
        FieldDef("full_name", "TEXT", nullable=False),
        FieldDef("name_normalized", "TEXT", nullable=False),
        FieldDef("phonetic_key", "TEXT", indexed=True),
        # ... your fields
    ],
    display_name_field="full_name",
    ngram_source_fields=["name_normalized"],
    text_form_pairs=[("normalized", "name_normalized")],
    phonetic_form_pairs=[("phonetic", "phonetic_key")],
    suffix_lists={},
    candidate_form_extractor=your_extractor_function,
)
```

2. Register it in `EntityTypeRegistry.default()` in `config.py`.

3. The engine automatically creates the DB tables and exposes `/v1/person/search`, etc.

## Project Structure

```
src/entity_resolution/
    api/                # FastAPI routers, schemas, middleware
    batch/              # Async batch job manager
    core/               # Config, dependencies, logging
    db/                 # Database, models, query builder
    entity_types/       # Pluggable entity type configs
    matching/           # Scoring strategies + ensemble
    normalization/      # Text normalization, transliteration, phonetics
    pipeline/           # Blocker, explainer, orchestration
```

## License

[MIT](LICENSE)
