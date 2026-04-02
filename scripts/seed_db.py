"""Download NTA corporate registry CSV and seed the SQLite database.

NTA data format (CSV, Shift_JIS / cp932):
    - Column 0:  sequence number
    - Column 1:  corporate number (13 digits)
    - Column 2:  process (01=new, 12=trade name, etc.)
    - Column 3:  correct (0=latest)
    - Column 4:  update date
    - Column 5:  change date
    - Column 6:  company name (kanji)
    - Column 7:  company name (furigana / kana)
    - Column 8:  address (prefecture code)
    - Column 9:  address (city)
    - Column 10: address (street)
    - ...
    - Column 24: English name (if available)

NTA download URL pattern:
    https://www.houjin-bangou.nta.go.jp/download/zenken/csv/{code}.zip

where ``code`` is a zero-padded 2-digit prefecture code (e.g. ``14`` for
Kanagawa).  The zip contains a single CSV encoded in cp932 (Shift_JIS).

Usage:
    python -m scripts.seed_db
    # or, from the project root:
    python scripts/seed_db.py
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import sys
import zipfile
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Ensure the ``src`` directory is on sys.path so that imports work when
# running the script directly (``python scripts/seed_db.py``).
# ---------------------------------------------------------------------------
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from entity_resolution.core.config import Settings  # noqa: E402
from entity_resolution.db.database import Database  # noqa: E402
from entity_resolution.normalization.normalizer import TextNormalizer  # noqa: E402
from entity_resolution.normalization.transliterator import Transliterator  # noqa: E402
from entity_resolution.normalization.phonetic import PhoneticEncoder  # noqa: E402


NTA_URL_TEMPLATE = (
    "https://www.houjin-bangou.nta.go.jp/download/zenken/csv/{code}.zip"
)

INSERT_COMPANY_SQL = """
    INSERT OR IGNORE INTO companies
        (corporate_number, name, name_normalized, furigana,
         en_name, en_name_normalized, name_romaji, phonetic_key,
         prefecture_code, city, address)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERT_NGRAM_SQL = """
    INSERT INTO company_ngrams (company_id, ngram, source_field)
    VALUES (?, ?, ?)
"""


async def _insert_batch(
    db: Database,
    rows: list[tuple],
    normalizer: TextNormalizer,
) -> None:
    """Insert a batch of company records together with their trigram ngrams."""
    for row in rows:
        # Insert the company row
        await db.execute(INSERT_COMPANY_SQL, row)

        # Retrieve the company_id for the just-inserted record
        result = await db.fetch_one(
            "SELECT id FROM companies WHERE corporate_number = ?",
            (row[0],),
        )
        if result is None:
            continue
        company_id = result["id"]

        # Generate and insert trigrams for each relevant text field.
        # Index mapping into `row`: 2=name_normalized, 5=en_name_normalized,
        # 6=name_romaji
        field_mapping: list[tuple[int, str]] = [
            (2, "name_normalized"),
            (5, "en_name_normalized"),
            (6, "name_romaji"),
        ]
        for field_idx, field_name in field_mapping:
            text = row[field_idx]
            if text:
                trigrams = normalizer.generate_trigrams(text)
                for trigram in trigrams:
                    await db.execute(
                        INSERT_NGRAM_SQL,
                        (company_id, trigram, field_name),
                    )


async def main() -> None:
    """Download, extract, parse, and seed the database."""
    settings = Settings()
    code = settings.nta_prefecture_code.zfill(2)

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    zip_path = data_dir / f"{code}.zip"
    csv_path = data_dir / f"{code}.csv"

    # ------------------------------------------------------------------
    # Step 1: Download the ZIP if not already cached locally
    # ------------------------------------------------------------------
    if not zip_path.exists():
        url = NTA_URL_TEMPLATE.format(code=code)
        print(f"Downloading NTA data from {url} ...")
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            zip_path.write_bytes(resp.content)
        print(f"Downloaded {len(resp.content):,} bytes -> {zip_path}")
    else:
        print(f"Using cached ZIP: {zip_path}")

    # ------------------------------------------------------------------
    # Step 2: Extract the CSV from the ZIP (re-encode to UTF-8)
    # ------------------------------------------------------------------
    if not csv_path.exists():
        print("Extracting CSV ...")
        with zipfile.ZipFile(zip_path) as zf:
            csv_files = [f for f in zf.namelist() if f.endswith(".csv")]
            if not csv_files:
                raise RuntimeError("No CSV file found inside the ZIP archive")
            with zf.open(csv_files[0]) as f:
                content = f.read().decode("cp932", errors="replace")
                csv_path.write_text(content, encoding="utf-8")
        print(f"Extracted to {csv_path}")
    else:
        print(f"Using cached CSV: {csv_path}")

    # ------------------------------------------------------------------
    # Step 3: Parse CSV and seed the database
    # ------------------------------------------------------------------
    normalizer = TextNormalizer()
    transliterator = Transliterator()
    encoder = PhoneticEncoder()

    db = Database(settings.database_path)
    await db.connect()

    print("Parsing CSV and seeding database ...")

    reader = csv.reader(io.StringIO(csv_path.read_text(encoding="utf-8")))

    count = 0
    batch_size = 500
    rows_batch: list[tuple] = []

    for row in reader:
        if len(row) < 9:
            continue

        # Extract relevant columns
        corp_number = row[1].strip()
        correct = row[3].strip() if len(row) > 3 else ""
        name = row[6].strip() if len(row) > 6 else ""
        furigana = row[7].strip() if len(row) > 7 else ""
        pref_code = row[8].strip() if len(row) > 8 else ""
        city = row[9].strip() if len(row) > 9 else ""
        address = row[10].strip() if len(row) > 10 else ""
        en_name = row[24].strip() if len(row) > 24 else ""

        # Skip records that lack a name or corporate number
        if not name or not corp_number:
            continue
        # Only keep the latest/current version of each record
        if correct != "0":
            continue

        # Pre-compute derived fields for search
        name_normalized = normalizer.normalize(name)
        en_name_normalized = normalizer.normalize(en_name) if en_name else None
        name_romaji = transliterator.to_romaji(name)
        phonetic_key = encoder.encode(name_romaji)

        rows_batch.append((
            corp_number,
            name,
            name_normalized,
            furigana or None,
            en_name or None,
            en_name_normalized,
            name_romaji,
            phonetic_key,
            pref_code or None,
            city or None,
            address or None,
        ))

        if len(rows_batch) >= batch_size:
            await _insert_batch(db, rows_batch, normalizer)
            count += len(rows_batch)
            print(f"  Inserted {count:,} records ...")
            rows_batch = []

    # Flush the remaining partial batch
    if rows_batch:
        await _insert_batch(db, rows_batch, normalizer)
        count += len(rows_batch)

    print(f"Done! Total records inserted: {count:,}")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
