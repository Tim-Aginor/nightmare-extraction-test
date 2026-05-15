#!/usr/bin/env python3
"""Aggregate per-cohort score files into a recall-side error breakdown.

Hallucination rate (from `hallucination_analysis.py`) is precision-side:
denominator = values the model emitted. A model that returns null on
hard fields gets a small denominator and looks better than a model that
attempts them.

This script reads the per-cohort `<cohort>/scores.json` files produced
by `score.py` (which now tracks correct/wrong/omitted counters per
field) and rolls them up into the recall-side complement:

- omission_rate_micro = fields-where-model-returned-null / GT-populated-fields
- wrong_value_rate_micro = fields-where-model-returned-wrong-value / GT-populated-fields
- any_error_rate_micro = (wrong + omitted) / GT-populated-fields
- correctness_rate_micro = correct / GT-populated-fields (= 1 - any_error_rate)

Output: `field_breakdown.json` with overall + by_category for each cohort.

Apurv's framing: "does hallucination rate include omissions?" — no,
that's precision-side. This is the recall-side answer. Surfacing both
keeps the headline honest.
"""

import argparse
import json
from pathlib import Path


COHORTS = [
    "gpt55", "gpt55_high", "gpt55_xhigh",
    "gpt54", "gpt54_high", "gpt54_xhigh",
    "opus47", "opus47_high", "opus47_xhigh",
    "sonnet", "sonnet_high", "sonnet_xhigh",
    "gemini_pro", "gemini_pro_high", "gemini_pro_xhigh",
]


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _from_scores(scores_path: Path) -> dict:
    s = json.loads(scores_path.read_text())
    agg = s["aggregate"]
    overall = agg.get("overall", {})

    out = {
        "overall": {
            "fields_scored": overall.get("fields_scored_total", 0),
            "fields_correct": overall.get("fields_correct_total", 0),
            "fields_wrong": overall.get("fields_wrong_total", 0),
            "fields_omitted": overall.get("fields_omitted_total", 0),
            "correctness_rate_micro": _rate(
                overall.get("fields_correct_total", 0),
                overall.get("fields_scored_total", 0),
            ),
            "wrong_value_rate_micro": overall.get("wrong_value_rate_micro"),
            "omission_rate_micro": overall.get("omission_rate_micro"),
            "any_error_rate_micro": overall.get("any_error_rate_micro"),
        },
        "by_category": {},
    }

    for cat, cat_agg in agg.items():
        if cat == "overall" or not isinstance(cat_agg, dict):
            continue
        out["by_category"][cat] = {
            "fields_scored": cat_agg.get("fields_scored_total", 0),
            "fields_correct": cat_agg.get("fields_correct_total", 0),
            "fields_wrong": cat_agg.get("fields_wrong_total", 0),
            "fields_omitted": cat_agg.get("fields_omitted_total", 0),
            "correctness_rate_micro": _rate(
                cat_agg.get("fields_correct_total", 0),
                cat_agg.get("fields_scored_total", 0),
            ),
            "wrong_value_rate_micro": cat_agg.get("wrong_value_rate_micro"),
            "omission_rate_micro": cat_agg.get("omission_rate_micro"),
            "any_error_rate_micro": cat_agg.get("any_error_rate_micro"),
        }

    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--results", type=Path, default=Path("results"))
    p.add_argument("--output", type=Path, default=Path("results/analysis/field_breakdown.json"))
    args = p.parse_args()

    out = {}
    for cohort in COHORTS:
        scores_path = args.results / cohort / "scores.json"
        if not scores_path.exists():
            print(f"  skip {cohort}: {scores_path} missing")
            continue
        out[cohort] = _from_scores(scores_path)
        ov = out[cohort]["overall"]
        print(f"  {cohort:22} fields={ov['fields_scored']:5} "
              f"correct={ov['correctness_rate_micro']*100:5.1f}%  "
              f"wrong={ov['wrong_value_rate_micro']*100:5.1f}%  "
              f"omitted={ov['omission_rate_micro']*100:5.1f}%")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
