#!/usr/bin/env python3
"""Deterministic hallucination analysis for Nightmare Extraction Test.

Ground truth JSON carries the authoritative universe of values for each
document (header fields, raw_ground_truth.fields, locations, claims,
drivers, etc.). A hallucination here is an extracted value that doesn't
land anywhere in that universe even after normalization.

No LLMs. No source-document parsing. Just JSON walking + string/number
matching.

Universe construction reads packet GT + every JSON in the packet's
generator-side ground_truth/ directory (document_truth_*.json,
field_truth_*.json, manifest_*.json, packet_truth.json). The legacy
PDF/xlsx/csv ingest path was dropped 2026-05-08 (plan §4-O): the four-
bucket generator regen ships richer JSON artifacts that already cover
every value the parsed-doc path produced, and dropping the parser
removes poppler / easyocr / pdf2image / numpy / scipy from the public-
release dependency footprint.

Usage:
    python scripts/hallucination_analysis.py \\
        --ground-truth ground_truth/ \\
        --results results/ \\
        --output results/hallucination_report.json
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, NamedTuple


# ── value normalization ────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def norm_string(s: Any) -> str:
    if s is None:
        return ""
    out = str(s).strip().lower()
    out = _PUNCT_RE.sub(" ", out)
    out = _WS_RE.sub(" ", out).strip()
    return out


def as_float(v: Any) -> float | None:
    if v is None or v is True or v is False:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(",", "").replace("$", "").replace(" ", "")
    s = s.rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def looks_meaningful_string(s: str) -> bool:
    """Filter out things that aren't worth flagging (boilerplate, nulls)."""
    if not s:
        return False
    if s in {"null", "none", "n a", "not applicable", "na", "unknown",
             "tbd", "pending", "open", "closed", "yes", "no", "true",
             "false", "active", "inactive"}:
        return False
    # One-char or single-word generic types aren't worth flagging
    if len(s) <= 2:
        return False
    return True


# ── Universe builder ──────────────────────────────────────────────────


# Plumbing keys whose values are filesystem paths, layout metadata, or
# template-only fields that should NOT enter the universe. Without this
# skip, maintainer paths, prompt-file names, and PDF layout coordinates
# (x/y/bbox/page) land as universe entries — a model fabricating any
# matching value gets credit. 2026-05-14 audit: 34–64% of the
# pre-skip universe number-set was layout coords; 14/25,969 model-emitted
# numerics across 5 cohorts × 148 docs were coordinate-rescued
# (0.054%) — material to the methodology claim, immaterial to published
# rates (well under rounding).
_UNIVERSE_SKIP_KEYS = {
    # paths / template metadata
    "document_path", "source_file", "prompt_file", "schema_file",
    "ocr_path", "render_path",
    # layout scalars
    "x", "y", "width", "height", "font_size", "baseline",
    "page_no", "page_number", "csv_row", "csv_col",
    # layout containers (whole subtree skipped)
    "bbox", "bboxes", "locations", "positions", "rects",
    "pages_affected",
}


def collect_universe(gt_doc: dict) -> tuple[set, list]:
    """Walk ground truth for a single doc; return (string_set, number_list)."""
    strings: set[str] = set()
    numbers: list[float] = []

    def walk(obj: Any):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k in _UNIVERSE_SKIP_KEYS:
                    continue
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            numbers.append(float(obj))
            # Also add string form so digit-for-digit matches work both ways
            strings.add(norm_string(obj))
        elif isinstance(obj, str):
            ns = norm_string(obj)
            if ns:
                strings.add(ns)
            # If the string is a number, capture it as a number too
            f = as_float(obj)
            if f is not None:
                numbers.append(f)

    walk(gt_doc)
    return strings, numbers


# ── Rich source-document universe ─────────────────────────────────────
#
# The benchmark GT JSON only models a subset of the fields that appear on
# the rendered document. Anything the model extracts that IS on the page
# but NOT in the GT would get flagged as a hallucination. To avoid these
# false positives, we also ingest every generator *_truth*.json next to
# the packet (document_truth_*.json, field_truth_*.json, manifest_*.json,
# packet_truth.json) — these carry every value the rendered page derives
# from. Live PDF/xlsx/csv parsing was retired 2026-05-08 (plan §4-O); see
# build_packet_universe docstring + memory/project_universe_cross_check.md.


