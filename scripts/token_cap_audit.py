#!/usr/bin/env python3
"""Per-doc token usage histogram, binned by output-cap headroom.

All API providers now run at max_tokens = 32000 (single-cap regime).
Gemini runs without an explicit cap. This script sanity-checks that no
doc approached the 32k cap on any model; if one does, the analysis
should flag possible truncation.

NOTE on `n_docs`: this field reports the count of docs with parseable
"OK" lines in the corresponding log file, not the total docs scored.
For the published run, GPT-5.4 and Opus 4.7 have complete logs (148/148).
Gemini Pro has 147 (one FAIL line). Sonnet 4.6's log file covers 122/148
because the Sonnet run spanned multiple sessions and the earlier log
was rotated before this audit was added. The headline finding is about
GPT-5.4 specifically, and its log coverage is complete.

Usage:
    python scripts/token_cap_audit.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path.cwd()
LOGS = REPO / "logs"
OUT = REPO / "results" / "analysis" / "token_cap_audit.json"

# Map log file → published model name
LOG_TO_MODEL = {
    "logs_gpt55.txt": "gpt55",
    "logs_gpt54.txt": "gpt54",
    "logs_opus47_api.txt": "opus47",
    "logs_sonnet_api.txt": "sonnet",
    "logs_gemini_pro.txt": "gemini_pro",
}

# Configured output caps - all API providers at 32000, Gemini unset.
OUTPUT_CAPS = {
    "gpt55":      32000,
    "gpt54":      32000,
    "opus47":     32000,
    "sonnet":     32000,
    "gemini_pro": None,
}

# logs_gpt54.txt sample line:
#   "  OK  : N1_easy_70001/acord_101 | 3300 tok | $0.0269 | 15.7s"
LINE_RE = re.compile(
    r"OK\s*:\s*(?P<doc>\S+)\s*\|\s*(?P<tok>\d+)\s*tok\s*\|\s*\$(?P<cost>[\d.]+)\s*\|\s*(?P<elapsed>[\d.]+)s"
)


def parse_log(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(errors="ignore").splitlines():
        m = LINE_RE.search(line)
        if not m:
            continue
        rows.append({
            "doc": m.group("doc"),
            "tokens": int(m.group("tok")),
            "cost_usd": float(m.group("cost")),
            "elapsed_s": float(m.group("elapsed")),
        })
    return rows


def main():
    by_model: dict[str, list[dict]] = defaultdict(list)
    for log_name, model in LOG_TO_MODEL.items():
        path = LOGS / log_name
        if not path.exists():
            continue
        rows = parse_log(path)
        # Some doc keys appear in multiple log files (retries / continuations).
        # Prefer the latest occurrence per doc.
        existing = {r["doc"] for r in by_model[model]}
        for r in rows:
            if r["doc"] in existing:
                # Replace existing entry (latest log wins for that doc).
                by_model[model] = [x for x in by_model[model] if x["doc"] != r["doc"]]
                existing.discard(r["doc"])
            by_model[model].append(r)
            existing.add(r["doc"])

    out: dict = {"per_model": {}}
    for model, rows in by_model.items():
        if not rows:
            continue
        toks = sorted(r["tokens"] for r in rows)
        n = len(toks)
        cap = OUTPUT_CAPS.get(model)
        # Pretend cap=∞ when None for the headroom counts
        cap_for_hr = cap if cap else 10**9

        def pct(p: float) -> int:
            i = max(0, min(n - 1, int(p * (n - 1))))
            return toks[i]

        near_cap = [r for r in rows if r["tokens"] >= 0.75 * cap_for_hr]
        near_cap.sort(key=lambda r: -r["tokens"])

        out["per_model"][model] = {
            "n_docs": n,
            "configured_output_cap": cap,
            "total_tokens_p50": pct(0.50),
            "total_tokens_p90": pct(0.90),
            "total_tokens_p95": pct(0.95),
            "total_tokens_max": toks[-1],
            "docs_above_75pct_cap": sum(1 for r in rows if r["tokens"] >= 0.75 * cap_for_hr),
            "docs_above_90pct_cap": sum(1 for r in rows if r["tokens"] >= 0.90 * cap_for_hr),
            "docs_above_95pct_cap": sum(1 for r in rows if r["tokens"] >= 0.95 * cap_for_hr),
            "near_cap_docs": [
                {"doc": r["doc"], "tokens": r["tokens"], "elapsed_s": r["elapsed_s"]}
                for r in near_cap[:15]
            ],
            "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 2),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT}")

    # Printable summary
    print("\n" + "=" * 78)
    print("TOKEN-CAP AUDIT - total tokens per doc, by published model")
    print("=" * 78)
    print(f"{'model':<14} {'cap':>8} {'p50':>7} {'p90':>7} {'p95':>7} {'max':>7} "
          f"{'>=75%':>7} {'>=90%':>7} {'cost$':>9}")
    for m in ("gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"):
        r = out["per_model"].get(m)
        if not r:
            continue
        cap = r["configured_output_cap"] or "-"
        print(
            f"{m:<14} {str(cap):>8} {r['total_tokens_p50']:>7} {r['total_tokens_p90']:>7} "
            f"{r['total_tokens_p95']:>7} {r['total_tokens_max']:>7} "
            f"{r['docs_above_75pct_cap']:>7} {r['docs_above_90pct_cap']:>7} "
            f"{r['total_cost_usd']:>9.2f}"
        )

    print()
    print("Interpretation:")
    print("  Total tokens = input + output. The cap is on OUTPUT tokens only,")
    print("  so ≥75% of cap as TOTAL tokens is a conservative upper bound on")
    print("  the docs that may have been truncated. The actual at-risk count is")
    print("  smaller. Under the single-cap regime, any non-zero count at ≥90%")
    print("  of 32K warrants a closer look.")


if __name__ == "__main__":
    main()
