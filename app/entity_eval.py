"""Entity resolution evaluation module: pairwise precision/recall against people_truth.json."""
import json
import os
from collections import defaultdict
from itertools import combinations
from typing import Dict, Any

from app.db import init_db, get_db
from app.inventory import scan_demo_data


def evaluate_entity_resolution(demo_dir: str = None) -> Dict[str, Any]:
    """Evaluate entity resolution against people_truth.json."""
    if demo_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        demo_dir = os.path.join(base_dir, "data", "demo")

    pt_path = os.path.join(demo_dir, "people_truth.json")
    if not os.path.exists(pt_path):
        print(f"ERROR: {pt_path} not found. Run scripts/seed.py first.")
        return {}

    with open(pt_path, encoding="utf-8") as f:
        people_truth = json.load(f)

    # Ensure DB is populated with demo data
    conn = get_db()
    init_db()

    # Check if DB has people; if not, scan demo data
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as count FROM person_records")
    if cur.fetchone()["count"] == 0:
        scan_demo_data(conn)

    # Build ground truth mapping: (source, record_key) -> true_person_id
    gt_record_to_person = {}
    for p in people_truth:
        pid = p["person_id"]
        for r in p["records"]:
            key = (r["source"], r["record_key"])
            gt_record_to_person[key] = pid

    # Build predicted mapping from DB
    cur.execute("""
        SELECT pr.person_id, s.filename as source, pr.record_key 
        FROM person_records pr
        JOIN sources s ON pr.source_id = s.id
    """)
    pred_record_to_person = {}
    for row in cur.fetchall():
        key = (row["source"], row["record_key"])
        pred_record_to_person[key] = row["person_id"]

    # Evaluate pairwise on all records present in people_truth
    eval_records = list(gt_record_to_person.keys())
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for r1, r2 in combinations(eval_records, 2):
        gt_same = (gt_record_to_person[r1] == gt_record_to_person[r2])
        pred_same = (pred_record_to_person.get(r1) == pred_record_to_person.get(r2)) and (r1 in pred_record_to_person)

        if gt_same and pred_same:
            tp += 1
        elif not gt_same and pred_same:
            fp += 1
        elif gt_same and not pred_same:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print("\nEntity Resolution Evaluation (Pairwise):")
    print(f"Total evaluated records: {len(eval_records)} across 12 known people")
    print(f"Pairwise pairs: {len(eval_records) * (len(eval_records) - 1) // 2}")
    print(f"TP: {tp:<5} FP: {fp:<5} FN: {fn:<5} TN: {tn:<5}")
    print(f"Precision: {precision:.4f} | Recall: {recall:.4f} | F1: {f1:.4f}\n")

    # Demographic / Demo Patient Table
    cur.execute("SELECT id, label, masked_name FROM people ORDER BY id")
    people_rows = cur.fetchall()

    print(f"{'ID':<4} {'Label':<28} {'Sources':<8} {'Health Terms?':<14} {'Source Files'}")
    print("-" * 80)

    people_table = []
    for p in people_rows:
        pid = p["id"]
        # Find distinct sources for this person
        cur.execute("""
            SELECT DISTINCT s.filename 
            FROM person_records pr 
            JOIN sources s ON pr.source_id = s.id 
            WHERE pr.person_id = ?
        """, (pid,))
        src_files = [r["filename"] for r in cur.fetchall()]

        # Check if any finding has health_term
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM findings f 
            JOIN person_records pr ON f.source_id = pr.source_id AND f.record_key = pr.record_key 
            WHERE pr.person_id = ? AND f.category = 'health_term'
        """, (pid,))
        has_health = cur.fetchone()["count"] > 0
        health_str = "Yes" if has_health else "No"
        src_str = ", ".join(src_files)

        print(f"{pid:<4} {p['label']:<28} {len(src_files):<8} {health_str:<14} {src_str}")
        people_table.append({
            "id": pid,
            "label": p["label"],
            "source_count": len(src_files),
            "sources": src_files,
            "has_health": has_health,
        })
    print()

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "people_table": people_table,
    }


def main():
    evaluate_entity_resolution()


if __name__ == "__main__":
    main()
