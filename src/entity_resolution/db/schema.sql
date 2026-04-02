CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    corporate_number TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    furigana TEXT,
    en_name TEXT,
    en_name_normalized TEXT,
    name_romaji TEXT,
    phonetic_key TEXT,
    prefecture_code TEXT,
    city TEXT,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_ngrams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    ngram TEXT NOT NULL,
    source_field TEXT NOT NULL  -- 'name_normalized', 'en_name_normalized', 'name_romaji'
);

CREATE INDEX IF NOT EXISTS idx_companies_phonetic_key ON companies(phonetic_key);
CREATE INDEX IF NOT EXISTS idx_companies_corporate_number ON companies(corporate_number);
CREATE INDEX IF NOT EXISTS idx_companies_en_name_normalized ON companies(en_name_normalized);
CREATE INDEX IF NOT EXISTS idx_company_ngrams_ngram ON company_ngrams(ngram);
CREATE INDEX IF NOT EXISTS idx_company_ngrams_company_id ON company_ngrams(company_id);
