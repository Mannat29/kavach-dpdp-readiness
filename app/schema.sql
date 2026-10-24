-- Kavach DPDP Database Schema

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    type TEXT NOT NULL,
    record_count INTEGER DEFAULT 0,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    record_key TEXT NOT NULL,
    location TEXT NOT NULL,
    category TEXT NOT NULL,
    masked_sample TEXT NOT NULL,
    value_hash TEXT NOT NULL,
    confidence REAL NOT NULL,
    meta_json TEXT
);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    masked_name TEXT,
    name_hash TEXT
);

CREATE TABLE IF NOT EXISTS person_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    record_key TEXT NOT NULL,
    link_type TEXT NOT NULL,
    link_confidence REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS questionnaire (
    key TEXT PRIMARY KEY,
    answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL
);