def _is_content_key(k: str) -> bool:
    """Heuristic: ingest dict keys that look like human-readable content
    labels ("Decking", "Roof Age", "SIC Code") and skip plumbing keys
    ("fields", "value", "doc_type", "locations", "insured_name").

    A content label has an uppercase letter or a space; plumbing keys
    are all lowercase snake_case.
    """
    if not isinstance(k, str) or len(k) < 3:
        return False
    return any(c.isupper() for c in k) or " " in k


def _ingest_value(obj: Any, strings: set[str], numbers: list[float]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k in _UNIVERSE_SKIP_KEYS:
                continue
            if _is_content_key(k):
                ns = norm_string(k)
                if ns:
                    strings.add(ns)
            _ingest_value(v, strings, numbers)
    elif isinstance(obj, list):
        for v in obj:
            _ingest_value(v, strings, numbers)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        numbers.append(float(obj))
        strings.add(norm_string(obj))
    elif isinstance(obj, str):
        ns = norm_string(obj)
        if ns:
            strings.add(ns)
        f = as_float(obj)
        if f is not None:
            numbers.append(f)


def _derive_packet_dir(gt_data: dict, gt_file: Path | None = None) -> Path | None:
    """Given a loaded packet GT dict, find the generator packet dir.

    Tries layouts in order:
      (a) document_path = .../packets/<difficulty>/doc_<seed>/documents/
          <file>.pdf  →  packet dir = .../packets/<difficulty>/
          doc_<seed>. This is the canonical v1 layout; document_path
          in the shipped GT is relative to the GT file's parent, so a
          fresh clone resolves correctly without any anchor walk.
      (b) packet_id + difficulty walk-up. Used when document_path is
          missing or unresolvable (e.g. a user wired a GT file into a
          custom workspace). Looks for `packets/<difficulty>/doc_<seed>`
          ascending from the GT file's parent so it works whether the
          user CD'd into `public/` or one level above.
      (c) Self-contained release layout: tier-2 artifacts live directly
          under `<gt_file_parent>/ground_truth/`. Used by the curated
          slices in `examples/*/source/` where there's no `packets/`
          tree at all.
    """
    docs = gt_data.get("documents", {}) or {}
    # (a) original generator layout via document_path
    for doc_gt in docs.values():
        p = doc_gt.get("document_path")
        if not p:
            continue
        pp = Path(p)
        if not pp.is_absolute() and gt_file is not None:
            pp = gt_file.resolve().parent / pp
        # .../doc_70001/documents/acord_140_70001.pdf -> .../doc_70001
        if pp.parent.name == "documents":
            cand = pp.parent.parent
            if cand.is_dir():
                return cand

    # (b) packet_id + difficulty walk-up
    packet_id = gt_data.get("packet_id")
    difficulty = gt_data.get("difficulty")
    if packet_id and difficulty and gt_file is not None:
        seed = packet_id.rsplit("_", 1)[-1]
        if seed.isdigit():
            rel = Path("packets") / difficulty / f"doc_{seed}"
            anchor = gt_file.resolve().parent
            for _ in range(6):  # bounded ascent
                cand = anchor / rel
                if cand.is_dir():
                    return cand
                if anchor == anchor.parent:
                    break
                anchor = anchor.parent

    # (c) self-contained release layout: tier-2 artifacts adjacent to gt_file
    if gt_file is not None:
        cand = gt_file.resolve().parent
        if (cand / "ground_truth").is_dir():
            return cand

    return None


def _compact(s: str) -> str:
    """Strip all non-alphanumerics for identifier-style comparisons."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


class PacketUniverse(NamedTuple):
    """Precomputed universe artifacts for one packet.

    Every form string_in_universe needs (raw strings, compact form, token
    set) is computed once when the universe is built, so matching is a
    pure function with no module-level cache. The prior design memoized
    compact/token sets keyed by id(universe), correct only while caches
    were manually cleared between packets AND GC didn't recycle a freed
    universe's id — a 2026-05-11 audit caught that invariant being broken
    (token cache was never cleared) and producing 0-3.3pp string-rate
    noise across runs. Precompute-at-build-time removes the discipline
    requirement entirely.
    """
    strings: set[str]
    numbers: list[float]
    compact: set[str]
    tokens: set[str]


def make_universe(strings: set[str], numbers: list[float]) -> PacketUniverse:
    """Bundle raw universe + the two derived forms string_in_universe needs."""
    compact = {_compact(u) for u in strings}
    compact.discard("")
    tokens: set[str] = set()
    for entry in strings:
        for t in entry.split():
            if len(t) >= 3:
                tokens.add(t)
    return PacketUniverse(strings=strings, numbers=numbers,
                          compact=compact, tokens=tokens)


def build_packet_universe(gt_data: dict, gt_file: Path | None = None) -> PacketUniverse:
    """Packet universe: packet GT + generator-side rendered_universe artifacts.

    Section (3) of the v1 universe build (live PDF/xlsx/csv parsing via
    poppler + easyocr + openpyxl) was dropped 2026-05-08 (plan §4-O). The
    generator's per-document JSON artifacts (document_truth_*.json,
    field_truth_*.json, manifest_*.json, packet_truth.json under
    <packet>/doc_<id>/ground_truth/) carry every value the parsed-doc path
    produced. Cross-check on the v1 corpus showed with-docs and no-docs
    universes agreed on 712/740 doc verdicts, and the 24 disagreements
    were exactly the matcher false-negatives the §4-O matcher tightening
    fixes — so the two paths converge after that fix lands. Documented
    in memory/project_universe_cross_check.md.
    """
    strings: set[str] = set()
    numbers: list[float] = []

    # (1) Packet GT for every doc in the packet
    for doc_gt in gt_data.get("documents", {}).values():
        s, n = collect_universe(doc_gt)
        strings |= s
        numbers.extend(n)

    # (2) Generator source-of-truth artifacts. sorted() for determinism even
    # though ingest is into order-independent collections - costs nothing.
    vdir = _derive_packet_dir(gt_data, gt_file)
    if vdir is not None and vdir.is_dir():
        gdir = vdir / "ground_truth"
        if gdir.is_dir():
            for jf in sorted(gdir.glob("*.json")):
                try:
                    _ingest_value(json.loads(jf.read_text()), strings, numbers)
                except Exception:
                    continue

    return make_universe(strings, numbers)


def string_in_universe(val: str, universe) -> bool:
    """Match the normalized value against the universe.

    `universe` is either a PacketUniverse (preferred — has compact/tokens
    precomputed) or a bare set[str] (back-compat for callers like
    alias_audit.py that pass `pu.strings` directly). In the bare-set case
    we wrap on the fly via make_universe(); cheap enough at call sites
    that don't hit it in a hot loop.

    Strategy (three tiers, cheapest first):
      1. Exact normalized match.
      2. Compact-form exact match (so "CL-2023-12345" matches
         "CL202312345" after punctuation/whitespace collapse). Requires
         ≥4 compact chars to avoid rubber-stamping trivially short values.
      3. All-tokens-match composition: for values with ≥2 tokens, accept
         only when EVERY token is in universe.strings (or is purely
         numeric). Catches legitimate concatenations like "LOC-001:
         Preston Center Tower - 8117 Preston Road, Dallas, TX 75225"
         where every component is in the source but the combined form
         isn't. A single non-source token is enough to fail.

    The earlier 80%-of-tokens fuzzy tier was dropped 2026-05-12 after an
    audit showed it admitting real hallucinations like "9900 state road
    philadelphia pa 19136" against a rendered "8717 ..." — same failure
    mode as the dropped numeric tolerance, one-sided against the
    over-emitting (typically OpenAI) cohorts. The 3-char floor that
    accompanied it was an OCR-pipeline workaround; OCR ingest was retired
    2026-05-08 so the floor is no longer needed.

    Substring matching was removed in the 2026-04-17 audit: it was
    rubber-stamping fabricated values as "not hallucinated" whenever they
    happened to share a substring with any long universe string, and
    systematically deflated published hallucination rates.
    """
    if not val:
        return False
    if not isinstance(universe, PacketUniverse):
        universe = make_universe(universe, [])
    if val in universe.strings:
        return True
    val_c = _compact(val)
    if len(val_c) >= 4 and val_c in universe.compact:
        return True
    # Composed-string acceptance. `val` is already norm_string'd (punctuation
    # collapsed to spaces), so split() is the correct tokenizer here. Accept
    # only when EVERY token appears in the universe (as a whole string, as a
    # compact form of a longer string, or as a split-token of one). The prior
    # 80%-of-tokens fuzzy tier was admitting real hallucinations like "9900
    # state road philadelphia pa 19136" against rendered "8717 ..." — same
    # failure mode as the dropped numeric tolerance. The earlier 3-char floor
    # on alpha tokens was a workaround for OCR-junk universe entries; OCR
    # ingest was retired 2026-05-08 so the floor is no longer needed and was
    # over-blocking legitimate state codes (PA/TX/OH) and ACORD form prefixes
    # (CA/CP/CG/WC/IL).
    toks_all = val.split()
    if len(toks_all) < 2:
        return False

    def _tok_ok(t: str) -> bool:
        if t in universe.strings:
            return True
        if len(t) >= 4 and t in universe.compact:
            return True
        return t in universe.tokens

    return all(_tok_ok(t) for t in toks_all)


def number_in_universe(val: float, numbers: list[float]) -> bool:
    """Exact match after as_float() normalization.

    The prior 1% relative tolerance was hiding real model errors: extracted
    $24.3M against rendered $24.5M, cents-truncated $153,631 against
    $153,631.51, year off-by-one (2009 against 2010). Villify renders exact
    numeric values and GT mirrors them, so any post-normalization mismatch
    is a model error. as_float() handles the legitimate normalization cases
    ("$1,500,000" → 1500000.0, "1500000" → 1500000.0).
    """
    return any(val == n for n in numbers)


# ── Extraction walker ─────────────────────────────────────────────────


# Leaves matched by name - these are schema enums or template metadata
# that ground truth doesn't model, so absence from the universe doesn't
# imply hallucination.
SKIP_LEAF_NAMES = {
    # Schema enums
    "coverage", "coverage_type", "coverage_code", "category", "priority",
    "status", "document_type", "statement_type", "period_type",
    "risk_level", "insurability", "entity_type", "construction",
    "occupancy", "mvr_status", "sex", "license_state",
    "risk_grade", "grading_scale", "fiscal_year", "period_end_date",
    "audited", "preparer", "report_type",
    # ACORD form metadata
    "form_edition", "form_title", "form_type", "form_code", "form_number",
    # Producer info - not tracked in GT
    "producer_code", "producer_name", "producer_address", "producer_id",
    # Dates that can be extracted but aren't in GT for many doc types
    "date", "report_date", "issue_date", "inspection_date",
    # Text/summary sections
    "summary", "description", "notes", "remarks",
    "executive_summary", "operations_description", "safety_programs",
    "claims_narrative", "nature_of_business", "loss_history_summary",
    # Enum-like
    "type", "kind", "role", "title",
}

# Path fragments - if the leaf's path contains any of these, skip it
SKIP_PATH_FRAGMENTS = {
    "form_info", "producer",
    "extracted_text_sections", "overall_assessment",
    "recommendations",  # recommendation text is narrative, not structured value
    "risk_highlights",  # free-text positive/concern lists
    # narrative.schema.json coverage-summary block. `current_limit` /
    # `requested_limit` are typed as strings here because the model is
    # paraphrasing/aggregating across SOV rows or prior-year tabs, not
    # quoting a single literal cell. Computed aggregates (e.g. Prior Year
    # SOV TIV column sum) get false-flagged otherwise.
    "coverages_discussed",
    # Aggregates - models compute these from line items, GT doesn't
    # necessarily store them. Scored separately by check_arithmetic.
    "grand_totals", "subtotals_by_coverage", "totals",
    "premium_summary", "premium_info",
    "ratios",  # financial ratios are model-computed
    # ACORD checkboxes: schema is {field: free-string, value: enum Yes/No}.
    # `field` is the model's paraphrase of the form's question label, not a
    # literal token from the page; `value` is already covered by the
    # checked/unchecked filler set. Treating `checkboxes[].field` as a leaf
    # to verify against the source universe penalizes models for inventing
    # an identifier where the schema asked them to.
    "checkboxes",
}


def _is_aggregate_leaf(leaf: str) -> bool:
    """Paths whose terminal name is an aggregate (model-computed sum)."""
    return leaf.startswith("total_") or leaf.startswith("subtotal_") or leaf in {
        "total", "subtotal", "grand_total", "total_insured_value",
        "total_current_assets", "total_fixed_assets", "total_assets",
        "total_current_liabilities", "total_long_term", "total_liabilities",
        "total_equity", "total_operating_expenses", "total_premium",
        "total_due", "taxes_fees",
    }

# Filler / refusal strings the model uses when it can't extract
FILLER_STRINGS = {
    "multiple", "various", "see below", "see coverages",
    "see above", "see schedule", "see attached", "see page",
    "n a", "na", "tbd", "pending", "unknown", "not applicable",
    "not available", "none", "null",
    # ACORD checkbox schema values: every model emits "checked"/"unchecked"
    # as the literal value for boolean checkbox fields. The rendered page
    # carries a glyph, not the English word, so these were being flagged
    # as fabrications on every ACORD across every model.
    "checked", "unchecked",
}


def walk_extraction(obj: Any, path: tuple = ()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_extraction(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_extraction(v, path + (f"[{i}]",))
    else:
        yield path, obj


# ── Per-doc analysis ──────────────────────────────────────────────────


def analyze_doc(extraction: dict, gt_doc: dict, packet_universe: PacketUniverse = None) -> dict:
    """Return a hallucination report for one extraction.

    packet_universe: optional PacketUniverse pre-computed from the entire
    packet. Shared customer info (insured, producer, preparer, carrier)
    repeats across docs, so matching against the packet-wide universe
    avoids false positives where the model extracts a real customer-level
    value that happens not to be modeled in that specific doc's ground
    truth.
    """
    if packet_universe is None:
        s, n = collect_universe(gt_doc)
        packet_universe = make_universe(s, n)

    # Walk extraction, score each leaf
    checked_strings = 0
    hallucinated_strings = 0
    checked_numbers = 0
    hallucinated_numbers = 0
    examples = []  # top offenders

    for path, value in walk_extraction(extraction):
        if value is None or value is True or value is False:
            continue
        leaf = path[-1] if path else ""
        # Normalize the leaf name for matching (drop list indices)
        leaf_bare = leaf if not (isinstance(leaf, str) and leaf.startswith("[")) else (
            path[-2] if len(path) >= 2 else ""
        )
        path_str = ".".join(str(p) for p in path)
        path_parts = {p for p in path if isinstance(p, str) and not p.startswith("[")}

        # Skip template / schema-enum leaves
        if leaf_bare in SKIP_LEAF_NAMES:
            continue
        if path_parts & SKIP_PATH_FRAGMENTS:
            continue
        if _is_aggregate_leaf(leaf_bare):
            continue

        # Numeric-first: numbers coerce cleanly
        num_val = as_float(value)
        is_numeric_field = isinstance(value, (int, float)) and not isinstance(value, bool)
        if num_val is not None and (is_numeric_field or (isinstance(value, str) and _is_mostly_numeric(value))):
            checked_numbers += 1
            if not number_in_universe(num_val, packet_universe.numbers):
                hallucinated_numbers += 1
                examples.append({
                    "kind": "number",
                    "path": path_str,
                    "value": value,
                })
            continue

        # String leaves
        if isinstance(value, str):
            ns = norm_string(value)
            if not looks_meaningful_string(ns):
                continue
            if ns in FILLER_STRINGS:
                continue
            # Skip any "see X" type filler
            if ns.startswith("see "):
                continue
            checked_strings += 1
            if not string_in_universe(ns, packet_universe):
                hallucinated_strings += 1
                # Flag high-value identifiers as high-severity
                severity = "high" if leaf_bare in {
                    "claim_number", "policy_number", "claimant",
                    "license_number", "naics_code", "sic_code",
                } else "normal"
                examples.append({
                    "kind": "string",
                    "path": path_str,
                    "value": value[:120],
                    "severity": severity,
                })

    # Overcount check: extracted list longer than GT list for major lists
    overcount = {}
    for list_key in ["locations", "claims", "drivers", "locations_inspected",
                     "recommendations", "coverages", "forms_attached",
                     "endorsements"]:
        gt_list = gt_doc.get(list_key)
        ext_list = extraction.get(list_key)
        if not isinstance(gt_list, list) or not isinstance(ext_list, list):
            continue
        if len(ext_list) > len(gt_list):
            overcount[list_key] = {
                "gt_count": len(gt_list),
                "ext_count": len(ext_list),
                "excess": len(ext_list) - len(gt_list),
            }

    # Internal arithmetic consistency
    arith_errors = check_arithmetic(extraction)

    return {
        "strings_checked": checked_strings,
        "strings_hallucinated": hallucinated_strings,
        "numbers_checked": checked_numbers,
        "numbers_hallucinated": hallucinated_numbers,
        # Rate is None (not 0.0) when nothing was evaluated, so a doc that
        # the scorer couldn't score on isn't silently reported as "zero
        # hallucinations." Downstream consumers must treat None as "no data"
        # and either filter or surface it explicitly.
        "string_hallucination_rate": (
            hallucinated_strings / checked_strings if checked_strings else None
        ),
        "number_hallucination_rate": (
            hallucinated_numbers / checked_numbers if checked_numbers else None
        ),
        "overcount_lists": overcount,
        "arithmetic_errors": arith_errors,
        "examples": examples,
    }


def _is_mostly_numeric(s: str) -> bool:
    """True when the string is really a formatted number, not prose."""
    s = s.strip()
    return bool(re.fullmatch(r"[\$\s]*-?[\d,]+(\.\d+)?\s*%?", s))


def check_arithmetic(extraction: dict) -> list[dict]:
    """Cheap internal consistency checks."""
    errors = []

    # SOV: compare the extraction's own reported TIV total against the sum
    # of its extracted per-location values. This is an internal-consistency
    # check - both sides come from the extraction, not ground truth.
    locs = extraction.get("locations")
    totals = extraction.get("totals", {}) or {}
    if isinstance(locs, list) and locs:
        reported_tiv = as_float(totals.get("tiv"))
        computed = 0.0
        ok = True
        for loc in locs:
            bv = as_float(loc.get("building_value") if isinstance(loc, dict) else None)
            cv = as_float(loc.get("contents_value") if isinstance(loc, dict) else None)
            bi = as_float(loc.get("bi_value") if isinstance(loc, dict) else None)
            tiv_loc = as_float(loc.get("tiv") if isinstance(loc, dict) else None)
            if tiv_loc is not None:
                computed += tiv_loc
            else:
                parts = [x for x in (bv, cv, bi) if x is not None]
                if parts:
                    computed += sum(parts)
                else:
                    ok = False
                    break
        if ok and reported_tiv is not None and reported_tiv > 0 and computed > 0:
            # Cents-level exact match. Doc-rendered numbers are exact and
            # the model should reproduce both per-loc and total faithfully;
            # rounding to cents absorbs float-summation noise without
            # admitting real model arithmetic errors.
            if round(computed, 2) != round(reported_tiv, 2):
                errors.append({
                    "kind": "tiv_sum_mismatch",
                    "reported": reported_tiv,
                    "computed": computed,
                })

    # Loss run: sum of claim incurred vs grand_totals.incurred
    claims = extraction.get("claims")
    gtots = extraction.get("grand_totals", {}) or {}
    if isinstance(claims, list) and claims:
        reported = as_float(gtots.get("incurred"))
        computed = 0.0
        ok = True
        for c in claims:
            if not isinstance(c, dict):
                continue
            inc = as_float(c.get("incurred"))
            if inc is None:
                p = as_float(c.get("paid"))
                r = as_float(c.get("reserved"))
                if p is not None and r is not None:
                    computed += p + r
                else:
                    ok = False
                    break
            else:
                computed += inc
        if ok and reported is not None and reported > 0 and computed > 0:
            if round(computed, 2) != round(reported, 2):
                errors.append({
                    "kind": "incurred_sum_mismatch",
                    "reported": reported,
                    "computed": computed,
                })

    # Financial statement: at any dict containing a `total_*` numeric, the
    # same-level non-total siblings should sum to that total. Mirrors the SOV
    # tiv_sum_mismatch check but generalized for balance-sheet/income-statement
    # shapes (e.g. operating_expenses.{depreciation, other_operating,
    # total_operating_expenses}). Only fires when every sibling is either a
    # direct numeric or a sibling dict that itself declares a total_* — that
    # way an opaque/partial sub-dict bails the check instead of producing a
    # spurious mismatch. Without this, `_is_aggregate_leaf` hides
    # `total_revenue` / `total_assets` / etc. from the hallucination universe
    # check and nothing else validates them.
    if "income_statement" in extraction or "balance_sheet" in extraction:
        _walk_financial_totals(extraction, "", errors)

    return errors


def _is_total_key(k: Any) -> bool:
    return isinstance(k, str) and (k.startswith("total_") or k.startswith("subtotal_") or k in {"total", "subtotal", "grand_total"})


def _walk_financial_totals(obj: Any, path: str, errors: list) -> None:
    if isinstance(obj, dict):
        for tk, tv_raw in obj.items():
            if not _is_total_key(tk):
                continue
            tv = as_float(tv_raw)
            if tv is None or tv == 0:
                continue
            parts: list[tuple[str, float]] | None = []
            for k, v in obj.items():
                if k == tk or _is_total_key(k):
                    continue
                if isinstance(v, bool):
                    continue
                nv = as_float(v)
                if nv is not None and isinstance(v, (int, float)):
                    parts.append((str(k), nv))
                elif isinstance(v, dict):
                    child_total: float | None = None
                    for ck, cv in v.items():
                        if _is_total_key(ck):
                            ct = as_float(cv)
                            if ct is not None:
                                child_total = ct
                                break
                    if child_total is None:
                        parts = None
                        break
                    parts.append((str(k), child_total))
                else:
                    parts = None
                    break
            if parts and len(parts) >= 1:
                computed = sum(p[1] for p in parts)
                if round(computed, 2) != round(tv, 2):
                    errors.append({
                        "kind": "financial_total_mismatch",
                        "location": f"{path}.{tk}" if path else tk,
                        "reported": tv,
                        "computed": computed,
                        "components": {p[0]: p[1] for p in parts},
                    })
        for k, v in obj.items():
            _walk_financial_totals(v, f"{path}.{k}" if path else str(k), errors)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_financial_totals(v, f"{path}[{i}]", errors)


# ── Aggregation ───────────────────────────────────────────────────────


def run_model(model_dir: Path, gt_dir: Path) -> dict:
    model_report = {
        "model": model_dir.name,
        "docs": {},
        "aggregate": {},
    }

    # category bucketing
    buckets = defaultdict(lambda: {
        "docs": 0,
        "strings_checked": 0, "strings_hallucinated": 0,
        "numbers_checked": 0, "numbers_hallucinated": 0,
        "overcount_docs": 0, "overcount_total_excess": 0,
        "arith_error_docs": 0,
        "high_severity_examples": [],
    })
    difficulty = defaultdict(lambda: {
        "docs": 0,
        "strings_checked": 0, "strings_hallucinated": 0,
        "numbers_checked": 0, "numbers_hallucinated": 0,
    })
    # Track missing/errored extractions at the model level so downstream
    # consumers can see the denominator without guessing. Silently dropping
    # these was a v1 survivor-bias pattern.
    missing_docs = 0
    errored_docs = 0

    for gt_file in sorted(gt_dir.glob("*.json")):
        if gt_file.name.endswith("_summary.json"):
            continue
        gt_data = json.loads(gt_file.read_text())
        packet_id = gt_data.get("packet_id", gt_file.stem)
        diff = gt_data.get("difficulty", "unknown")

        # Build packet-wide universe: packet GT + generator source-of-truth
        # + rendered document content. Shared customer info and fields the
        # packet GT schema doesn't model (agency_customer_id, distances,
        # fire district, etc.) would otherwise register as hallucinations.
        packet_universe = build_packet_universe(gt_data, gt_file)

        for doc_key, doc_gt in gt_data.get("documents", {}).items():
            ext_path = model_dir / f"extraction_{packet_id}_{doc_key}.json"
            if not ext_path.exists():
                missing_docs += 1
                continue
            try:
                ext = json.loads(ext_path.read_text())
            except Exception:
                errored_docs += 1
                continue
            if isinstance(ext, dict) and "error" in ext and set(ext.keys()) <= {
                "error", "packet_id", "doc_type"
            }:
                errored_docs += 1
                continue  # stub

            rep = analyze_doc(ext, doc_gt, packet_universe=packet_universe)
            model_report["docs"][f"{packet_id}/{doc_key}"] = rep

            cat = doc_gt.get("category", "other")
            b = buckets[cat]
            b["docs"] += 1
            b["strings_checked"] += rep["strings_checked"]
            b["strings_hallucinated"] += rep["strings_hallucinated"]
            b["numbers_checked"] += rep["numbers_checked"]
            b["numbers_hallucinated"] += rep["numbers_hallucinated"]
            if rep["overcount_lists"]:
                b["overcount_docs"] += 1
                b["overcount_total_excess"] += sum(
                    v["excess"] for v in rep["overcount_lists"].values()
                )
            if rep["arithmetic_errors"]:
                b["arith_error_docs"] += 1
            for ex in rep["examples"]:
                if ex.get("severity") == "high":
                    b["high_severity_examples"].append({
                        "doc": f"{packet_id}/{doc_key}",
                        **ex,
                    })

            d = difficulty[diff]
            d["docs"] += 1
            d["strings_checked"] += rep["strings_checked"]
            d["strings_hallucinated"] += rep["strings_hallucinated"]
            d["numbers_checked"] += rep["numbers_checked"]
            d["numbers_hallucinated"] += rep["numbers_hallucinated"]

    # Finalize aggregates. Rates are None when nothing was checked, so the
    # output JSON distinguishes "genuine 0% hallucination" from "scorer
    # couldn't evaluate this bucket." Downstream must treat None explicitly.
    agg_cats = {}
    for cat, b in buckets.items():
        agg_cats[cat] = {
            **b,
            "string_hallucination_rate": (
                b["strings_hallucinated"] / b["strings_checked"]
                if b["strings_checked"] else None
            ),
            "number_hallucination_rate": (
                b["numbers_hallucinated"] / b["numbers_checked"]
                if b["numbers_checked"] else None
            ),
            # Keep only 5 examples per category in the summary to avoid giant output
            "high_severity_examples": b["high_severity_examples"][:5],
        }

    agg_diff = {}
    for diff_key, d in difficulty.items():
        agg_diff[diff_key] = {
            **d,
            "string_hallucination_rate": (
                d["strings_hallucinated"] / d["strings_checked"]
                if d["strings_checked"] else None
            ),
            "number_hallucination_rate": (
                d["numbers_hallucinated"] / d["numbers_checked"]
                if d["numbers_checked"] else None
            ),
        }

    all_strings_checked = sum(b["strings_checked"] for b in buckets.values())
    all_strings_hall = sum(b["strings_hallucinated"] for b in buckets.values())
    all_nums_checked = sum(b["numbers_checked"] for b in buckets.values())
    all_nums_hall = sum(b["numbers_hallucinated"] for b in buckets.values())

    model_report["aggregate"] = {
        "overall": {
            "docs": sum(b["docs"] for b in buckets.values()),
            "docs_missing": missing_docs,
            "docs_errored": errored_docs,
            "strings_checked": all_strings_checked,
            "strings_hallucinated": all_strings_hall,
            "string_hallucination_rate": (
                all_strings_hall / all_strings_checked if all_strings_checked else None
            ),
            "numbers_checked": all_nums_checked,
            "numbers_hallucinated": all_nums_hall,
            "number_hallucination_rate": (
                all_nums_hall / all_nums_checked if all_nums_checked else None
            ),
            "overcount_docs": sum(b["overcount_docs"] for b in buckets.values()),
            "arith_error_docs": sum(b["arith_error_docs"] for b in buckets.values()),
        },
        "by_category": agg_cats,
        "by_difficulty": agg_diff,
    }

    return model_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ground-truth", type=Path, default=Path("ground_truth"))
    ap.add_argument("--results", type=Path, default=Path("results"))
    ap.add_argument("--output", type=Path, default=Path("results/hallucination_report.json"))
    # Default is the five frontier models being published in the benchmark.
    # A warning is printed at run time listing which dirs will be scored;
    # confirm before shipping any published number.
    ap.add_argument("--models", nargs="*", default=["gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"])
    args = ap.parse_args()

    print("=" * 80)
    print("MODELS BEING SCORED - verify before publishing any number:")
    for m in args.models:
        mdir = args.results / m
        status = "OK" if mdir.is_dir() else "MISSING"
        print(f"  results/{m}  [{status}]")
    print("=" * 80)

    all_reports = {}
    for model in args.models:
        model_dir = args.results / model
        if not model_dir.is_dir():
            print(f"skipping {model}: no dir")
            continue
        print(f"analyzing {model}...")
        all_reports[model] = run_model(model_dir, args.ground_truth)

    args.output.write_text(json.dumps(all_reports, indent=2))
    print(f"\nReport written: {args.output}")

    # Printable summary
    print("\n" + "=" * 80)
    print("HALLUCINATION SUMMARY")
    print("-" * 80)
    print(f"{'Model':<20} {'Str hall%':>10} {'Num hall%':>10} {'Overcount':>10} {'ArithErr':>10} {'Miss/Err':>10}")

    def _fmt_rate(r: float | None) -> str:
        # Match the float formatter's column width so None rows don't break
        # table alignment.
        return f"{'(no data)':>10}" if r is None else f"{r:>10.1%}"

    for m, rep in all_reports.items():
        o = rep["aggregate"]["overall"]
        print(f"{m:<20} "
              f"{_fmt_rate(o['string_hallucination_rate'])} "
              f"{_fmt_rate(o['number_hallucination_rate'])} "
              f"{o['overcount_docs']:>10} "
              f"{o['arith_error_docs']:>10} "
              f"{o.get('docs_missing', 0) + o.get('docs_errored', 0):>10}")


if __name__ == "__main__":
    main()
