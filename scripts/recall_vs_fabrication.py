#!/usr/bin/env python3
"""Recall-vs-fabrication Pareto: pre-empts the "Gemini extracted less, so
naturally hallucinated less" critique.

A model that emits fewer fields has fewer chances to fabricate. The raw
hallucination rate (hallucinated / checked) corrects for this - but only
weakly, because models that emit fewer fields *also* tend to skip the
hard ones. So we report two quantities side by side per model:

  - extraction volume (strings_checked, numbers_checked = a recall proxy)
  - fabrication rate

A reviewer can then see whether Model X's low rate is "low fab on a
representative volume" (good) or "low fab because it didn't try" (less
interesting).

Also computes per-category recall rank vs fabrication rank, plus per-doc
scatter data ready to plot.

Usage:
    python scripts/recall_vs_fabrication.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path.cwd()
HALL = REPO / "results" / "hallucination_report.json"
OUT = REPO / "results" / "analysis" / "recall_vs_fabrication.json"

PUBLISHED_MODELS = ["gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"]


def main():
    rep = json.loads(HALL.read_text())

    out: dict = {"per_model": {}, "per_category": {}, "scatter": []}

    # Per-model totals
    for m in PUBLISHED_MODELS:
        o = rep[m]["aggregate"]["overall"]
        sc_s = o["strings_checked"]
        sc_n = o["numbers_checked"]
        hl_s = o["strings_hallucinated"]
        hl_n = o["numbers_hallucinated"]
        out["per_model"][m] = {
            "docs": o["docs"],
            "strings_checked_total": sc_s,
            "numbers_checked_total": sc_n,
            "strings_per_doc": sc_s / o["docs"] if o["docs"] else 0,
            "numbers_per_doc": sc_n / o["docs"] if o["docs"] else 0,
            "string_hallucination_rate": hl_s / sc_s if sc_s else None,
            "number_hallucination_rate": hl_n / sc_n if sc_n else None,
            # "Effective" fab count per doc: how many fabricated values
            # the user encounters per document. Combines volume × rate.
            "fabricated_per_doc": (hl_s + hl_n) / o["docs"] if o["docs"] else 0,
        }

    # Per-category cross-model
    cats = sorted({c for m in PUBLISHED_MODELS for c in rep[m]["aggregate"]["by_category"]})
    for cat in cats:
        out["per_category"][cat] = {}
        for m in PUBLISHED_MODELS:
            cb = rep[m]["aggregate"]["by_category"].get(cat, {})
            sc_s = cb.get("strings_checked", 0)
            sc_n = cb.get("numbers_checked", 0)
            hl_s = cb.get("strings_hallucinated", 0)
            hl_n = cb.get("numbers_hallucinated", 0)
            n_docs = cb.get("docs", 0)
            out["per_category"][cat][m] = {
                "docs": n_docs,
                "strings_per_doc": sc_s / n_docs if n_docs else 0,
                "numbers_per_doc": sc_n / n_docs if n_docs else 0,
                "string_rate": hl_s / sc_s if sc_s else None,
                "number_rate": hl_n / sc_n if sc_n else None,
            }

    # Per-doc scatter rows (ready to plot)
    for m in PUBLISHED_MODELS:
        for k, doc in rep[m]["docs"].items():
            out["scatter"].append({
                "model": m,
                "doc": k,
                "category": k.split("/", 1)[1] if "/" in k else "unknown",
                "difficulty": k.split("_", 1)[0],
                "strings_checked": doc["strings_checked"],
                "numbers_checked": doc["numbers_checked"],
                "strings_hallucinated": doc["strings_hallucinated"],
                "numbers_hallucinated": doc["numbers_hallucinated"],
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT}")

    # Printable summary
    print("\n" + "=" * 78)
    print("RECALL × FABRICATION - per-model totals")
    print("=" * 78)
    print(f"{'model':<14} {'str/doc':>10} {'num/doc':>10} {'str_rate':>10} "
          f"{'num_rate':>10} {'fabs/doc':>10}")
    for m in PUBLISHED_MODELS:
        r = out["per_model"][m]
        sr = r["string_hallucination_rate"]
        nr = r["number_hallucination_rate"]
        print(f"{m:<14} {r['strings_per_doc']:>10.1f} {r['numbers_per_doc']:>10.1f} "
              f"{(sr*100 if sr is not None else 0):>9.1f}% "
              f"{(nr*100 if nr is not None else 0):>9.1f}% "
              f"{r['fabricated_per_doc']:>10.2f}")

    print("\nInterpretation:")
    print("  - High extraction volume + low fab rate = strong extraction")
    print("  - Low extraction volume + low fab rate = conservative model")
    print("  - The 'fabs/doc' column is the user-facing impact (total fabs ÷ docs).")


if __name__ == "__main__":
    main()
