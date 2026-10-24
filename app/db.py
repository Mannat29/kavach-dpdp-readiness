"""Database access module for Kavach."""
import os
import sqlite3
from typing import Optional

DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "kavach.sqlite")


def get_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection. In Flask request context, reuses g.db."""
    try:
        from flask import g, has_app_context, current_app
        if has_app_context():
            if "db" not in g:
                path = db_path or current_app.config.get("DATABASE") or os.environ.get("KAVACH_DATABASE", DEFAULT_DB_PATH)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                g.db = sqlite3.connect(path)
                g.db.row_factory = sqlite3.Row
                g.db.execute("PRAGMA foreign_keys = ON")
            return g.db
    except ImportError:
        pass

    path = db_path or os.environ.get("KAVACH_DATABASE", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_app(app):
    """Register database functions with the Flask app."""
    app.teardown_appcontext(close_db)


def close_db(e=None):
    """Close connection attached to flask.g."""
    try:
        from flask import g
        db = g.pop("db", None)
        if db is not None:
            db.close()
    except (ImportError, RuntimeError):
        pass


def init_db(db_path: Optional[str] = None):
    """Initialize database tables using schema.sql."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_db(db_path)

    # Migration: check if ledger has old schema
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(ledger)")
        cols = {row["name"] for row in cur.fetchall()}
        if cols and ("type" not in cols or "payload_json" not in cols):
            import json, hashlib, datetime
            cur.execute("SELECT * FROM ledger ORDER BY id ASC")
            old_rows = cur.fetchall()
            conn.execute("DROP TABLE ledger")
            conn.commit()
            conn.execute("""
                CREATE TABLE ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    event_json TEXT GENERATED ALWAYS AS (payload_json) STORED,
                    entry_hash TEXT GENERATED ALWAYS AS (hash) STORED,
                    created_at TEXT GENERATED ALWAYS AS (ts) STORED
                )
            """)
            prev_h = "0" * 64
            for r in old_rows:
                try:
                    ev_data = json.loads(r["event_json"]) if "event_json" in r.keys() else {}
                except Exception:
                    ev_data = {}
                ev_type = ev_data.get("event") or ev_data.get("type", "unknown")
                ts = r["created_at"] if "created_at" in r.keys() and r["created_at"] else datetime.datetime.now(datetime.timezone.utc).isoformat()
                payload_str = json.dumps(ev_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                h = hashlib.sha256(f"{prev_h}|{ts}|{ev_type}|{payload_str}".encode("utf-8")).hexdigest()
                conn.execute(
                    "INSERT INTO ledger (id, ts, type, payload_json, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)",
                    (r["id"], ts, ev_type, payload_str, prev_h, h),
                )
                prev_h = h
            conn.commit()
    except Exception:
        pass

    conn.executescript(schema_sql)
    conn.commit()

    # Migration: add path column to sources if missing
    try:
        conn.execute("ALTER TABLE sources ADD COLUMN path TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists

    try:
        from flask import has_app_context
        if not has_app_context():
            conn.close()
    except (ImportError, RuntimeError):
        conn.close()
