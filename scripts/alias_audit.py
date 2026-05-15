#!/usr/bin/env python3
"""Reclassify flagged "fabrications" by token-level universe coverage.

The published hallucination rates are produced by `hallucination_analysis.py`,
which flags an extracted string when its normalized whole-string form does
not appear in the source-document universe (after compact-form fallback
and composed-string match).

This audit re-walks every extraction, re-flags each previously-flagged
string against the same packet universe, and splits residuals by what
the token-coverage classifier thinks they are:

  - composed_string (≥80% audit tokens in universe): analyzer-leaks - the
    audit thinks these should have matched. Any volume here is a signal
    the analyzer needs another pass.
  - partial_overlap (40 to 80%): ambiguous. Includes real model transcription
    errors ("Karen Weismann" when truth is "Karen Weissman", most tokens
    match but the identifier token is wrong), schema gaps (values the
    generator doesn't model), and OCR limitations on adversarial renders.
    Verified 2026-04-18 via source/generator-GT spot-check: most of these
    are legitimate flags, NOT reclassifiable. Do not treat as launch blocker.
  - format_variance (compact-form match that analyzer missed): should be
    ~0 post-fix since the analyzer now runs compact-form match itself.
  - true_fabrication (<40%): analyzer and audit agree it's a fabrication.

Decision rule (post-2026-04-18):
  Fix the analyzer only if the composed_string FRACTION of flagged
  strings exceeds 5% for any model - that indicates a real analyzer
  leak worth chasing. Partial_overlap is not grounds for further analyzer
  relaxation; doing so would accept real transcription errors.

Numeric flags are checked against the universe with 1% tolerance and a
small-integer floor - much less room for false positives, so this audit
is string-only.

Usage:
    python scripts/alias_audit.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Reuse the analyzer's universe builder so we are auditing against the
# exact same source-of-truth set the published numbers came from.
import sys
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from hallucination_analysis import (  # noqa: E402
    build_packet_universe,
    walk_extraction,
    norm_string,
    as_float,
    string_in_universe,
    looks_meaningful_string,
    SKIP_LEAF_NAMES,
    SKIP_PATH_FRAGMENTS,
    _is_aggregate_leaf,
    _is_mostly_numeric,
    FILLER_STRINGS,
)

REPO = Path.cwd()
GT_DIR = REPO / "ground_truth"
RESULTS_DIR = REPO / "results"
OUT = REPO / "results" / "analysis" / "alias_audit.json"

PUBLISHED_MODELS = ["gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"]


_TOKEN_SPLIT = re.compile(r"[\s,;:|/()\[\]{}\\\"'_\-]+")


def tokenize(value: str) -> list[str]:
    """Split a candidate value into universe-comparable tokens.

    Mirrors the tokenization used when ingesting source PDFs / xlsx /
    csv into the universe. Tokens are stripped of leading/trailing
    punctuation and lowercased.
    """
    raw = _TOKEN_SPLIT.split(str(value))
    out = []
    for t in raw:
        t = t.strip(".,;:$%()[]{}'\"")
        if not t:
            continue
        out.append(t.lower())
    return out


def token_coverage(value: str, universe: set[str]) -> tuple[int, int, list[str]]:
    """How many of value's tokens appear in the universe? Returns
    (matched, total, unmatched_tokens)."""
    toks = tokenize(value)
    if not toks:
        return 0, 0, []
    matched = 0
    unmatched = []
    for t in toks:
        ns = norm_string(t)
        if not ns:
            continue
        # Universe entries were normalized at ingest, so direct membership
        # works for token matches (the universe contains "preston",
        # "8117", etc. as separate strings from _ingest_text).
        if ns in universe or string_in_universe(ns, universe):
            matched += 1
        else:
            unmatched.append(t)
    return matched, len(toks), unmatched


def classify(value: str, universe: set[str]) -> dict:
    """Bucket a previously-flagged value by token coverage.

    Thresholds chosen to match what a reviewer would call "real but
    weirdly composed" vs "made up":
      ≥0.80 token coverage → composed_string
      0.40-0.80           → partial_overlap
      <0.40                → true_fabrication
    Also catches format_variance separately: if the compact-form value
    matches a universe compact form, classify as format_variance.
    """
    matched, total, unmatched = token_coverage(value, universe)
    if total == 0:
        return {"bucket": "non_meaningful", "ratio": None,
                "matched": 0, "total": 0, "unmatched": []}
    ratio = matched / total

    # Format variance: does the compact form (digits-and-letters only)
    # already exist in the universe? string_in_universe checks this with
    # a length-4 floor; here we drop the floor for short identifiers
    # because date-like or currency-like values are common.
    compact = re.sub(r"[^a-z0-9]", "", str(value).lower())
    if compact and len(compact) >= 3:
        for u in universe:
            if compact == re.sub(r"[^a-z0-9]", "", u):
                return {"bucket": "format_variance", "ratio": 1.0,
                        "matched": matched, "total": total, "unmatched": []}

    if ratio >= 0.80:
        bucket = "composed_string"
    elif ratio >= 0.40:
        bucket = "partial_overlap"
    else:
        bucket = "true_fabrication"
    return {"bucket": bucket, "ratio": ratio,
            "matched": matched, "total": total,
            "unmatched": unmatched[:10]}


def audit_doc(extraction: dict, universe) -> dict:
    """For one extraction, re-flag strings exactly as the analyzer does,
    then classify each flagged string."""
    # build_packet_universe returns a PacketUniverse NamedTuple; we only
    # need the raw normalized strings for the token-coverage classifier.
    strings = universe.strings
    buckets = {"composed_string": 0, "format_variance": 0,
               "partial_overlap": 0, "true_fabrication": 0,
               "non_meaningful": 0}
    examples: dict[str, list] = {b: [] for b in buckets}

    flagged_total = 0
    for path, value in walk_extraction(extraction):
        if value is None or value is True or value is False:
            continue
        leaf = path[-1] if path else ""
        leaf_bare = leaf if not (isinstance(leaf, str) and leaf.startswith("[")) else (
            path[-2] if len(path) >= 2 else ""
        )
        path_parts = {p for p in path if isinstance(p, str) and not p.startswith("[")}

        if leaf_bare in SKIP_LEAF_NAMES:
            continue
        if path_parts & SKIP_PATH_FRAGMENTS:
            continue
        if _is_aggregate_leaf(leaf_bare):
            continue

        # Skip numerics - same gate as the analyzer
        num_val = as_float(value)
        is_numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if num_val is not None and (is_numeric or (isinstance(value, str) and _is_mostly_numeric(value))):
            continue

        if not isinstance(value, str):
            continue
        ns = norm_string(value)
        if not looks_meaningful_string(ns):
            continue
        if ns in FILLER_STRINGS:
            continue
        if ns.startswith("see "):
            continue

        # Was this string flagged by the analyzer?
        if string_in_universe(ns, strings):
            continue

        flagged_total += 1
        cls = classify(value, strings)
        buckets[cls["bucket"]] += 1
        if len(examples[cls["bucket"]]) < 5:
            examples[cls["bucket"]].append({
                "path": ".".join(str(p) for p in path),
                "value": str(value)[:160],
                "ratio": cls["ratio"],
                "unmatched_tokens": cls["unmatched"],
            })

    return {"flagged_strings": flagged_total, "buckets": buckets, "examples": examples}


def audit_model(model: str, gt_dir: Path, results_dir: Path) -> dict:
    model_dir = results_dir / model
    if not model_dir.is_dir():
        return {"error": f"missing dir {model_dir}"}

    cumulative = {b: 0 for b in
                  ("composed_string", "format_variance", "partial_overlap",
                   "true_fabrication", "non_meaningful")}
    flagged_total = 0
    per_doc = {}
    sample_examples: dict[str, list] = {b: [] for b in cumulative}

    for gt_file in sorted(gt_dir.glob("*.json")):
        if gt_file.name.endswith("_summary.json"):
            continue
        gt_data = json.loads(gt_file.read_text())
        packet_id = gt_data.get("packet_id", gt_file.stem)
        # Build packet universe once per packet - same as the analyzer
        universe = build_packet_universe(gt_data)

        for doc_key, _doc_gt in gt_data.get("documents", {}).items():
            ext_path = model_dir / f"extraction_{packet_id}_{doc_key}.json"
            if not ext_path.exists():
                continue
            try:
                ext = json.loads(ext_path.read_text())
            except Exception:
                continue
            if isinstance(ext, dict) and "error" in ext and set(ext.keys()) <= {
                "error", "packet_id", "doc_type"
            }:
                continue
            rep = audit_doc(ext, universe)
            per_doc[f"{packet_id}/{doc_key}"] = rep
            flagged_total += rep["flagged_strings"]
            for b, n in rep["buckets"].items():
                cumulative[b] += n
            for b, exs in rep["examples"].items():
                if len(sample_examples[b]) < 8:
                    for ex in exs:
                        if len(sample_examples[b]) >= 8:
                            break
                        sample_examples[b].append({"doc": f"{packet_id}/{doc_key}", **ex})

    # Post-fix decision signal: composed_string fraction only. Partial-
    # overlap is NOT treated as reclassifiable; spot-check against
    # generator GT + source PDFs shows most of that bucket is legitimate
    # transcription error or schema gap.
    composed_fraction = (
        cumulative["composed_string"] / flagged_total if flagged_total else None
    )
    # Legacy field retained for backward compatibility with any downstream
    # consumers; no longer used in the decision rule.
    not_true_fab = sum(cumulative[b] for b in
                       ("composed_string", "format_variance", "partial_overlap"))
    reclassify_fraction = (
        not_true_fab / flagged_total if flagged_total else None
    )

    return {
        "model": model,
        "flagged_strings_total": flagged_total,
        "buckets": cumulative,
        "composed_fraction": composed_fraction,
        "reclassify_fraction": reclassify_fraction,
        "true_fabrication_fraction": (
            cumulative["true_fabrication"] / flagged_total if flagged_total else None
        ),
        "sample_examples": sample_examples,
    }


def main():
    out: dict = {"models": {}}
    for m in PUBLISHED_MODELS:
        print(f"auditing {m}...")
        out["models"][m] = audit_model(m, GT_DIR, RESULTS_DIR)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT}")

    # Printable summary
    print("\n" + "=" * 78)
    print("ALIAS / RECLASSIFICATION AUDIT - flagged strings split by token coverage")
    print("=" * 78)
    print(f"{'model':<14} {'flagged':>8} {'true_fab':>9} {'composed':>9} "
          f"{'format':>8} {'partial':>8} {'composed%':>10}")
    for m, rep in out["models"].items():
        if "error" in rep:
            print(f"{m:<14} ERROR")
            continue
        b = rep["buckets"]
        cf = rep["composed_fraction"]
        print(
            f"{m:<14} {rep['flagged_strings_total']:>8} "
            f"{b['true_fabrication']:>9} "
            f"{b['composed_string']:>9} "
            f"{b['format_variance']:>8} "
            f"{b['partial_overlap']:>8} "
            f"{(cf*100 if cf is not None else 0):>9.1f}%"
        )

    print()
    print("Decision rule (post-2026-04-18): fix the analyzer only if any")
    print("model's composed_string fraction exceeds 5%. Partial_overlap is")
    print("NOT treated as reclassifiable, verified via generator-GT spot-check")
    print("that most of that bucket is real transcription error / schema gap.")
    threshold = 0.05
    triggered = []
    for m, rep in out["models"].items():
        if "error" in rep or rep.get("composed_fraction") is None:
            continue
        if rep["composed_fraction"] >= threshold:
            triggered.append((m, rep["composed_fraction"]))
    if triggered:
        print("  → THRESHOLD MET for:")
        for m, f in triggered:
            print(f"      {m}: composed_string={f*100:.1f}% (≥ {threshold*100:.0f}%)")
        print("  Fix the analyzer's composed-string matcher before publishing.")
    else:
        print(f"  → all models below {threshold*100:.0f}% composed_string threshold.")
        print("  Existing rates stand.")


if __name__ == "__main__":
    main()
