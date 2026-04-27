#!/usr/bin/env python3
"""GT-independent fabrication signal: internal arithmetic consistency.

The hallucination analyzer already runs `check_arithmetic` on every doc:
- SOV: sum of per-location TIVs vs reported `totals.tiv`
- Loss run: sum of claim incurred vs reported `grand_totals.incurred`

When these mismatch by >2% the doc is flagged with an arithmetic_error.
This is purely an internal-consistency check: both numbers come from the
extraction itself. Ground truth doesn't enter. So this signal survives
the "your GT is synthetic / your generator is biased" critique entirely.

This script aggregates those existing flags per model, broken down by
category and difficulty, plus the same overcount metric (`overcount_lists`)
which is also GT-independent at the count level (we count rows the model
emits, not whether they match GT).

Usage:
    python scripts/internal_consistency.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO = Path.cwd()
HALL = REPO / "results" / "hallucination_report.json"
OUT = REPO / "results" / "analysis" / "internal_consistency.json"

PUBLISHED_MODELS = ["gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"]


def difficulty_of(doc_key: str) -> str:
    return doc_key.split("_", 1)[0]


def category_of(doc_key: str) -> str:
    """Extract category from "N1_easy_70001/acord_101" → "acord_101"."""
    return doc_key.split("/", 1)[1] if "/" in doc_key else "unknown"


def aggregate(report: dict, model: str) -> dict:
    docs = report[model]["docs"]

    arith_errors_by_kind: dict[str, int] = defaultdict(int)
    arith_docs_by_diff: dict[str, int] = defaultdict(int)
    arith_docs_by_cat: dict[str, int] = defaultdict(int)

    overcount_excess_by_diff: dict[str, int] = defaultdict(int)
    overcount_excess_by_cat: dict[str, int] = defaultdict(int)
    overcount_docs_by_diff: dict[str, int] = defaultdict(int)
    overcount_docs_by_cat: dict[str, int] = defaultdict(int)

    by_diff_n: dict[str, int] = defaultdict(int)
    by_cat_n: dict[str, int] = defaultdict(int)

    arith_examples = []
    overcount_examples = []

    for k, doc in docs.items():
        diff = difficulty_of(k)
        cat = category_of(k)
        by_diff_n[diff] += 1
        by_cat_n[cat] += 1

        for ae in doc.get("arithmetic_errors", []):
            arith_errors_by_kind[ae.get("kind", "unknown")] += 1
            if len(arith_examples) < 12:
                arith_examples.append({"doc": k, **ae})
        if doc.get("arithmetic_errors"):
            arith_docs_by_diff[diff] += 1
            arith_docs_by_cat[cat] += 1

        oc = doc.get("overcount_lists") or {}
        if oc:
            excess = sum(v["excess"] for v in oc.values())
            overcount_excess_by_diff[diff] += excess
            overcount_excess_by_cat[cat] += excess
            overcount_docs_by_diff[diff] += 1
            overcount_docs_by_cat[cat] += 1
            if len(overcount_examples) < 12:
                overcount_examples.append({
                    "doc": k,
                    "lists": {kk: vv for kk, vv in oc.items()},
                })

    return {
        "model": model,
        "arithmetic_errors_by_kind": dict(arith_errors_by_kind),
        "arith_error_docs_by_difficulty": dict(arith_docs_by_diff),
        "arith_error_docs_by_category": dict(arith_docs_by_cat),
        "overcount_excess_by_difficulty": dict(overcount_excess_by_diff),
        "overcount_excess_by_category": dict(overcount_excess_by_cat),
        "overcount_docs_by_difficulty": dict(overcount_docs_by_diff),
        "overcount_docs_by_category": dict(overcount_docs_by_cat),
        "docs_by_difficulty": dict(by_diff_n),
        "docs_by_category": dict(by_cat_n),
        "examples": {
            "arithmetic_errors": arith_examples,
            "overcount": overcount_examples,
        },
    }


def main():
    report = json.loads(HALL.read_text())
    out = {m: aggregate(report, m) for m in PUBLISHED_MODELS}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT}")

    # Printable summary
    print("\n" + "=" * 78)
    print("INTERNAL CONSISTENCY (GT-INDEPENDENT) - by model")
    print("=" * 78)
    print(f"{'model':<14} {'tiv_mismatch':>14} {'incurred_mismatch':>18} "
          f"{'overcount_docs':>14} {'overcount_excess':>16}")
    for m, rep in out.items():
        tiv = rep["arithmetic_errors_by_kind"].get("tiv_sum_mismatch", 0)
        inc = rep["arithmetic_errors_by_kind"].get("incurred_sum_mismatch", 0)
        oc_docs = sum(rep["overcount_docs_by_difficulty"].values())
        oc_excess = sum(rep["overcount_excess_by_difficulty"].values())
        print(f"{m:<14} {tiv:>14} {inc:>18} {oc_docs:>14} {oc_excess:>16}")

    # Per-difficulty overcount
    print()
    print("Overcount excess by difficulty (extra rows beyond GT):")
    diffs = ["N1", "N2", "N3", "N4", "N5"]
    print(f"  {'diff':<6} " + "  ".join(f"{m:>14}" for m in PUBLISHED_MODELS))
    for d in diffs:
        row = [f"  {d:<6}"]
        for m in PUBLISHED_MODELS:
            v = out[m]["overcount_excess_by_difficulty"].get(d, 0)
            row.append(f"{v:>14}")
        print("  ".join(row))

    print()
    print("Arithmetic-error docs by difficulty (TIV/incurred sum mismatch):")
    print(f"  {'diff':<6} " + "  ".join(f"{m:>14}" for m in PUBLISHED_MODELS))
    for d in diffs:
        row = [f"  {d:<6}"]
        for m in PUBLISHED_MODELS:
            v = out[m]["arith_error_docs_by_difficulty"].get(d, 0)
            row.append(f"{v:>14}")
        print("  ".join(row))


if __name__ == "__main__":
    main()
