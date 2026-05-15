#!/usr/bin/env python3
"""All-pairs paired per-document analysis across the published models.

Reads the existing hallucination_report.json. Computes:

  1. Pairwise sign tests on per-doc fabrication counts for every unique
     (model_i, model_j) pair. Each of the 148 docs is a paired observation:
     same packet, same difficulty, same prompt. The sign test asks whether
     model_i produces more fabricated values than model_j more often than
     chance.

  2. Holm-Bonferroni correction across the full family of tests
     (n_unique_pairs × 3 metrics: total / numbers / strings). Adjusted
     p-values reported alongside the raw ones.

  3. Per-doc Δ distribution for every pair (mean, median, bootstrap 95% CI
     with seed pinning for reproducibility).

  4. Per-difficulty bootstrap 95% CIs on the per-model rates.

  5. Cross-model agreement: for each model, how many docs is it strictly
     worse than every other on this run? (replaces the gpt54-centric
     "worse than ALL THREE" framing now that GPT-5.5 is in the lineup
     and also a top outlier.)

History: pre-2026-05-11 this script hard-coded PRIMARY = "gpt54" and
COMPARATORS = the other 4 models. With GPT-5.5 now in the lineup AND
showing string rates higher than GPT-5.4, the gpt54-centric framing
miscounts the cross-model story. Refactored to all-pairs.

Usage:
    python scripts/paired_stats.py [--effort default|high|xhigh|all]
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path.cwd()
HALL = REPO / "results" / "hallucination_report.json"
OUT = REPO / "results" / "analysis" / "paired_stats.json"

PUBLISHED_MODELS = ["gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"]
EFFORTS = ("default", "high", "xhigh")


def model_keys_at_effort(effort: str) -> list[str]:
    """Map ('default'|'high'|'xhigh') × base-model to the hallucination_report key."""
    suffix = "" if effort == "default" else f"_{effort}"
    return [f"{m}{suffix}" for m in PUBLISHED_MODELS]


def load() -> dict:
    return json.loads(HALL.read_text())


def per_doc_fab_counts(report: dict, model_keys: list[str]) -> dict[str, dict[str, dict]]:
    """{model_key: {doc_key: {strings, numbers, total}}}."""
    out: dict[str, dict[str, dict]] = {}
    for m in model_keys:
        if m not in report:
            continue
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
        return {"n_discordant": 0, "p_two_sided": 1.0, "win_rate": None}
    res = stats.binomtest(wins, n, p=0.5, alternative="two-sided")
    return {
        "n_discordant": n,
        "p_two_sided": float(res.pvalue),
        "win_rate": wins / n,
    }


def pair_compare(counts_a: dict, counts_b: dict, key: str = "total",
                 boot_seed: int = 0) -> dict:
    """Per-doc paired comparison: counts_a vs counts_b on the given metric.

    Returns wins from a's perspective (a > b on more docs ⇒ wins > losses).
    """
    common = sorted(set(counts_a) & set(counts_b))
    wins = losses = ties = 0
    deltas = []
    for k in common:
        a = counts_a[k][key]
        b = counts_b[k][key]
        d = a - b
        deltas.append(d)
        if d > 0:
            wins += 1
        elif d < 0:
            losses += 1
        else:
            ties += 1
    sign = sign_test(wins, losses)
    deltas_arr = np.array(deltas) if deltas else np.array([0])
    rng = np.random.default_rng(boot_seed)
    boots = np.array([
        deltas_arr[rng.integers(0, len(deltas_arr), len(deltas_arr))].mean()
        for _ in range(2000)
    ])
    return {
        "n_docs": len(common),
        "a_more": wins,
        "a_less": losses,
        "tied": ties,
        "sign_test": sign,
        "mean_delta": float(deltas_arr.mean()),
        "median_delta": float(np.median(deltas_arr)),
        "delta_ci95": [float(np.percentile(boots, 2.5)),
                       float(np.percentile(boots, 97.5))],
    }


def holm_bonferroni(p_values: dict[tuple, float]) -> dict[tuple, float]:
    """Family-wise error correction. Returns dict mapping label → adjusted p.

    Holm-Bonferroni is uniformly more powerful than Bonferroni at the same
    FWER level. The family is the full set of paired tests reported in the
    same run (all-pairs × 3 metrics per effort level).
    """
    items = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted: dict[tuple, float] = {}
    running_max = 0.0
    for i, (label, p) in enumerate(items):
        adj = p * (m - i)
        # Holm is monotone — adjusted p-values can never decrease as i grows.
        running_max = max(running_max, adj)
        adjusted[label] = min(1.0, running_max)
    return adjusted


def all_pairs(counts: dict[str, dict], metric: str = "total",
              effort_label: str = "default") -> dict:
    """Compute paired tests for every unique pair of models in `counts`.

    Returns {"<a>_vs_<b>": {result_dict, ...}}. The asymmetric naming
    encodes direction: a_more is "a has more fabs than b on this many
    docs."
    """
    models = sorted(counts.keys())
    pairs = list(combinations(models, 2))
    raw_p: dict[tuple, float] = {}
    results: dict[str, dict] = {}
    for i, (a, b) in enumerate(pairs):
        cmp = pair_compare(counts[a], counts[b], metric, boot_seed=i)
        label = f"{a}_vs_{b}"
        results[label] = cmp
        raw_p[label] = cmp["sign_test"]["p_two_sided"]

    # Holm correction over the full pairs × this metric (the cross-metric
    # family correction is applied in main() across the consolidated set).
    adj = holm_bonferroni(raw_p)
    for label, r in results.items():
        r["sign_test"]["p_two_sided_holm_within_metric"] = adj[label]
    return results


def difficulty_bootstrap(report: dict, model_keys: list[str]) -> dict:
    """Per-difficulty bootstrap CI on rates. Resamples docs within each cell."""
    out: dict = {}
    rng = np.random.default_rng(42)

    for m in model_keys:
        if m not in report:
            continue
        out[m] = {}
        by_diff: dict[str, list] = defaultdict(list)
        for doc_key, doc in report[m]["docs"].items():
            diff = doc_key.split("_", 1)[0]
            by_diff[diff].append(doc)

        for diff, docs in sorted(by_diff.items()):
            sc_str = sum(d["strings_checked"] for d in docs)
            hl_str = sum(d["strings_hallucinated"] for d in docs)
            sc_num = sum(d["numbers_checked"] for d in docs)
            hl_num = sum(d["numbers_hallucinated"] for d in docs)

            boots_str = []
            boots_num = []
            for _ in range(2000):
                idx = rng.integers(0, len(docs), len(docs))
                samp = [docs[i] for i in idx]
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


def per_model_dominance(counts: dict[str, dict]) -> dict:
    """For each model, how many docs is it strictly worse / better than
    EVERY other model in the cohort, on total fabrication count?

    Replaces the prior gpt54-centric "worse than all 3" reporting.
    """
    models = sorted(counts.keys())
    if len(models) < 2:
        return {}
    common = sorted(set.intersection(*(set(counts[m]) for m in models)))
    out = {m: {"worse_than_all_others": 0, "better_than_all_others": 0,
               "tied_with_all_others": 0, "mixed": 0} for m in models}
    for k in common:
        vals = {m: counts[m][k]["total"] for m in models}
        for m in models:
            others = [vals[o] for o in models if o != m]
            if all(vals[m] > o for o in others):
                out[m]["worse_than_all_others"] += 1
            elif all(vals[m] < o for o in others):
                out[m]["better_than_all_others"] += 1
            elif all(vals[m] == o for o in others):
                out[m]["tied_with_all_others"] += 1
            else:
                out[m]["mixed"] += 1
    return {"n_docs": len(common), "per_model": out}


def run_effort(report: dict, effort: str) -> dict:
    """Run the full all-pairs analysis at one effort level."""
    keys = [k for k in model_keys_at_effort(effort) if k in report]
    counts = per_doc_fab_counts(report, keys)
    if len(counts) < 2:
        return {"effort": effort, "skipped": "fewer than 2 models present"}

    pairwise_total = all_pairs(counts, "total", effort)
    pairwise_num = all_pairs(counts, "numbers", effort)
    pairwise_str = all_pairs(counts, "strings", effort)

    # Cross-metric Holm: family is all_pairs × 3 metrics for this effort
    family_p: dict[tuple, float] = {}
    for label, r in pairwise_total.items():
        family_p[("total", label)] = r["sign_test"]["p_two_sided"]
    for label, r in pairwise_num.items():
        family_p[("numbers", label)] = r["sign_test"]["p_two_sided"]
    for label, r in pairwise_str.items():
        family_p[("strings", label)] = r["sign_test"]["p_two_sided"]
    adj_family = holm_bonferroni(family_p)
    for (metric, label), adj in adj_family.items():
        target = {"total": pairwise_total, "numbers": pairwise_num,
                  "strings": pairwise_str}[metric]
        target[label]["sign_test"]["p_two_sided_holm_family"] = adj

    return {
        "effort": effort,
        "models": keys,
        "n_docs_per_model": {m: len(counts[m]) for m in keys},
        "totals": {
            m: {
                "fab_total": sum(c["total"] for c in counts[m].values()),
                "fab_strings": sum(c["strings"] for c in counts[m].values()),
                "fab_numbers": sum(c["numbers"] for c in counts[m].values()),
                "checked_strings": sum(c["strings_checked"] for c in counts[m].values()),
                "checked_numbers": sum(c["numbers_checked"] for c in counts[m].values()),
            }
            for m in keys
        },
        "pairwise_total_fabs": pairwise_total,
        "pairwise_numbers_only": pairwise_num,
        "pairwise_strings_only": pairwise_str,
        "dominance_total": per_model_dominance(counts),
        "difficulty_bootstrap": difficulty_bootstrap(report, keys),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--effort", choices=("default", "high", "xhigh", "all"),
                    default="all")
    args = ap.parse_args()

    report = load()
    efforts = EFFORTS if args.effort == "all" else (args.effort,)
    result = {effort: run_effort(report, effort) for effort in efforts}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"Wrote {OUT}")

    # Printable summary — one block per effort level
    for effort, eff_result in result.items():
        if eff_result.get("skipped"):
            print(f"\n[{effort}] {eff_result['skipped']}")
            continue
        print("\n" + "=" * 78)
        print(f"PAIRED ANALYSIS @ effort={effort}  (all-pairs sign tests)")
        print("=" * 78)
        models = eff_result["models"]
        print(f"models: {', '.join(models)}")
        print(f"n_docs per model: {eff_result['n_docs_per_model']}")
        print(f"\nPairwise total fabrications (sign test, p w/ Holm-family correction):")
        for label, r in sorted(eff_result["pairwise_total_fabs"].items()):
            sign = r["sign_test"]
            ci = r["delta_ci95"]
            a, b = label.split("_vs_")
            print(
                f"  {a:>14} vs {b:<14} | "
                f"{a} more on {r['a_more']:>3}/{r['n_docs']}, less on {r['a_less']:>3} | "
                f"mean Δ={r['mean_delta']:+.2f} [95% CI {ci[0]:+.2f},{ci[1]:+.2f}] | "
                f"p_raw={sign['p_two_sided']:.2e} p_holm={sign['p_two_sided_holm_family']:.2e}"
            )

        dom = eff_result["dominance_total"]
        print(f"\nDominance (over n={dom['n_docs']} common docs):")
        for m, d in sorted(dom["per_model"].items()):
            print(
                f"  {m:<16} worse-than-all-others={d['worse_than_all_others']:>3}  "
                f"better-than-all-others={d['better_than_all_others']:>3}  "
                f"tied-all={d['tied_with_all_others']:>3}  mixed={d['mixed']:>3}"
            )


if __name__ == "__main__":
    main()
