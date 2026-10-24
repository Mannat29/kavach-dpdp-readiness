"""Evaluation module: compare scan results against ground truth."""
import argparse
import json
import os
import sys
from typing import Dict, Any

from app.detect import scan_file


def evaluate(data_dir: str = None, dataset: str = "demo") -> Dict[str, Any]:
    """Run evaluation on a dataset directory and print/return results."""
    if data_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder = "demo_hard" if dataset == "hard" else "demo"
        data_dir = os.path.join(base_dir, "data", folder)

    gt_path = os.path.join(data_dir, "ground_truth.json")
    if not os.path.exists(gt_path):
        print(f"ERROR: ground_truth.json not found in {data_dir}.")
        return {}

    with open(gt_path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Build ground truth set: (source, location, category)
    gt_set = set()
    gt_categories = set()
    for item in ground_truth:
        gt_set.add((item["source"], item["location"], item["category"]))
        gt_categories.add(item["category"])

    # Scan all supported files in dataset directory
    supported_exts = (".xlsx", ".csv", ".txt")
    files = sorted([f for f in os.listdir(data_dir) if f.endswith(supported_exts)])
    all_findings = []
    for fname in files:
        fpath = os.path.join(data_dir, fname)
        findings = scan_file(fpath)
        all_findings.extend(findings)

    # Build predicted set
    pred_set = set()
    pred_categories = set()
    for f in all_findings:
        pred_set.add((f["source"], f["location"], f["category"]))
        pred_categories.add(f["category"])

    # Every category in ground truth must be evaluated and printed
    categories = sorted(gt_categories | pred_categories)
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

    # Overall totals - sum of all category rows
    total_tp = sum(r["tp"] for r in results.values())
    total_fp = sum(r["fp"] for r in results.values())
    total_fn = sum(r["fn"] for r in results.values())
    overall_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    overall_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) > 0 else 0.0

    overall = {
        "tp": total_tp,
        "fp": total_fp,
        "fn": total_fn,
        "precision": overall_p,
        "recall": overall_r,
        "f1": overall_f1,
    }

    # Print table
    print(f"\nEvaluation Report: dataset='{dataset}' ({data_dir})")
    print(f"{'Category':<15} {'TP':>4} {'FP':>4} {'FN':>4} {'Prec':>6} {'Recall':>6} {'F1':>6}")
    print("-" * 55)
    for cat in categories:
        r = results[cat]
        print(f"{cat:<15} {r['tp']:>4} {r['fp']:>4} {r['fn']:>4} {r['precision']:>6.2f} {r['recall']:>6.2f} {r['f1']:>6.2f}")
    print("-" * 55)
    print(f"{'OVERALL':<15} {total_tp:>4} {total_fp:>4} {total_fn:>4} {overall_p:>6.2f} {overall_r:>6.2f} {overall_f1:>6.2f}")
    print()

    # Check acceptance criteria for demo set
    critical = {"aadhaar", "phone", "email", "pan", "gstin"}
    issues = []
    if dataset == "demo":
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
        else:
            print("All acceptance criteria met.")

    return {
        "categories": results,
        "overall": overall,
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate detection against ground truth.")
    parser.add_argument("--set", choices=["demo", "hard"], default="demo", help="Dataset to evaluate (demo or hard)")
    args = parser.parse_args()
    res = evaluate(dataset=args.set)
    if args.set == "demo" and res.get("issues"):
        sys.exit(1)


if __name__ == "__main__":
    main()
