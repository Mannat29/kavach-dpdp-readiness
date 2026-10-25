"""Reset database, scan demo data, and import demo rights requests.

Usage:
    python scripts/demo_reset.py
"""
import os
import shutil
import sys

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.db import get_db, init_db
from app.inventory import scan_demo_data, get_inventory_summary
from app.rights import parse_whatsapp_text, process_intake
from app.ledger import append_ledger


def reset_demo():
    print("=" * 60)
    print("Kavach: Fresh Demo Reset")
    print("=" * 60)

    # 1. Reset database tables
    conn = get_db()
    init_db()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")
    tables = [
        "findings",
        "person_records",
        "people",
        "sources",
        "questionnaire",
        "risks",
        "rights_requests",
        "breach_simulations",
        "ledger",
        "evidence_packs",
        "ledger_tamper_backup",
        "purpose_answers",
    ]
    for table in tables:
        cur.execute(f"DELETE FROM {table}")
    try:
        cur.execute(
            "DELETE FROM sqlite_sequence WHERE name IN "
            "('sources', 'findings', 'people', 'person_records', 'risks', 'rights_requests', 'breach_simulations', 'ledger', 'evidence_packs', 'purpose_answers')"
        )
    except Exception:
        pass
    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    print("[1/3] Database cleared.")

    # Clean workspace and out directories
    for folder in ["workspace", "out"]:
        target_dir = os.path.join(BASE_DIR, "data", folder)
        if os.path.exists(target_dir):
            for fname in os.listdir(target_dir):
                fpath = os.path.join(target_dir, fname)
                try:
                    if os.path.isfile(fpath) or os.path.islink(fpath):
                        os.unlink(fpath)
                    elif os.path.isdir(fpath):
                        shutil.rmtree(fpath)
                except OSError:
                    pass
        else:
            os.makedirs(target_dir, exist_ok=True)

    # 2. Scan demo data files
    print("[2/3] Scanning demo files from data/demo/...")
    scan_demo_data(conn)
    summary = get_inventory_summary(conn)
    append_ledger("scan_completed", {"demo": True, "files_scanned": len(summary.get("sources", []))}, conn)
    print(f"      Scanned {len(summary.get('sources', []))} sources, found {summary.get('total_findings', 0)} PII findings across {summary.get('total_people', 0)} resolved people.")

    # 3. Import demo requests
    demo_requests_file = os.path.join(BASE_DIR, "data", "demo", "demo_requests.txt")
    if os.path.exists(demo_requests_file):
        with open(demo_requests_file, "r", encoding="utf-8") as f:
            raw_text = f.read()
        messages = parse_whatsapp_text(raw_text)
        created = process_intake(messages, conn)
        print(f"[3/3] Imported {len(created)} rights requests from demo_requests.txt.")
    else:
        print(f"[3/3] Warning: {demo_requests_file} not found; skipping request import.")

    print("=" * 60)
    print("Demo environment successfully restored!")
    print("=" * 60)


if __name__ == "__main__":
    reset_demo()
