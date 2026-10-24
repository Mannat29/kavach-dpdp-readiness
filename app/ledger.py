"""Ledger module: hash-chained audit log for rights request events."""
import hashlib
import json
import datetime


def append_ledger(event: dict, conn) -> int:
    """Append an event to the ledger with hash chaining. Returns new ledger entry id."""
    cur = conn.cursor()

    # Get the last entry hash for chaining
    cur.execute("SELECT entry_hash FROM ledger ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["entry_hash"] if row else "genesis"

    # Serialize event with timestamp
    entry = {
        "event": event,
        "prev_hash": prev_hash,
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    entry_json = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    entry_hash = hashlib.sha256(entry_json.encode("utf-8")).hexdigest()

    cur.execute(
        "INSERT INTO ledger (event_json, prev_hash, entry_hash) VALUES (?, ?, ?)",
        (json.dumps(event, ensure_ascii=False), prev_hash, entry_hash),
    )
    conn.commit()
    return cur.lastrowid
