"""SQL query constants.

All queries use ANSI-compatible SQL for portability across SQLite and
Snowflake.  Parameter placeholders use ``?`` (the sqlite3 convention);
a Snowflake adapter would swap these to positional ``%s`` or ``:1`` markers.
"""

# ------------------------------------------------------------------
# Insert
# ------------------------------------------------------------------

INSERT_COMPANY = """
INSERT INTO companies (
    corporate_number,
    name,
    name_normalized,
    furigana,
    en_name,
    en_name_normalized,
    name_romaji,
    phonetic_key,
    prefecture_code,
    city,
    address
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERT_NGRAM = """
INSERT INTO company_ngrams (company_id, ngram, source_field)
VALUES (?, ?, ?)
"""

# ------------------------------------------------------------------
# Search / Candidates
# ------------------------------------------------------------------

SEARCH_BY_NGRAMS = """
SELECT
    cn.company_id,
    COUNT(cn.ngram) AS match_count
FROM company_ngrams cn
WHERE cn.ngram IN ({placeholders})
GROUP BY cn.company_id
ORDER BY match_count DESC
LIMIT ?
"""
# NOTE: The ``{placeholders}`` token must be replaced at runtime with
# the correct number of ``?`` markers for the ngram list.  For example:
#
#     ngrams = ["abc", "bcd", "cde"]
#     placeholders = ", ".join("?" for _ in ngrams)
#     sql = SEARCH_BY_NGRAMS.format(placeholders=placeholders)
#     params = [*ngrams, limit]

SEARCH_BY_PHONETIC_KEY = """
SELECT
    c.id AS company_id
FROM companies c
WHERE c.phonetic_key = ?
   OR c.phonetic_key LIKE ? || '%'
ORDER BY c.id
LIMIT ?
"""
# Parameters: (phonetic_key_exact, phonetic_key_prefix, limit)

# ------------------------------------------------------------------
# Fetch
# ------------------------------------------------------------------

GET_COMPANY_BY_ID = """
SELECT
    id,
    corporate_number,
    name,
    name_normalized,
    furigana,
    en_name,
    en_name_normalized,
    name_romaji,
    phonetic_key,
    prefecture_code,
    city,
    address
FROM companies
WHERE id = ?
"""

GET_COMPANIES_BY_IDS = """
SELECT
    id,
    corporate_number,
    name,
    name_normalized,
    furigana,
    en_name,
    en_name_normalized,
    name_romaji,
    phonetic_key,
    prefecture_code,
    city,
    address
FROM companies
WHERE id IN ({placeholders})
ORDER BY id
"""
# NOTE: ``{placeholders}`` must be replaced at runtime, similar to
# SEARCH_BY_NGRAMS.

# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------

GET_STATS = """
SELECT
    (SELECT COUNT(*) FROM companies) AS company_count,
    (SELECT COUNT(*) FROM company_ngrams) AS ngram_count
"""

COUNT_COMPANIES = """
SELECT COUNT(*) AS total FROM companies
"""
