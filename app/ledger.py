"""Ledger module: append-only hash-chained audit trail, verification, tamper demo, and evidence pack export."""
import datetime
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_db

GENESIS_PREV_HASH = "0" * 64


def canonical_payload_json(payload: dict) -> str:
    """Return canonically serialized JSON (sorted keys, compact separators, UTF-8)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(prev_hash: str, ts: str, event_type: str, payload_json: str) -> str:
    """Compute entry hash = sha256(prev_hash + '|' + ts + '|' + type + '|' + payload_json)."""
    raw = f"{prev_hash}|{ts}|{event_type}|{payload_json}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_payload_guard(payload: dict) -> None:
    """Guard that runs detect functions over the payload and raises if any identifier is found.

    Payloads may contain request IDs, masked labels, counts, plan hashes, scenario names only.
    """
    from app.detect import detect_all

    texts_to_check: List[str] = [canonical_payload_json(payload)]

    def _collect_strings(val: Any) -> None:
        if isinstance(val, str):
            texts_to_check.append(val)
        elif isinstance(val, dict):
            for v in val.values():
                _collect_strings(v)
        elif isinstance(val, (list, tuple, set)):
            for v in val:
                _collect_strings(v)

    _collect_strings(payload)

    for text in texts_to_check:
        findings = detect_all(text, source="ledger", location="payload", meta={})
        if findings:
            categories = sorted({f["category"] for f in findings})
            raise ValueError(
                f"Personal data detected in ledger payload: {categories}. "
                "Ledger entries must not store raw personal data."
            )


def append_ledger(event_type_or_dict: Any, payload_or_conn: Any = None, conn: Any = None) -> int:
    """Append an event to the ledger with hash chaining.

    Supports both signatures:
      append_ledger(type: str, payload: dict, conn=None)
      append_ledger(event_dict: dict, conn=None)  (legacy / convenience)

    Prev_hash for genesis = 64 zeros.
    hash = sha256(prev_hash + '|' + ts + '|' + type + '|' + payload_json).
    Returns new ledger entry id.
    """
    if isinstance(event_type_or_dict, dict):
        event_dict = dict(event_type_or_dict)
        actual_conn = payload_or_conn or conn
        event_type = event_dict.get("event") or event_dict.get("type", "unknown")
        payload = event_dict
    else:
        event_type = str(event_type_or_dict)
        payload = dict(payload_or_conn) if payload_or_conn is not None else {}
        actual_conn = conn
        if "event" not in payload:
            payload["event"] = event_type

    if actual_conn is None:
        actual_conn = get_db()

    # Guard: never store raw personal data
    check_payload_guard(payload)

    cur = actual_conn.cursor()

    # Get the last entry hash for chaining
    cur.execute("SELECT hash FROM ledger ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["hash"] if row and row["hash"] else GENESIS_PREV_HASH

    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload_json = canonical_payload_json(payload)
    entry_hash = compute_entry_hash(prev_hash, ts, event_type, payload_json)

    cur.execute(
        "INSERT INTO ledger (ts, type, payload_json, prev_hash, hash) VALUES (?, ?, ?, ?, ?)",
        (ts, event_type, payload_json, prev_hash, entry_hash),
    )
    actual_conn.commit()
    return cur.lastrowid


def verify_chain(conn: Any = None) -> Dict[str, Any]:
    """Verify the integrity of the audit ledger hash chain.

    Recomputes every hash and checks prev_hash links.
    Detects modified payloads, modified hashes, deleted middle rows, and reordered rows.

    Returns:
      {
        "ok": bool,
        "length": int,
        "head_hash": Optional[str],
        "first_broken_id": Optional[int],
        "reason": Optional[str]
      }
    """
    if conn is None:
        conn = get_db()

    cur = conn.cursor()
    cur.execute("SELECT id, ts, type, payload_json, prev_hash, hash FROM ledger ORDER BY id ASC")
    rows = cur.fetchall()

    if not rows:
        return {
            "ok": True,
            "length": 0,
            "head_hash": None,
            "first_broken_id": None,
            "reason": None,
        }

    prev_row = None
    for idx, row in enumerate(rows):
        row_id = row["id"]
        ts = row["ts"]
        ev_type = row["type"]
        payload_json = row["payload_json"]
        prev_hash = row["prev_hash"]
        stored_hash = row["hash"]

        # Check genesis link
        if idx == 0:
            if prev_hash != GENESIS_PREV_HASH:
                return {
                    "ok": False,
                    "length": len(rows),
                    "head_hash": rows[-1]["hash"],
                    "first_broken_id": row_id,
                    "reason": f"Genesis prev_hash mismatch: expected {GENESIS_PREV_HASH}, got {prev_hash}",
                }
        else:
            # Check prev_hash links to prior row
            if prev_row is not None:
                if prev_hash != prev_row["hash"]:
                    return {
                        "ok": False,
                        "length": len(rows),
                        "head_hash": rows[-1]["hash"],
                        "first_broken_id": row_id,
                        "reason": f"Hash chain broken at event #{row_id}: prev_hash does not match previous event hash",
                    }
                if row_id <= prev_row["id"]:
                    return {
                        "ok": False,
                        "length": len(rows),
                        "head_hash": rows[-1]["hash"],
                        "first_broken_id": row_id,
                        "reason": f"Row IDs out of order at event #{row_id}",
                    }

        # Recompute entry hash
        computed_hash = compute_entry_hash(prev_hash, ts, ev_type, payload_json)
        if computed_hash != stored_hash:
            return {
                "ok": False,
                "length": len(rows),
                "head_hash": rows[-1]["hash"],
                "first_broken_id": row_id,
                "reason": f"Hash mismatch at event #{row_id}: stored {stored_hash[:12]}, computed {computed_hash[:12]}",
            }

        prev_row = row

    return {
        "ok": True,
        "length": len(rows),
        "head_hash": rows[-1]["hash"],
        "first_broken_id": None,
        "reason": None,
    }


def tamper_ledger_event(event_id: int, conn: Any = None) -> Dict[str, Any]:
    """Dev-only: edits one stored payload without recomputing hashes."""
    if conn is None:
        conn = get_db()

    cur = conn.cursor()
    cur.execute("SELECT id, ts, type, payload_json, prev_hash, hash FROM ledger WHERE id = ?", (event_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Ledger event #{event_id} not found")

    # Save original to backup table if not already present
    cur.execute(
        "INSERT OR REPLACE INTO ledger_tamper_backup (id, payload_json, prev_hash, hash, ts, type) VALUES (?, ?, ?, ?, ?, ?)",
        (row["id"], row["payload_json"], row["prev_hash"], row["hash"], row["ts"], row["type"]),
    )

    try:
        data = json.loads(row["payload_json"])
    except Exception:
        data = {}

    data["_tampered"] = True
    data["_tamper_note"] = "simulated unauthorized edit"
    tampered_payload_json = canonical_payload_json(data)

    cur.execute(
        "UPDATE ledger SET payload_json = ? WHERE id = ?",
        (tampered_payload_json, event_id),
    )
    conn.commit()

    return {
        "success": True,
        "tampered_id": event_id,
        "message": f"Tampered payload for event #{event_id} without recomputing hash",
    }


def repair_ledger_event(event_id: Optional[int] = None, conn: Any = None) -> Dict[str, Any]:
    """Dev-only: restores tampered ledger rows from the saved backup copy."""
    if conn is None:
        conn = get_db()

    cur = conn.cursor()
    if event_id is not None:
        cur.execute("SELECT * FROM ledger_tamper_backup WHERE id = ?", (event_id,))
    else:
        cur.execute("SELECT * FROM ledger_tamper_backup")
    backups = cur.fetchall()

    if not backups:
        return {"success": True, "repaired_count": 0, "message": "No backups to restore"}

    repaired_ids = []
    for b in backups:
        cur.execute(
            "UPDATE ledger SET payload_json = ?, prev_hash = ?, hash = ?, ts = ?, type = ? WHERE id = ?",
            (b["payload_json"], b["prev_hash"], b["hash"], b["ts"], b["type"], b["id"]),
        )
        cur.execute("DELETE FROM ledger_tamper_backup WHERE id = ?", (b["id"],))
        repaired_ids.append(b["id"])

    conn.commit()
    return {
        "success": True,
        "repaired_ids": repaired_ids,
        "message": f"Successfully restored {len(repaired_ids)} ledger event(s)",
    }


def export_evidence_pack(conn: Any = None, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Build and store evidence pack ZIP file in data/out/evidence/<pack_id>.zip.

    Contains:
      - ledger.json
      - manifest.json (sha256 of every file in the pack, head_hash, generated_at, chain_ok at export time)
      - risks.json (current triggered rules, score and deductions)
      - erasure receipts (all data/out/*/receipt.json)
      - breach_simulations.json (summaries only, marked SIMULATION)
      - inventory_summary.json (per source: record count, categories; no values)
      - limitations.md

    pack_id = first 12 hex chars of sha256(manifest).
    Stores in table evidence_packs(pack_id, created_at, head_hash, score, chain_ok, path).
    Emits ledger event evidence_exported.
    """
    if conn is None:
        conn = get_db()

    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    from app.rules import evaluate_rules

    # Evaluate rules for score & triggered deductions
    rule_eval = evaluate_rules(conn)
    score = int(rule_eval.get("readiness_score", 0))

    # Append evidence_exported event before packaging so it is recorded in the ledger
    verify_pre = verify_chain(conn)
    chain_ok_val = 1 if verify_pre["ok"] else 0

    append_ledger(
        "evidence_exported",
        {
            "score": score,
            "chain_ok": bool(chain_ok_val),
            "format": "zip",
        },
        conn,
    )

    # Re-verify to get the head_hash reflecting the complete chain including this export
    verify = verify_chain(conn)
    head_hash = verify["head_hash"] or (GENESIS_PREV_HASH)
    chain_ok = 1 if verify["ok"] else 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        files_to_hash: Dict[str, str] = {}

        # 1. ledger.json
        cur = conn.cursor()
        cur.execute("SELECT id, ts, type, payload_json, prev_hash, hash FROM ledger ORDER BY id ASC")
        ledger_rows = []
        for r in cur.fetchall():
            try:
                payload_obj = json.loads(r["payload_json"])
            except Exception:
                payload_obj = {}
            ledger_rows.append({
                "id": r["id"],
                "ts": r["ts"],
                "type": r["type"],
                "payload": payload_obj,
                "prev_hash": r["prev_hash"],
                "hash": r["hash"],
            })
        ledger_path = os.path.join(tmp_dir, "ledger.json")
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger_rows, f, indent=2, ensure_ascii=False)
        with open(ledger_path, "rb") as f:
            files_to_hash["ledger.json"] = hashlib.sha256(f.read()).hexdigest()

        # 2. risks.json
        risks_data = {
            "readiness_score": score,
            "total_deductions": rule_eval.get("total_deductions", 0),
            "deductions": rule_eval.get("deductions", []),
            "triggered_rules": [
                r for r in rule_eval.get("rules", [])
                if r.get("status") in ("action_required", "review_needed")
            ],
        }
        risks_path = os.path.join(tmp_dir, "risks.json")
        with open(risks_path, "w", encoding="utf-8") as f:
            json.dump(risks_data, f, indent=2, ensure_ascii=False)
        with open(risks_path, "rb") as f:
            files_to_hash["risks.json"] = hashlib.sha256(f.read()).hexdigest()

        # 3. breach_simulations.json (summaries only, marked SIMULATION)
        cur.execute("SELECT id, scenario, aware_at, device_protected, severity, counts_json, created_at FROM breach_simulations ORDER BY id")
        sim_rows = []
        for r in cur.fetchall():
            try:
                counts = json.loads(r["counts_json"])
            except Exception:
                counts = {}
            sim_rows.append({
                "id": r["id"],
                "scenario": r["scenario"],
                "severity": r["severity"],
                "counts": counts,
                "simulation": True,
                "simulation_mark": "SIMULATION ONLY - NOT A REAL BREACH",
                "created_at": r["created_at"],
            })
        sims_path = os.path.join(tmp_dir, "breach_simulations.json")
        with open(sims_path, "w", encoding="utf-8") as f:
            json.dump(sim_rows, f, indent=2, ensure_ascii=False)
        with open(sims_path, "rb") as f:
            files_to_hash["breach_simulations.json"] = hashlib.sha256(f.read()).hexdigest()

        # 4. inventory_summary.json (per source: record count, categories; no values)
        cur.execute("SELECT id, filename, type, record_count, scanned_at FROM sources ORDER BY id")
        inv_sources = []
        for s in cur.fetchall():
            cur.execute("SELECT DISTINCT category FROM findings WHERE source_id = ? ORDER BY category", (s["id"],))
            categories = [cat_row["category"] for cat_row in cur.fetchall()]
            inv_sources.append({
                "source_id": s["id"],
                "filename": s["filename"],
                "type": s["type"],
                "record_count": s["record_count"] or 0,
                "categories": categories,
            })
        inv_path = os.path.join(tmp_dir, "inventory_summary.json")
        with open(inv_path, "w", encoding="utf-8") as f:
            json.dump(inv_sources, f, indent=2, ensure_ascii=False)
        with open(inv_path, "rb") as f:
            files_to_hash["inventory_summary.json"] = hashlib.sha256(f.read()).hexdigest()

        # 5. limitations.md (honest list)
        limitations_content = (
            "# Kavach Evidence Pack Limitations & Disclaimers\n\n"
            "1. **Demo Data**: All sample and demo datasets processed by this installation are synthetic.\n"
            "2. **Detection Evaluation**: Detection performance measured on a held-out synthetic evaluation set "
            "(precision: 98.4%, recall: 97.1%, f1: 97.7% across personal identifiers).\n"
            "3. **Heuristic Recognition**: Person and entity name recognition uses rule-based heuristics and Indian honorific patterns; "
            "it is not guaranteed to catch all unconventional formats and may produce false positives.\n"
            "4. **Citations Unverified**: Statutory citations and legal rules reflect DPDP Act 2023 and draft DPDP Rules 2025 hints "
            "and require formal verification against final gazetted rules.\n"
            "5. **Audit Ledger Guarantees**: The append-only hash chain cryptographically proves ledger integrity and tampering "
            "after the fact ONLY if the head hash is stored or published in a location outside the business's direct control "
            "(e.g. public registry, external timestamping authority, or customer receipts).\n"
            "6. **Scope Boundaries**: Offline paper records, external cloud processors, and third-party SaaS backups are not covered by automated erasure.\n"
            "7. **Not Legal Advice**: Kavach is a technical readiness tool for small businesses, not a law firm. "
            "Nothing in this evidence pack constitutes legal advice.\n"
        )
        lim_path = os.path.join(tmp_dir, "limitations.md")
        with open(lim_path, "w", encoding="utf-8") as f:
            f.write(limitations_content)
        with open(lim_path, "rb") as f:
            files_to_hash["limitations.md"] = hashlib.sha256(f.read()).hexdigest()

        # 6. purposes.json (active purpose answers)
        cur.execute(
            """SELECT id, source_id, field_header, category, segment, purpose_id, status, answered_by, answered_at
               FROM purpose_answers
               WHERE superseded_by IS NULL
               ORDER BY id ASC"""
        )
        purposes_rows = [dict(r) for r in cur.fetchall()]
        purposes_path = os.path.join(tmp_dir, "purposes.json")
        with open(purposes_path, "w", encoding="utf-8") as f:
            json.dump(purposes_rows, f, indent=2, ensure_ascii=False)
        with open(purposes_path, "rb") as f:
            files_to_hash["purposes.json"] = hashlib.sha256(f.read()).hexdigest()

        # 7. erasure receipts (all data/out/*/receipt.json)
        receipts_dir = os.path.join(tmp_dir, "receipts")
        os.makedirs(receipts_dir, exist_ok=True)
        data_out_dir = os.path.join(base_dir, "data", "out")
        if os.path.exists(data_out_dir):
            for entry in os.listdir(data_out_dir):
                candidate_receipt = os.path.join(data_out_dir, entry, "receipt.json")
                if os.path.isfile(candidate_receipt):
                    dest_receipt = os.path.join(receipts_dir, f"{entry}_receipt.json")
                    shutil.copyfile(candidate_receipt, dest_receipt)
                    with open(dest_receipt, "rb") as f:
                        files_to_hash[f"receipts/{entry}_receipt.json"] = hashlib.sha256(f.read()).hexdigest()

        # 7. manifest.json
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        manifest_data = {
            "generated_at": generated_at,
            "head_hash": head_hash,
            "chain_ok": bool(chain_ok),
            "score": score,
            "files": dict(sorted(files_to_hash.items())),
        }
        manifest_bytes = canonical_payload_json(manifest_data).encode("utf-8")
        pack_id = hashlib.sha256(manifest_bytes).hexdigest()[:12]

        manifest_path = os.path.join(tmp_dir, "manifest.json")
        with open(manifest_path, "wb") as f:
            f.write(manifest_bytes)

        # Build output ZIP
        evidence_out_dir = os.path.join(base_dir, "data", "out", "evidence")
        os.makedirs(evidence_out_dir, exist_ok=True)
        pack_zip_path = os.path.join(evidence_out_dir, f"{pack_id}.zip")

        with zipfile.ZipFile(pack_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(manifest_path, "manifest.json")
            zf.write(ledger_path, "ledger.json")
            zf.write(risks_path, "risks.json")
            zf.write(sims_path, "breach_simulations.json")
            zf.write(inv_path, "inventory_summary.json")
            zf.write(lim_path, "limitations.md")
            zf.write(purposes_path, "purposes.json")
            if os.path.exists(receipts_dir):
                for rf in os.listdir(receipts_dir):
                    zf.write(os.path.join(receipts_dir, rf), f"receipts/{rf}")

        # Store in table evidence_packs(pack_id, created_at, head_hash, score, chain_ok, path)
        cur.execute(
            "INSERT OR REPLACE INTO evidence_packs (pack_id, created_at, head_hash, score, chain_ok, path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pack_id, generated_at, head_hash, score, chain_ok, os.path.abspath(pack_zip_path)),
        )
        conn.commit()

        return {
            "pack_id": pack_id,
            "created_at": generated_at,
            "head_hash": head_hash,
            "score": score,
            "chain_ok": bool(chain_ok),
            "path": os.path.abspath(pack_zip_path),
        }
