"""Inventory and Entity Resolution module for Kavach."""
import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app.detect import scan_file, hash_value, mask_value
from app.db import get_db

SENSITIVE_CATEGORIES = {"aadhaar", "health_term", "bank_account", "pan"}


def make_record_key(source: str, location: str) -> str:
    """Format record_key: source + sheet/row for tabular files, line number for chat."""
    if location.startswith("line "):
        return location
    # Tabular: drop the column part (/C\d+)
    sheet_row = re.sub(r"/C\d+$", "", location)
    return f"{source}:{sheet_row}"


def mask_name(name: str) -> str:
    """Mask name like 'Person 07 (R**** K***)'."""
    if not name:
        return "****"
    words = name.strip().split()
    masked_words = []
    for w in words:
        if len(w) <= 1:
            masked_words.append(w)
        else:
            masked_words.append(w[0].upper() + "*" * min(4, len(w) - 1))
    return " ".join(masked_words)


class UnionFind:
    """Union-Find disjoint-set data structure."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            return x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        rx = self.find(x)
        ry = self.find(y)
        if rx != ry:
            self.parent[rx] = ry


def scan_and_ingest_file(fpath: str, conn=None) -> int:
    """Scan a file and ingest findings into DB. Returns source_id."""
    if conn is None:
        conn = get_db()

    filename = os.path.basename(fpath)
    ext = os.path.splitext(filename)[1].lstrip(".").lower()

    # Check if source already exists
    cur = conn.cursor()
    cur.execute("SELECT id FROM sources WHERE filename = ?", (filename,))
    row = cur.fetchone()
    if row:
        source_id = row["id"]
        # Clear previous findings and person_records for this source to prevent duplication
        cur.execute("DELETE FROM findings WHERE source_id = ?", (source_id,))
        cur.execute("DELETE FROM person_records WHERE source_id = ?", (source_id,))
        cur.execute("UPDATE sources SET scanned_at = CURRENT_TIMESTAMP WHERE id = ?", (source_id,))
    else:
        cur.execute(
            "INSERT INTO sources (filename, type, record_count) VALUES (?, ?, 0)",
            (filename, ext),
        )
        source_id = cur.lastrowid

    # Scan the file
    findings = scan_file(fpath)
    distinct_records = set()

    for f in findings:
        rec_key = make_record_key(filename, f["location"])
        distinct_records.add(rec_key)
        meta_json = json.dumps(f["meta"]) if "meta" in f else None

        cur.execute(
            """INSERT INTO findings 
               (source_id, record_key, location, category, masked_sample, value_hash, confidence, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_id,
                rec_key,
                f["location"],
                f["category"],
                f["masked_sample"],
                f["value_hash"],
                f["confidence"],
                meta_json,
            ),
        )

    # Update record_count
    cur.execute(
        "UPDATE sources SET record_count = ? WHERE id = ?",
        (len(distinct_records), source_id),
    )
    conn.commit()
    return source_id


