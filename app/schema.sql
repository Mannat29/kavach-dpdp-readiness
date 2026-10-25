-- Kavach DPDP Database Schema

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    type TEXT NOT NULL,
    record_count INTEGER DEFAULT 0,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    path TEXT
);

CREATE TABLE IF NOT EXISTS rights_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intent TEXT NOT NULL,
    sender_masked TEXT,
    person_id INTEGER REFERENCES people(id),
    resolution TEXT,
    confidence REAL,
    received_at TIMESTAMP,
    due_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'received',
    message_excerpt_masked TEXT,
    plan_json TEXT,
    plan_hash TEXT,
    executed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    event_json TEXT GENERATED ALWAYS AS (payload_json) STORED,
    entry_hash TEXT GENERATED ALWAYS AS (hash) STORED,
    created_at TEXT GENERATED ALWAYS AS (ts) STORED
);

CREATE TABLE IF NOT EXISTS evidence_packs (
    pack_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    head_hash TEXT NOT NULL,
    score INTEGER NOT NULL,
    chain_ok INTEGER NOT NULL,
    path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_tamper_backup (
    id INTEGER PRIMARY KEY,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    ts TEXT NOT NULL,
    type TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS breach_simulations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario TEXT NOT NULL,
    aware_at TIMESTAMP NOT NULL,
    device_protected TEXT NOT NULL,
    severity TEXT NOT NULL,
    counts_json TEXT NOT NULL,
    drafts_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purpose_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    field_header TEXT,
    category TEXT,
    segment TEXT,
    purpose_id TEXT NULL,
    status TEXT CHECK(status IN ('confirmed', 'unknown')),
    answered_by TEXT,
    answered_at TEXT,
    superseded_by INTEGER NULL
);

