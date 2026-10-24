"""Evaluation module: compare scan results against ground truth."""
import json
import os
import sys
from collections import defaultdict

from app.detect import scan_file


def main():
    demo_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo")
    gt_path = os.path.join(demo_dir, "ground_truth.json")

    if not os.path.exists(gt_path):
        print("ERROR: ground_truth.json not found. Run `python scripts/seed.py` first.")
        sys.exit(1)

    with open(gt_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Build ground truth set: (source, location, category)
    gt_set = set()
    for item in ground_truth:
        gt_set.add((item["source"], item["location"], item["category"]))

    # Scan all demo files
    files = ["patients.xlsx", "billing.csv", "staff.csv", "appointments_form.csv", "whatsapp_chat.txt"]
    all_findings = []
    for fname in files:
        fpath = os.path.join(demo_dir, fname)
        if not os.path.exists(fpath):
            print(f"  WARNING: {fname} not found, skipping")
            continue
        findings = scan_file(fpath)
        all_findings.extend(findings)

    # Build predicted set
    pred_set = set()
    for f in all_findings:
        pred_set.add((f["source"], f["location"], f["category"]))

    # Per-category metrics
    categories = sorted(set(c for _, _, c in gt_set | pred_set))
    results = {}

    for cat in categories:
        gt_cat = {(s, l) for s, l, c in gt_set if c == cat}
        pred_cat = {(s, l) for s, l, c in pred_set if c == cat}
        tp = len(gt_cat & pred_cat)
        fp = len(pred_cat - gt_cat)
        fn = len(gt_cat - pred_cat)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        results[cat] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}

    # Overall
    total_tp = sum(r["tp"] for r in results.values())
    total_fp = sum(r["fp"] for r in results.values())
    total_fn = sum(r["fn"] for r in results.values())
    overall_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) > 0 else 0.0

    # Print table
    print()
    print(f"{'Category':<15} {'TP':>4} {'FP':>4} {'FN':>4} {'Prec':>6} {'Recall':>6} {'F1':>6}")
    print("-" * 55)
    for cat in categories:
        r = results[cat]
        print(f"{cat:<15} {r['tp']:>4} {r['fp']:>4} {r['fn']:>4} {r['precision']:>6.2f} {r['recall']:>6.2f} {r['f1']:>6.2f}")
    print("-" * 55)
    print(f"{'OVERALL':<15} {total_tp:>4} {total_fp:>4} {total_fn:>4} {overall_p:>6.2f} {overall_r:>6.2f} {overall_f1:>6.2f}")
    print()

    # Check acceptance criteria
    critical = {"aadhaar", "phone", "email", "pan", "gstin"}
    issues = []
    for cat in critical:
        if cat in results:
            r = results[cat]
            if r["recall"] < 0.95:
                issues.append(f"{cat} recall {r['recall']:.2f} < 0.95")
            if r["precision"] < 0.90:
                issues.append(f"{cat} precision {r['precision']:.2f} < 0.90")

    if issues:
        print("ACCEPTANCE ISSUES:")
        for issue in issues:
            print(f"  - {issue}")
        # Print some FN details for debugging
        for cat in critical:
            if cat in results and results[cat]["fn"] > 0:
                gt_cat = {(s, l) for s, l, c in gt_set if c == cat}
                pred_cat = {(s, l) for s, l, c in pred_set if c == cat}
                fn_items = gt_cat - pred_cat
                if fn_items:
                    print(f"\n  {cat} false negatives (first 5):")
                    for s, l in list(fn_items)[:5]:
                        print(f"    {s} @ {l}")
        sys.exit(1)
    else:
        print("All acceptance criteria met.")


if __name__ == "__main__":
    main()
