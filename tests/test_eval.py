"""Tests for evaluation module."""
import json
import os
from app.eval import evaluate


def test_eval_categories_and_sum():
    """Verify all ground truth categories are evaluated and rows sum to OVERALL."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gt_path = os.path.join(base_dir, "data", "demo", "ground_truth.json")
    with open(gt_path, encoding="utf-8") as f:
        gt_data = json.load(f)

    gt_categories = set(item["category"] for item in gt_data)

    res = evaluate(dataset="demo")
    cat_results = res["categories"]
    overall = res["overall"]

    # 1. Every category in ground truth must be in cat_results
    for cat in gt_categories:
        assert cat in cat_results, f"Ground truth category '{cat}' missing from evaluation results"

    # Specifically PAN must be present
    assert "pan" in cat_results, "'pan' must be present in category results"

    # 2. Rows sum to OVERALL
    sum_tp = sum(r["tp"] for r in cat_results.values())
    sum_fp = sum(r["fp"] for r in cat_results.values())
    sum_fn = sum(r["fn"] for r in cat_results.values())

    assert sum_tp == overall["tp"], f"TP sum {sum_tp} does not equal overall TP {overall['tp']}"
    assert sum_fp == overall["fp"], f"FP sum {sum_fp} does not equal overall FP {overall['fp']}"
    assert sum_fn == overall["fn"], f"FN sum {sum_fn} does not equal overall FN {overall['fn']}"
