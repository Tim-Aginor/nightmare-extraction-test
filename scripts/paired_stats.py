#!/usr/bin/env python3
"""Paired per-document analysis across the five published models.

Reads the existing hallucination_report.json and *_scores.json. Computes:

  1. Pairwise sign tests on per-doc fabrication counts (GPT-5.4 vs each
     other model). Each of the 148 docs is a paired observation: same
     packet, same difficulty, same prompt. The sign test asks whether
     GPT-5.4 produces more fabricated values than the comparator more
     often than chance.

  2. Per-doc Δ distribution (gpt54 fab count − comparator fab count)
     so you can quote "on N docs, GPT-5.4 fabricated ≥1 more numeric
     value than every other model simultaneously."

  3. Per-difficulty bootstrap 95% CIs on the published numeric/string
     hallucination rates. Resamples docs within difficulty.

This is the strongest defense against the "n=1, no statistics" critique:
the paired structure means we don't need more seeds to make a defensible
between-model claim, only to make a within-model rate claim.

Usage:
    python scripts/paired_stats.py
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path.cwd()
HALL = REPO / "results" / "hallucination_report.json"
OUT = REPO / "results" / "analysis" / "paired_stats.json"

PUBLISHED_MODELS = ["gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"]
PRIMARY = "gpt54"
COMPARATORS = ["gpt55", "opus47", "sonnet", "gemini_pro"]


def load() -> dict:
    return json.loads(HALL.read_text())


def per_doc_fab_counts(report: dict) -> dict[str, dict[str, dict]]:
    """{model: {doc_key: {strings, numbers, total}}}."""
    out: dict[str, dict[str, dict]] = {}
    for m in PUBLISHED_MODELS:
        out[m] = {}
        for k, v in report[m]["docs"].items():
            out[m][k] = {
                "strings": v["strings_hallucinated"],
                "numbers": v["numbers_hallucinated"],
                "total": v["strings_hallucinated"] + v["numbers_hallucinated"],
                "strings_checked": v["strings_checked"],
                "numbers_checked": v["numbers_checked"],
            }
    return out


def sign_test(wins: int, losses: int) -> dict:
    """Two-sided sign test on discordant pairs (ties dropped)."""
    n = wins + losses
    if n == 0:
        return {"n_discordant": 0, "p_two_sided": 1.0}
    # scipy.binomtest two-sided
    res = stats.binomtest(wins, n, p=0.5, alternative="two-sided")
    return {
        "n_discordant": n,
        "p_two_sided": float(res.pvalue),
        "win_rate": wins / n,
    }


def pairwise(counts: dict, primary: str, key: str = "total") -> dict:
    """Per-doc paired comparison: primary model vs each comparator."""
    out = {}
    pdocs = counts[primary]
    for other in COMPARATORS:
        odocs = counts[other]
        common = sorted(set(pdocs) & set(odocs))
        wins = losses = ties = 0
        deltas = []
        for k in common:
            p = pdocs[k][key]
            o = odocs[k][key]
            d = p - o
            deltas.append(d)
            if d > 0:
                wins += 1
            elif d < 0:
                losses += 1
            else:
                ties += 1
        sign = sign_test(wins, losses)
        deltas_arr = np.array(deltas)
        # Bootstrap 95% CI on the mean per-doc delta
        rng = np.random.default_rng(0)
        boots = np.array([
            deltas_arr[rng.integers(0, len(deltas_arr), len(deltas_arr))].mean()
            for _ in range(2000)
        ])
        out[other] = {
            "n_docs": len(common),
            f"{primary}_more": wins,
            f"{primary}_less": losses,
            "tied": ties,
            "sign_test": sign,
            "mean_delta": float(deltas_arr.mean()),
            "median_delta": float(np.median(deltas_arr)),
            "delta_ci95": [float(np.percentile(boots, 2.5)),
                           float(np.percentile(boots, 97.5))],
        }
    return out


def difficulty_bootstrap(report: dict) -> dict:
    """Per-difficulty bootstrap CI on string and numeric hallucination rates.

    Resamples docs within (model, difficulty) cell. Reports point estimate
    + 95% CI for both rates.
    """
    out: dict = {}
    rng = np.random.default_rng(42)

    # Group docs by difficulty for each model
    for m in PUBLISHED_MODELS:
        out[m] = {}
        by_diff: dict[str, list] = defaultdict(list)
        for doc_key, doc in report[m]["docs"].items():
            # doc_key is "N1_easy_70001/acord_101" → diff "N1"
            diff = doc_key.split("_", 1)[0]
            by_diff[diff].append(doc)

        for diff, docs in sorted(by_diff.items()):
            sc_str = sum(d["strings_checked"] for d in docs)
            hl_str = sum(d["strings_hallucinated"] for d in docs)
            sc_num = sum(d["numbers_checked"] for d in docs)
            hl_num = sum(d["numbers_hallucinated"] for d in docs)

            # Bootstrap by resampling docs (preserves within-doc dependence)
            arr = docs
            boots_str = []
            boots_num = []
            for _ in range(2000):
                idx = rng.integers(0, len(arr), len(arr))
                samp = [arr[i] for i in idx]
                tot_sc_s = sum(d["strings_checked"] for d in samp)
                tot_hl_s = sum(d["strings_hallucinated"] for d in samp)
                tot_sc_n = sum(d["numbers_checked"] for d in samp)
                tot_hl_n = sum(d["numbers_hallucinated"] for d in samp)
                boots_str.append(tot_hl_s / tot_sc_s if tot_sc_s else 0)
                boots_num.append(tot_hl_n / tot_sc_n if tot_sc_n else 0)

            out[m][diff] = {
                "n_docs": len(docs),
                "string_rate": hl_str / sc_str if sc_str else None,
                "string_rate_ci95": [
                    float(np.percentile(boots_str, 2.5)),
                    float(np.percentile(boots_str, 97.5)),
                ],
                "number_rate": hl_num / sc_num if sc_num else None,
                "number_rate_ci95": [
                    float(np.percentile(boots_num, 2.5)),
                    float(np.percentile(boots_num, 97.5)),
                ],
            }
    return out


def cross_model_agreement(counts: dict) -> dict:
    """How many docs is GPT-5.4 worse than ALL three comparators simultaneously?"""
    pdocs = counts[PRIMARY]
    odocs = {m: counts[m] for m in COMPARATORS}
    common = sorted(set(pdocs) & set.intersection(*(set(d) for d in odocs.values())))

    worse_all = better_all = mixed = neutral = 0
    worst_offenders = []  # docs where gpt54 is worse than all three by the largest margin
    for k in common:
        p = pdocs[k]["total"]
        diffs = [p - odocs[m][k]["total"] for m in COMPARATORS]
        if all(d > 0 for d in diffs):
            worse_all += 1
            worst_offenders.append((k, p, [odocs[m][k]["total"] for m in COMPARATORS],
                                    sum(diffs)))
        elif all(d < 0 for d in diffs):
            better_all += 1
        elif all(d == 0 for d in diffs):
            neutral += 1
        else:
            mixed += 1

    worst_offenders.sort(key=lambda x: -x[3])
    return {
        "n_docs": len(common),
        "gpt54_worse_than_all_three": worse_all,
        "gpt54_better_than_all_three": better_all,
        "gpt54_tied_with_all_three": neutral,
        "mixed": mixed,
        "top_15_worst_offenders": [
            {"doc": d, "gpt54_fabs": p, "comparator_fabs": others, "sum_delta": sd}
            for d, p, others, sd in worst_offenders[:15]
        ],
    }


def main():
    report = load()
    counts = per_doc_fab_counts(report)

    result = {
        "primary": PRIMARY,
        "comparators": COMPARATORS,
        "n_docs_per_model": {m: len(counts[m]) for m in PUBLISHED_MODELS},
        "totals": {
            m: {
                "fab_total": sum(c["total"] for c in counts[m].values()),
                "fab_strings": sum(c["strings"] for c in counts[m].values()),
                "fab_numbers": sum(c["numbers"] for c in counts[m].values()),
                "checked_strings": sum(c["strings_checked"] for c in counts[m].values()),
                "checked_numbers": sum(c["numbers_checked"] for c in counts[m].values()),
            }
            for m in PUBLISHED_MODELS
        },
        "pairwise_total_fabs": pairwise(counts, PRIMARY, "total"),
        "pairwise_numbers_only": pairwise(counts, PRIMARY, "numbers"),
        "pairwise_strings_only": pairwise(counts, PRIMARY, "strings"),
        "cross_model_agreement_total": cross_model_agreement(counts),
        "difficulty_bootstrap": difficulty_bootstrap(report),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"Wrote {OUT}")

    # Printable summary
    print("\n" + "=" * 78)
    print(f"PAIRED ANALYSIS: {PRIMARY} vs comparators (per-doc fabrication count)")
    print("=" * 78)
    for c in COMPARATORS:
        r = result["pairwise_total_fabs"][c]
        sign = r["sign_test"]
        ci = r["delta_ci95"]
        print(
            f"\n  vs {c}: {r[f'{PRIMARY}_more']}/{r['n_docs']} docs gpt54 worse, "
            f"{r[f'{PRIMARY}_less']} better, {r['tied']} tied"
        )
        print(
            f"    sign test: p={sign['p_two_sided']:.2e} on {sign['n_discordant']} discordant pairs"
        )
        print(
            f"    mean Δ (gpt54 − {c}): {r['mean_delta']:+.2f} fabs/doc "
            f"[95% CI {ci[0]:+.2f}, {ci[1]:+.2f}]"
        )

    print("\n" + "-" * 78)
    cm = result["cross_model_agreement_total"]
    print(
        f"\nCross-model agreement (n={cm['n_docs']}):"
        f"\n  gpt54 worse than ALL THREE comparators on:  {cm['gpt54_worse_than_all_three']} docs"
        f"\n  gpt54 better than ALL THREE comparators on: {cm['gpt54_better_than_all_three']} docs"
        f"\n  tied with all three on:                     {cm['gpt54_tied_with_all_three']} docs"
        f"\n  mixed:                                      {cm['mixed']} docs"
    )

    print("\n" + "-" * 78)
    print("\nDifficulty bootstrap CIs (numeric hallucination rate):")
    print(f"  {'diff':<6} " + " ".join(f"{m:>22}" for m in PUBLISHED_MODELS))
    diffs = ["N1", "N2", "N3", "N4", "N5"]
    for diff in diffs:
        row = [f"  {diff:<6}"]
        for m in PUBLISHED_MODELS:
            d = result["difficulty_bootstrap"][m].get(diff, {})
            r = d.get("number_rate")
            ci = d.get("number_rate_ci95", [None, None])
            if r is None:
                row.append(f"{'(n/a)':>22}")
            else:
                row.append(f"{r*100:>5.1f}% [{ci[0]*100:>4.1f},{ci[1]*100:>4.1f}]")
        print(" ".join(row))


if __name__ == "__main__":
    main()