def run_entity_resolution(conn=None):
    """Run entity resolution over all ingested findings and populate people and person_records."""
    if conn is None:
        conn = get_db()

    cur = conn.cursor()

    # Fetch all findings
    cur.execute("SELECT id, source_id, record_key, category, masked_sample, value_hash, meta_json FROM findings")
    all_findings = cur.fetchall()

    if not all_findings:
        return

    # Group findings by record: (source_id, record_key)
    record_findings = defaultdict(list)
    for f in all_findings:
        rec_id = (f["source_id"], f["record_key"])
        record_findings[rec_id].append(f)

    # Index records by strong identifiers: phone, email, aadhaar
    strong_to_records = defaultdict(set)
    # Index records by name hash
    name_to_records = defaultdict(set)
    # Best masked name per record
    record_name_hint = {}

    for rec_id, f_list in record_findings.items():
        for f in f_list:
            cat = f["category"]
            v_hash = f["value_hash"]
            if cat in {"phone", "email", "aadhaar"}:
                strong_to_records[(cat, v_hash)].add(rec_id)
            elif cat == "name":
                name_to_records[v_hash].add(rec_id)
                if rec_id not in record_name_hint:
                    record_name_hint[rec_id] = f["masked_sample"]

    uf = UnionFind()
    strong_linked_records = set()

    # Stage 1: Union records sharing strong identifiers (phone, email, aadhaar)
    for (cat, v_hash), rec_set in strong_to_records.items():
        rec_list = list(rec_set)
        for i in range(len(rec_list)):
            strong_linked_records.add(rec_list[i])
            if i > 0:
                uf.union(rec_list[0], rec_list[i])

    # Stage 2: Records that link by name hash (e.g. chat senders and name-only records)
    for name_hash, rec_set in name_to_records.items():
        rec_list = list(rec_set)
        for i in range(len(rec_list)):
            if i > 0:
                uf.union(rec_list[0], rec_list[i])

    # Ensure every record is in UF
    for rec_id in record_findings.keys():
        uf.find(rec_id)

    # Group records into clusters
    clusters = defaultdict(list)
    for rec_id in record_findings.keys():
        root = uf.find(rec_id)
        clusters[root].append(rec_id)

    # Sort clusters deterministically: multi-source clusters first, then by record count
    sorted_clusters = sorted(
        clusters.values(),
        key=lambda cl: (-len(set(r[0] for r in cl)), -len(cl), cl[0]),
    )

    # Clear existing people and person_records
    cur.execute("DELETE FROM person_records")
    cur.execute("DELETE FROM people")

    # Persist people and person_records
    for p_idx, cluster in enumerate(sorted_clusters, start=1):
        # Determine person label and masked name
        masked_name = None
        name_hash = None
        for rec_id in cluster:
            if rec_id in record_name_hint:
                masked_name = record_name_hint[rec_id]
                # get name_hash from findings
                for f in record_findings[rec_id]:
                    if f["category"] == "name":
                        name_hash = f["value_hash"]
                        break
                break

        if not masked_name:
            masked_name = "Unknown"

        # Format label: "Person 01 (R**** K***)"
        label = f"Person {p_idx:02d} ({masked_name})"

        cur.execute(
            "INSERT INTO people (id, label, masked_name, name_hash) VALUES (?, ?, ?, ?)",
            (p_idx, label, masked_name, name_hash),
        )

        # Insert person_records
        for (source_id, rec_key) in cluster:
            rec_id = (source_id, rec_key)
            # Check if this record shares a strong identifier
            has_strong = rec_id in strong_linked_records
            if has_strong:
                link_type = "strong"
                link_confidence = 1.0
            else:
                link_type = "name"
                link_confidence = 0.6

            cur.execute(
                """INSERT INTO person_records (person_id, source_id, record_key, link_type, link_confidence)
                   VALUES (?, ?, ?, ?, ?)""",
                (p_idx, source_id, rec_key, link_type, link_confidence),
            )

    conn.commit()


def get_inventory_summary(conn=None) -> Dict:
    """Compute per-source summary and overall stats."""
    if conn is None:
        conn = get_db()

    cur = conn.cursor()
    cur.execute("SELECT id, filename, type, record_count, scanned_at FROM sources ORDER BY id")
    sources = cur.fetchall()

    sources_summary = []
    total_findings_count = 0
    total_records_count = 0

    for s in sources:
        s_id = s["id"]
        # Fetch findings for this source
        cur.execute("SELECT category, meta_json FROM findings WHERE source_id = ?", (s_id,))
        f_rows = cur.fetchall()
        total_findings_count += len(f_rows)
        total_records_count += s["record_count"]

        categories = sorted(set(r["category"] for r in f_rows))

        # Check sensitive flag: Aadhaar, health_term, bank_account, PAN, minors
        is_sensitive = any(cat in SENSITIVE_CATEGORIES for cat in categories)
        if not is_sensitive:
            for r in f_rows:
                if r["category"] == "dob" and r["meta_json"]:
                    try:
                        meta = json.loads(r["meta_json"])
                        if meta.get("is_minor"):
                            is_sensitive = True
                            break
                    except json.JSONDecodeError:
                        pass

        sources_summary.append({
            "id": s["id"],
            "filename": s["filename"],
            "type": s["type"],
            "record_count": s["record_count"],
            "findings_count": len(f_rows),
            "categories_present": categories,
            "has_sensitive": is_sensitive,
            "scanned_at": s["scanned_at"],
        })

    cur.execute("SELECT COUNT(*) as count FROM people")
    people_count = cur.fetchone()["count"]

    return {
        "sources": sources_summary,
        "total_sources": len(sources_summary),
        "total_records": total_records_count,
        "total_findings": total_findings_count,
        "total_people": people_count,
    }


def scan_demo_data(conn=None, data_dir: Optional[str] = None):
    """Scan all standard files from data_dir (defaults to data/demo)."""
    if conn is None:
        conn = get_db()

    if data_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, "data", "demo")

    # Clear previous DB data to ensure clean state
    cur = conn.cursor()
    cur.execute("DELETE FROM findings")
    cur.execute("DELETE FROM person_records")
    cur.execute("DELETE FROM people")
    cur.execute("DELETE FROM sources")
    conn.commit()

    files = ["patients.xlsx", "billing.csv", "staff.csv", "appointments_form.csv", "whatsapp_chat.txt"]
    for fname in files:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            scan_and_ingest_file(fpath, conn)

    run_entity_resolution(conn)
