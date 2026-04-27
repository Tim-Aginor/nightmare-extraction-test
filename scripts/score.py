#!/usr/bin/env python3
"""Scoring engine for Nightmare Extraction Test.

Compares model extractions against ground truth and produces:
- Per-document scores by category
- Per-packet aggregate scores
- Cross-model comparison tables

Supports all document categories: SOV, loss runs, ACORD forms, engineering
reports, dec pages, driver schedules, financial statements, narratives.

Usage:
    python scripts/score.py \
        --ground-truth ground_truth/ \
        --extractions results/sonnet/ \
        --output results/sonnet/scores.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any


# ── Normalization Helpers ──────────────────────────────────────────────


def normalize_string(val: Any) -> str:
    """Normalize a string for fuzzy comparison."""
    if val is None:
        return ""
    s = str(val).strip().lower()
    s = re.sub(r'\s+', ' ', s)
    s = s.replace(",", "").replace(".", "").replace(";", "").replace("$", "").replace("%", "")
    return s


def normalize_address(val: Any) -> str:
    """Normalize an address for matching."""
    s = normalize_string(val)
    for long, short in [("street", "st"), ("avenue", "av"), ("boulevard", "blvd"),
                        ("drive", "dr"), ("road", "rd"), ("suite", "ste")]:
        s = s.replace(long, short)
    s = re.sub(r'\bste\s*\d+\b', '', s)
    s = re.sub(r'\bsuite\s*\d+\b', '', s)
    return s.strip()


def to_float(val: Any) -> float | None:
    """Convert value to float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("$", "").replace(",", "").replace(" ", "")
    if not s or s.lower() in ("null", "none", "n/a", "-", "\u2014"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def normalize_date(val: Any) -> str | None:
    """Normalize date to YYYY-MM-DD."""
    if val is None:
        return None
    s = str(val).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    return s


def compare_values(ext_val: Any, gt_val: Any, field_type: str = "string") -> bool:
    """Compare extracted vs ground truth values.

    Auto-promote to numeric when gt_val is a Python int/float: the
    field_type heuristic misses fields like bs_cash, is_net_income,
    annual_revenue, etc. (stored as native floats in raw_ground_truth),
    and the string-normalization path strips '.' which mangles decimals.
    """
    if field_type != "date":
        if isinstance(gt_val, (int, float)) and not isinstance(gt_val, bool):
            field_type = "numeric"
        elif field_type == "string":
            # Auto-promote when both sides parse as numbers AND at least one
            # carries a decimal point. The decimal gate is critical: without
            # it, nominal numeric strings (ZIPs like "07001", years like
            # "2024", policy counts, NAICS codes) would promote to numeric
            # and the 1% tolerance would silently accept off-by-one errors
            # (e.g. "77002" vs "77003" reads as correct). The original bug
            # this fix addressed is GT-stored decimal strings like "125.50",
            # which always contain '.' - so the decimal gate preserves the
            # intended fix while blocking the adversarial regression.
            gt_str = str(gt_val) if gt_val is not None else ""
            ext_str = str(ext_val) if ext_val is not None else ""
            if "." in gt_str or "." in ext_str:
                gt_f_probe = to_float(gt_val)
                ext_f_probe = to_float(ext_val)
                if gt_f_probe is not None and ext_f_probe is not None:
                    field_type = "numeric"

    if field_type == "numeric":
        ext_f = to_float(ext_val)
        gt_f = to_float(gt_val)
        if gt_f is None:
            return ext_f is None
        if ext_f is None:
            return False
        if gt_f == 0:
            return ext_f == 0
        return abs(ext_f - gt_f) / abs(gt_f) <= 0.01  # 1% tolerance

    elif field_type == "date":
        return normalize_date(ext_val) == normalize_date(gt_val)

    else:  # string
        return normalize_string(ext_val) == normalize_string(gt_val)


# ── Field lookup across nested extraction schemas ─────────────────────
#
# Ground truth uses flat field names (insured_name, carrier_name, ...).
# Extractions follow category-specific nested prompt schemas
# (insured.name, policy_info.carrier_name, carrier_info.policy_period_start).
# FIELD_ALIASES maps each GT field name to the paths it could live at.

FIELD_ALIASES = {
    "insured_name": [
        "insured_name", "named_insured", "company_name",
        "header.insured_name", "header.company_name",
        "insured.name", "insured.insured_name", "insured.company_name",
        "applicant.name", "named_insured.name",
    ],
    "insured_address": [
        "insured_address", "insured.address", "insured.address_line_1",
        "insured.street_address", "insured.street",
        "header.insured_address", "address",
    ],
    "insured_city": [
        "insured_city", "insured.city", "header.insured_city", "city",
    ],
    "insured_state": [
        "insured_state", "insured.state", "header.insured_state", "state",
    ],
    "insured_zip": [
        "insured_zip", "insured.zip", "insured.zip_code", "insured.postal_code",
        "header.insured_zip", "zip", "zip_code",
    ],
    "carrier_name": [
        "carrier_name", "insurer_name",
        "header.carrier_name",
        "carrier.name", "carrier_info.carrier_name", "carrier_info.name",
        "policy_info.carrier_name", "policy_info.carrier",
    ],
    "wc_carrier_name": [
        "wc_carrier_name", "wc.carrier_name", "workers_comp.carrier_name",
        "workers_compensation.carrier_name",
    ],
    "policy_number": [
        "policy_number", "header.policy_number",
        "policy_info.policy_number", "carrier_info.policy_number",
    ],
    "policy_period_start": [
        "policy_period_start", "effective_date", "policy_effective_date",
        "header.policy_period_start", "policy_info.effective_date",
        "carrier_info.policy_period_start", "policy_info.policy_effective_date",
    ],
    "policy_period_end": [
        "policy_period_end", "expiration_date", "policy_expiration_date",
        "header.policy_period_end", "policy_info.expiration_date",
        "carrier_info.policy_period_end", "policy_info.policy_expiration_date",
    ],
    "total_premium": [
        "total_premium", "premium_info.total_premium",
        "premium_summary.total_premium", "premium.total",
    ],
}

# Heuristic: if a GT field isn't in the alias table, try flat lookup
# plus lookup under "header" - same as the original behaviour.
_DEFAULT_ALIAS_SUFFIX = ["{name}", "header.{name}"]


def _get_by_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


_GT_PREFIX_EXPANSIONS = {
    "bs_": ["", "balance_sheet_", "assets_", "liabilities_", "equity_"],
    "is_": ["", "income_statement_", "revenue_"],
    "cf_": ["", "cash_flow_"],
    "wc_": ["", "workers_comp_", "workers_compensation_"],
    "gl_": ["", "general_liability_"],
}

_LEAF_SYNONYMS = {
    "revenue": {"net_revenue", "gross_revenue", "total_revenue"},
    "cogs": {"cost_of_goods_sold", "cost_of_sales"},
    "ebit": {"operating_income"},
    "ebt": {"income_before_tax", "pre_tax_income"},
    "tax_provision": {"income_tax", "tax_expense"},
    "ppe_net": {"net_fixed_assets", "property_plant_equipment"},
    "current_lt_debt": {"current_debt", "current_portion_long_term_debt"},
    "equity": {"total_equity"},
    "num_employees_ft": {"employee_count", "full_time_employees", "num_employees"},
    "annual_revenue": {"annual_revenue", "revenue", "net_revenue"},
    "nature_of_business": {"nature_of_business", "business_description"},
    "entity_type": {"entity_type", "organization_type"},
}


def _walk_leaves(obj: Any, path: tuple = ()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_leaves(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_leaves(v, path + (f"[{i}]",))
    else:
        yield path, obj


def _leaf_search(extracted: dict, gt_field: str) -> Any:
    """Fallback: find any leaf key in the extraction matching gt_field.

    Honours common prefix conventions (bs_, is_, cf_) and a small synonym
    table. Returns the first non-empty match.
    """
    candidates = {gt_field}
    for prefix, _ in _GT_PREFIX_EXPANSIONS.items():
        if gt_field.startswith(prefix):
            candidates.add(gt_field[len(prefix):])
    for c in list(candidates):
        candidates |= _LEAF_SYNONYMS.get(c, set())

    for path, val in _walk_leaves(extracted):
        if val in (None, "", [], {}):
            continue
        last = path[-1] if path else ""
        if last in candidates:
            return val
    return None


# Coverage-aware lookup (Bug B fix, 2026-04-17).
#
# Dec pages and some ACORD-derived extractions emit structured coverage
# data as:
#
#     {"coverages": [{"coverage_type": "Building", "limit": 222340000,
#                     "deductible": 50000, ...}, ...],
#      "premium_summary": {"total_premium": 403697, ...},
#      "policy_info": {"policy_number": "CP-LSPH-...", ...}}
#
# But GT emits flat suffix-convention fields like `limit_property_building`,
# `premium_property`, `deductible_property`, `policy_number_property`,
# `form_type_property`. Without the lookup below, none of these nested
# values are reachable and every model loses identical points on dec_pages
# (visible as ~61.2% composite uniform across models).

# GT field-name subpart → extraction coverage_type keyword that should match.
_COVERAGE_SUBPART_KEYWORDS = {
    "building": ["building"],
    "contents": ["contents", "personal property", "business personal"],
    "business_income": ["business income", "bi "],
    "bi": ["business income", "bi "],
    "coinsurance": ["coinsurance"],
    "liability": ["liability"],
    "auto_liability": ["auto liability", "automobile liability"],
    "physical_damage": ["physical damage", "collision", "comprehensive"],
    "umbrella": ["umbrella", "excess"],
}

# GT field coverage slug → extraction coverage_type keyword.
_COVERAGE_SLUG_KEYWORDS = {
    "property": ["property", "building", "contents", "business income"],
    "gl": ["general liability", "gl", "liability"],
    "wc": ["workers comp", "workers' comp", "workers compensation"],
    "auto": ["auto", "automobile"],
    "umbrella": ["umbrella", "excess"],
    "crime": ["crime", "fidelity"],
    "cyber": ["cyber"],
    "epl": ["employment practices", "epl"],
    "d_o": ["directors and officers", "d&o", "d and o"],
}

# Base attribute name in GT → extraction dict key on a coverage entry.
_COVERAGE_BASE_KEYS = {
    "limit": "limit",
    "premium": "premium",
    "deductible": "deductible",
    "form_type": "coverage_code",
    "policy_number": "policy_number",
    "billing_plan": "billing_plan",
}


def _parse_coverage_gt_field(gt_field: str) -> tuple[str, str, str | None] | None:
    """Split a GT field like 'limit_property_building' into (base, slug, sub).

    Returns None if the field doesn't match a coverage pattern. Handles:
      limit_<slug>_<sub>, premium_<slug>, deductible_<slug>,
      policy_number_<slug>, form_type_<slug>, billing_plan_<slug>.
    """
    # Multi-word bases first
    for multi_base in ("policy_number", "form_type", "billing_plan"):
        prefix = multi_base + "_"
        if gt_field.startswith(prefix):
            rest = gt_field[len(prefix):]
            slug, _, sub = rest.partition("_")
            if slug in _COVERAGE_SLUG_KEYWORDS:
                return multi_base, slug, sub or None
            return None

    # Single-word bases: limit / premium / deductible
    for base in ("limit", "premium", "deductible"):
        prefix = base + "_"
        if gt_field.startswith(prefix):
            rest = gt_field[len(prefix):]
            slug, _, sub = rest.partition("_")
            if slug in _COVERAGE_SLUG_KEYWORDS:
                return base, slug, sub or None
            return None
    return None


def _coverage_lookup(extracted: dict, gt_field: str) -> Any:
    """Find coverage-suffixed GT fields in a nested extraction schema."""
    parsed = _parse_coverage_gt_field(gt_field)
    if parsed is None:
        return None
    base, slug, sub = parsed

    # Policy-level fields don't need a coverage iteration.
    if base == "premium" and sub is None:
        for p in ("premium_summary.total_premium", "premium.total",
                  "total_premium", "premium_info.total_premium"):
            v = _get_by_path(extracted, p)
            if v not in (None, "", [], {}):
                return v
    if base == "policy_number":
        for p in ("policy_info.policy_number", "carrier_info.policy_number",
                  "header.policy_number", "policy_number"):
            v = _get_by_path(extracted, p)
            if v not in (None, "", [], {}):
                return v
    if base == "billing_plan":
        for p in ("policy_info.billing_plan", "billing_plan",
                  "header.billing_plan"):
            v = _get_by_path(extracted, p)
            if v not in (None, "", [], {}):
                return v

    # Walk coverages[] (and similarly-shaped nested lists) for per-coverage
    # attributes (limit / premium / deductible / coverage_code).
    ext_key = _COVERAGE_BASE_KEYS.get(base)
    if ext_key is None:
        return None

    candidate_lists: list[list] = []
    for path in ("coverages", "policy_info.coverages",
                 "coverages_requested", "coverage_schedule"):
        v = _get_by_path(extracted, path)
        if isinstance(v, list):
            candidate_lists.append(v)

    # Subpart keyword (e.g. "building") takes priority over slug keyword
    # because property sub-limits are more specific than the whole line.
    if sub:
        sub_kws = [k.lower() for k in _COVERAGE_SUBPART_KEYWORDS.get(sub, [sub.replace("_", " ")])]
    else:
        sub_kws = []
    slug_kws = [k.lower() for k in _COVERAGE_SLUG_KEYWORDS.get(slug, [slug])]

    for covs in candidate_lists:
        for cov in covs:
            if not isinstance(cov, dict):
                continue
            cov_type = str(cov.get("coverage_type", cov.get("type", ""))).lower()
            if sub_kws and not any(kw in cov_type for kw in sub_kws):
                continue
            if not sub_kws and not any(kw in cov_type for kw in slug_kws):
                continue
            v = cov.get(ext_key)
            if v not in (None, "", [], {}):
                return v

    # Deductibles and premiums that are identical across all coverages
    # (common for property packages) can be returned by consensus.
    if base in ("deductible", "premium") and not sub:
        vals = set()
        for covs in candidate_lists:
            for cov in covs:
                if isinstance(cov, dict):
                    v = cov.get(ext_key)
                    if v not in (None, "", [], {}):
                        vals.add(v if not isinstance(v, list) else tuple(v))
        if len(vals) == 1:
            return next(iter(vals))

    return None


def lookup_field(extracted: dict, gt_field: str) -> Any:
    """Find gt_field's value in an extraction that uses a nested schema."""
    paths = FIELD_ALIASES.get(gt_field) or [p.format(name=gt_field) for p in _DEFAULT_ALIAS_SUFFIX]
    for p in paths:
        v = _get_by_path(extracted, p)
        if v not in (None, "", [], {}):
            return v
    # Coverage-aware lookup before the generic leaf search - catches
    # dec_page/ACORD structured coverage fields.
    cov_val = _coverage_lookup(extracted, gt_field)
    if cov_val is not None:
        return cov_val
    return _leaf_search(extracted, gt_field)


def _field_type(gt_field: str) -> str:
    if gt_field.endswith("_start") or gt_field.endswith("_end") or gt_field.endswith("_date"):
        return "date"
    if gt_field in ("total_premium",) or gt_field.endswith("_amount") or gt_field.endswith("_value"):
        return "numeric"
    return "string"


# ── Generic Header Scoring ─────────────────────────────────────────────


def score_header_fields(extracted: dict, ground_truth: dict) -> dict:
    """Score common header fields present in most doc types."""
    gt_header = ground_truth.get("header", {})

    fields_to_check = [
        ("insured_name", "string"),
        ("carrier_name", "string"),
        ("insured_state", "string"),
        ("policy_period_start", "date"),
        ("policy_period_end", "date"),
    ]

    correct = 0
    total = 0

    for field, ftype in fields_to_check:
        gt_val = gt_header.get(field)
        if gt_val is None:
            continue
        total += 1
        ext_val = lookup_field(extracted, field)
        if compare_values(ext_val, gt_val, ftype):
            correct += 1

    return {
        # None (not 1.0) when no header fields existed in GT, so downstream
        # aggregators skip the doc for avg_header_accuracy rather than
        # averaging a phantom 1.0 into the published number. The composite
        # in score_generic is already guarded by header_fields_scored > 0.
        "header_accuracy": (correct / total) if total else None,
        "header_fields_scored": total,
        "header_fields_correct": correct,
    }


# ── SOV Scoring ────────────────────────────────────────────────────────


def match_locations(extracted: list, ground_truth: list) -> list[tuple[dict, dict]]:
    """Match extracted locations to ground truth by address."""
    matches = []
    used_gt = set()

    for ext_loc in extracted:
        ext_addr = normalize_address(str(ext_loc.get("address", "")) + " " + str(ext_loc.get("city", "")))
        best_match, best_score = None, 0

        for i, gt_loc in enumerate(ground_truth):
            if i in used_gt:
                continue
            gt_addr = normalize_address(str(gt_loc.get("address", "")) + " " + str(gt_loc.get("city", "")))
            if not ext_addr or not gt_addr:
                continue

            ext_words = set(ext_addr.split())
            gt_words = set(gt_addr.split())
            overlap = len(ext_words & gt_words) / max(len(ext_words), len(gt_words))

            if overlap > best_score and overlap > 0.4:
                best_score = overlap
                best_match = i

        if best_match is not None:
            matches.append((ext_loc, ground_truth[best_match]))
            used_gt.add(best_match)

    return matches


def score_sov(extracted: dict, ground_truth: dict) -> dict:
    """Score SOV extraction."""
    gt_locations = ground_truth.get("locations", [])
    ext_locations = extracted.get("locations", [])
    gt_totals = ground_truth.get("totals", {})

    # Location coverage
    matches = match_locations(ext_locations, gt_locations)
    location_coverage = len(matches) / len(gt_locations) if gt_locations else 1.0

    # Field accuracy
    numeric_fields = ["building_value", "contents_value", "bi_value", "tiv", "year_built", "square_feet"]
    string_fields = ["construction", "occupancy", "state"]
    correct, total = 0, 0

    for ext_loc, gt_loc in matches:
        for fld in numeric_fields:
            gt_val = gt_loc.get(fld)
            if gt_val is not None:
                total += 1
                if compare_values(ext_loc.get(fld), gt_val, "numeric"):
                    correct += 1
        for fld in string_fields:
            gt_val = gt_loc.get(fld)
            if gt_val is not None:
                total += 1
                if compare_values(ext_loc.get(fld), gt_val, "string"):
                    correct += 1

    field_accuracy = correct / total if total else None

    # TIV accuracy. Distinguish "GT has no TIV total" (drop from composite)
    # from "GT TIV is present and positive" (compare, with 10% catastrophic
    # threshold). Handing out free 1.0 when GT lacked the data was a v1 bug
    # that silently inflated scores.
    gt_tiv_raw = to_float(gt_totals.get("tiv"))
    ext_totals = extracted.get("totals", {})
    ext_tiv_raw = to_float(ext_totals.get("tiv"))
    if gt_tiv_raw is not None and gt_tiv_raw > 0:
        ext_tiv_for_compare = ext_tiv_raw if ext_tiv_raw is not None else 0.0
        tiv_accuracy = max(0, 1.0 - abs(ext_tiv_for_compare - gt_tiv_raw) / gt_tiv_raw)
    else:
        tiv_accuracy = None

    # Catastrophic errors
    catastrophic = []
    zero_locations_flag = False
    if len(ext_locations) == 0 and len(gt_locations) > 0:
        catastrophic.append("zero_locations")
        zero_locations_flag = True
    # Don't also fire location_count_mismatch when zero_locations already fired
    if not zero_locations_flag and abs(len(ext_locations) - len(gt_locations)) > 1:
        catastrophic.append("location_count_mismatch")
    if tiv_accuracy is not None and gt_tiv_raw and abs((ext_tiv_raw or 0) - gt_tiv_raw) / gt_tiv_raw > 0.10:
        catastrophic.append("tiv_off_10pct")

    # Check for missed sub-buildings
    gt_subs = [loc for loc in gt_locations if loc.get("is_sub_building")]
    if gt_subs:
        matched_indices = {gt_locations.index(m[1]) for m in matches}
        if any(gt_locations.index(sb) not in matched_indices for sb in gt_subs):
            catastrophic.append("missed_sub_buildings")

    # Composite: weight components that actually have signal. When a component
    # is absent (no matches → field_accuracy None; no GT TIV → tiv_accuracy
    # None), its weight is redistributed pro-rata to the rest. location_coverage
    # and the catastrophic term are always present.
    components: list[tuple[float, float]] = [(location_coverage, 0.40)]
    if field_accuracy is not None:
        components.append((field_accuracy, 0.35))
    if tiv_accuracy is not None:
        components.append((tiv_accuracy, 0.15))
    components.append((1.0 if not catastrophic else 0, 0.10))
    total_w = sum(w for _, w in components)
    composite = sum(v * w for v, w in components) / total_w

    return {
        "category": "sov",
        "location_coverage": round(location_coverage, 4),
        "field_accuracy": round(field_accuracy, 4) if field_accuracy is not None else None,
        "tiv_accuracy": round(tiv_accuracy, 4) if tiv_accuracy is not None else None,
        "composite_score": round(composite, 4),
        "catastrophic_errors": catastrophic,
        "catastrophic_count": len(catastrophic),
        "details": {
            "gt_locations": len(gt_locations),
            "ext_locations": len(ext_locations),
            "matched": len(matches),
            "gt_tiv": gt_tiv_raw,
            "ext_tiv": ext_tiv_raw,
        }
    }


# ── Loss Run Scoring ───────────────────────────────────────────────────


def match_claims(extracted: list, ground_truth: list) -> list[tuple[dict, dict]]:
    """Match claims by claim number. Each GT claim matches at most once."""
    gt_by_num: dict[str, tuple[int, dict]] = {}
    for i, c in enumerate(ground_truth):
        k = normalize_string(c.get("claim_number", ""))
        if k and k not in gt_by_num:
            gt_by_num[k] = (i, c)
    matches = []
    used: set[int] = set()
    for ext in extracted:
        ext_num = normalize_string(ext.get("claim_number", ""))
        if ext_num and ext_num in gt_by_num:
            idx, gt = gt_by_num[ext_num]
            if idx in used:
                continue
            used.add(idx)
            matches.append((ext, gt))
    return matches


def score_loss_run(extracted: dict, ground_truth: dict) -> dict:
    """Score loss run extraction."""
    gt_claims = ground_truth.get("claims", [])
    ext_claims = extracted.get("claims", [])
    gt_totals = ground_truth.get("grand_totals", {})

    matches = match_claims(ext_claims, gt_claims)
    claim_coverage = len(matches) / len(gt_claims) if gt_claims else 1.0

    # Field accuracy
    correct, total, cov_correct, cov_total = 0, 0, 0, 0
    for ext, gt in matches:
        for fld in ["paid", "reserved", "incurred"]:
            if gt.get(fld) is not None:
                total += 1
                if compare_values(ext.get(fld), gt.get(fld), "numeric"):
                    correct += 1
        if gt.get("date_of_loss"):
            total += 1
            if compare_values(ext.get("date_of_loss"), gt.get("date_of_loss"), "date"):
                correct += 1
        if gt.get("coverage"):
            cov_total += 1
            if normalize_string(ext.get("coverage")) == normalize_string(gt.get("coverage")):
                cov_correct += 1

    field_accuracy = correct / total if total else None
    coverage_accuracy = cov_correct / cov_total if cov_total else None

    # Totals accuracy. Same rule as SOV TIV: drop from composite when GT
    # doesn't carry the total, rather than awarding free 1.0.
    gt_incurred_raw = to_float(gt_totals.get("incurred"))
    ext_totals = extracted.get("grand_totals", {})
    ext_incurred_raw = to_float(ext_totals.get("incurred"))
    if gt_incurred_raw is not None and gt_incurred_raw > 0:
        ext_for_compare = ext_incurred_raw if ext_incurred_raw is not None else 0.0
        incurred_accuracy = max(0, 1.0 - abs(ext_for_compare - gt_incurred_raw) / gt_incurred_raw)
    else:
        incurred_accuracy = None

    catastrophic = []
    zero_claims_flag = False
    if len(ext_claims) == 0 and len(gt_claims) > 0:
        catastrophic.append("zero_claims")
        zero_claims_flag = True
    if not zero_claims_flag and len(gt_claims) > 0 and abs(len(ext_claims) - len(gt_claims)) / len(gt_claims) > 0.20:
        catastrophic.append("claim_count_off_20pct")
    if incurred_accuracy is not None and gt_incurred_raw and abs((ext_incurred_raw or 0) - gt_incurred_raw) / gt_incurred_raw > 0.15:
        catastrophic.append("incurred_off_15pct")

    # Composite with component rebalance + catastrophic term. Weights sum
    # to 1.00 when every component is present (claim_coverage 0.30 + field
    # 0.30 + incurred 0.20 + coverage 0.10 + catastrophic 0.10). Prior to
    # 2026-04-17 audit 2 they summed to 1.10 - math still normalized via
    # total_w but the effective weighting diverged from the documented
    # scheme, which a researcher cross-checking would flag.
    components: list[tuple[float, float]] = [(claim_coverage, 0.30)]
    if field_accuracy is not None:
        components.append((field_accuracy, 0.30))
    if incurred_accuracy is not None:
        components.append((incurred_accuracy, 0.20))
    if coverage_accuracy is not None:
        components.append((coverage_accuracy, 0.10))
    components.append((1.0 if not catastrophic else 0, 0.10))
    total_w = sum(w for _, w in components)
    composite = sum(v * w for v, w in components) / total_w

    return {
        "category": "loss_run",
        "claim_coverage": round(claim_coverage, 4),
        "field_accuracy": round(field_accuracy, 4) if field_accuracy is not None else None,
        "coverage_accuracy": round(coverage_accuracy, 4) if coverage_accuracy is not None else None,
        "incurred_accuracy": round(incurred_accuracy, 4) if incurred_accuracy is not None else None,
        "composite_score": round(composite, 4),
        "catastrophic_errors": catastrophic,
        "catastrophic_count": len(catastrophic),
        "details": {
            "gt_claims": len(gt_claims),
            "ext_claims": len(ext_claims),
            "matched": len(matches),
        }
    }


# ── Driver Schedule Scoring ────────────────────────────────────────────


def score_driver_schedule(extracted: dict, ground_truth: dict) -> dict:
    """Score driver schedule extraction."""
    gt_drivers = ground_truth.get("drivers", [])
    ext_drivers = extracted.get("drivers", [])

    # Match by name
    gt_by_name = {normalize_string(d.get("name", "")): d for d in gt_drivers}
    matches = []
    for ext in ext_drivers:
        name = normalize_string(ext.get("name", ""))
        if name in gt_by_name:
            matches.append((ext, gt_by_name[name]))

    driver_coverage = len(matches) / len(gt_drivers) if gt_drivers else 1.0

    # Field accuracy
    correct, total = 0, 0
    for ext, gt in matches:
        for fld in ["license_state", "sex", "mvr_status"]:
            if gt.get(fld):
                total += 1
                if normalize_string(ext.get(fld)) == normalize_string(gt.get(fld)):
                    correct += 1
        if gt.get("license_number"):
            total += 1
            if normalize_string(ext.get("license_number")) == normalize_string(gt.get("license_number")):
                correct += 1

    field_accuracy = correct / total if total else None

    catastrophic = []
    if len(ext_drivers) == 0 and len(gt_drivers) > 0:
        catastrophic.append("zero_drivers")

    components: list[tuple[float, float]] = [(driver_coverage, 0.50)]
    if field_accuracy is not None:
        components.append((field_accuracy, 0.40))
    components.append((1.0 if not catastrophic else 0, 0.10))
    total_w = sum(w for _, w in components)
    composite = sum(v * w for v, w in components) / total_w

    return {
        "category": "driver_schedule",
        "driver_coverage": round(driver_coverage, 4),
        "field_accuracy": round(field_accuracy, 4) if field_accuracy is not None else None,
        "composite_score": round(composite, 4),
        "catastrophic_errors": catastrophic,
        "catastrophic_count": len(catastrophic),
        "details": {
            "gt_drivers": len(gt_drivers),
            "ext_drivers": len(ext_drivers),
            "matched": len(matches),
        }
    }


# ── Generic / ACORD / Other Scoring ────────────────────────────────────


def score_generic(extracted: dict, ground_truth: dict, category: str) -> dict:
    """Generic scoring for ACORD forms, narratives, dec pages, etc."""
    header_score = score_header_fields(extracted, ground_truth)

    # Match structured lists where ground truth has non-empty lists.
    # If GT has no lists, list_coverage is absent from the composite
    # (we don't hand out free credit).
    #
    # ACORD / dec_page extractions nest these lists (e.g. locations live
    # under `additional_fields.premises` on ACORD 125, under `locations`
    # on dec pages, under various keys for coverages). Fall through to
    # nested candidate paths when the top-level key is empty - before
    # this lookup was added (2026-04-17 Bug B fix), ACORD list_coverage
    # was a flat 0.0% across every model.
    _LIST_ALIASES: dict[str, list[str]] = {
        "locations": [
            "locations",
            "additional_fields.premises",
            "additional_fields.locations",
            "premises",
            "applicant_info.locations",
            "applicant_info.premises",
            "property_schedule",
        ],
        "coverages": [
            "coverages",
            "coverages_requested",
            "coverage_schedule",
            "policy_info.coverages",
        ],
        "drivers": ["drivers", "driver_schedule", "additional_fields.drivers"],
        "locations_inspected": ["locations_inspected", "inspected_locations"],
        "recommendations": ["recommendations", "overall_assessment.recommendations"],
        "forms": ["forms", "forms_attached", "endorsements"],
        "endorsements": ["endorsements", "forms_attached", "forms"],
    }

    def _resolve_list(obj: dict, key: str) -> list:
        for p in _LIST_ALIASES.get(key, [key]):
            v = _get_by_path(obj, p)
            if isinstance(v, list) and v:
                return v
        # Fallback to exact top-level (may still be empty list, which is fine)
        v = obj.get(key)
        return v if isinstance(v, list) else []

    list_scores = []
    for list_key in _LIST_ALIASES.keys():
        gt_list = _resolve_list(ground_truth, list_key)
        if not gt_list:
            continue
        ext_list = _resolve_list(extracted, list_key)
        coverage = min(len(ext_list) / len(gt_list), 1.0)
        list_scores.append(coverage)

    list_coverage = sum(list_scores) / len(list_scores) if list_scores else None

    # Score all raw_ground_truth.fields using the aliased lookup.
    gt_raw = ground_truth.get("raw_ground_truth", {}).get("fields", {})
    field_hits = 0
    field_total = 0
    for key, val in gt_raw.items():
        gt_val = val.get("value") if isinstance(val, dict) else val
        if gt_val in (None, "", [], {}):
            continue
        field_total += 1
        ext_val = lookup_field(extracted, key)
        if compare_values(ext_val, gt_val, _field_type(key)):
            field_hits += 1

    field_accuracy = field_hits / field_total if field_total else None

    # Composite: weight components that actually have signal.
    # Header (30%) / lists (30%) / raw fields (40%). If a component
    # is absent, its weight is redistributed pro-rata to the rest.
    components = []
    if header_score["header_fields_scored"] > 0:
        components.append((header_score["header_accuracy"], 0.30))
    if list_coverage is not None:
        components.append((list_coverage, 0.30))
    if field_accuracy is not None:
        components.append((field_accuracy, 0.40))

    if components:
        total_w = sum(w for _, w in components)
        composite = sum(v * w for v, w in components) / total_w
    else:
        # GT has no header fields, no lists, and no raw_ground_truth.fields.
        # We verified this never hits in the current 148-doc set, but set
        # composite=None defensively so a schema drift doesn't silently drag
        # averages to 0. Downstream filters `composite_score is not None`.
        composite = None

    # Catastrophic error: model emitted nothing scoreable even though
    # GT had many fields.
    catastrophic = []
    if field_total >= 5 and field_hits == 0:
        catastrophic.append("zero_field_recall")

    return {
        "category": category,
        "header_accuracy": (
            round(header_score["header_accuracy"], 4)
            if header_score["header_accuracy"] is not None else None
        ),
        "list_coverage": round(list_coverage, 4) if list_coverage is not None else None,
        "field_accuracy": round(field_accuracy, 4) if field_accuracy is not None else None,
        "composite_score": round(composite, 4) if composite is not None else None,
        "catastrophic_errors": catastrophic,
        "catastrophic_count": len(catastrophic),
        "details": {
            "header_fields": header_score["header_fields_scored"],
            "raw_fields_checked": field_total,
            "raw_fields_hit": field_hits,
            "lists_scored": len(list_scores),
        }
    }


# ── Main Scoring Dispatch ──────────────────────────────────────────────


def score_extraction(extraction_path: Path, ground_truth: dict) -> dict | None:
    """Score a single extraction against ground truth."""
    try:
        extraction = json.loads(extraction_path.read_text())
    except Exception as e:
        return {"error": str(e), "file": str(extraction_path)}

    if "error" in extraction:
        return {"error": extraction["error"], "file": str(extraction_path)}

    category = ground_truth.get("category", "")

    if category == "sov":
        return score_sov(extraction, ground_truth)
    elif category == "loss_run":
        return score_loss_run(extraction, ground_truth)
    elif category == "driver_schedule":
        return score_driver_schedule(extraction, ground_truth)
    else:
        # Generic scoring for ACORD, engineering, dec page, financial, narrative
        return score_generic(extraction, ground_truth, category)


# ── Main ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Score nightmare benchmark extractions")
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--extractions", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results = {
        "model": args.extractions.name,
        "packets": {},
        "aggregate": {},
    }

    category_scores = {}

    for gt_file in sorted(args.ground_truth.glob("*.json")):
        if gt_file.name.endswith("_summary.json") or gt_file.name.endswith("_summary.csv"):
            continue

        gt_data = json.loads(gt_file.read_text())
        packet_id = gt_data.get("packet_id", gt_file.stem)

        print(f"Scoring {packet_id}...")

        packet_results = {"difficulty": gt_data.get("difficulty"), "documents": {}}

        for doc_key, doc_gt in gt_data.get("documents", {}).items():
            ext_file = args.extractions / f"extraction_{packet_id}_{doc_key}.json"
            if not ext_file.exists():
                ext_file = args.extractions / f"{packet_id}_{doc_key}.json"

            cat = doc_gt.get("category", "other")

            if not ext_file.exists():
                score = {
                    "category": cat,
                    "composite_score": 0.0,
                    "error": "extraction not found",
                    "catastrophic_errors": ["extraction_missing"],
                    "catastrophic_count": 1,
                }
            else:
                score = score_extraction(ext_file, doc_gt)
                # score_extraction returns {"error": ..., "file": ...} on
                # JSON-load failure or when the extraction payload itself
                # contains an "error" key (API stub). Treat as composite=0
                # so the doc stays in the denominator instead of silently
                # dropping out (v1 survivor-bias pattern).
                if score and "error" in score:
                    score = {
                        "category": cat,
                        "composite_score": 0.0,
                        "error": score.get("error"),
                        "file": score.get("file"),
                        "catastrophic_errors": ["extraction_errored"],
                        "catastrophic_count": 1,
                    }

            packet_results["documents"][doc_key] = score

            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append(score)

        results["packets"][packet_id] = packet_results

    # Aggregate by category. Per-metric averages (avg_location_coverage,
    # avg_field_accuracy, etc.) are emitted so generate_report.py has real
    # numbers to publish - the previous version emitted only avg_composite,
    # leaving every sub-metric column showing 0.0%.
    _PER_METRIC_KEYS = [
        "location_coverage", "field_accuracy", "tiv_accuracy",
        "claim_coverage", "coverage_accuracy", "incurred_accuracy",
        "driver_coverage", "list_coverage", "header_accuracy",
    ]

    def _avg_present(scores_list: list, key: str) -> float | None:
        vals = [s[key] for s in scores_list if isinstance(s, dict) and s.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    for cat, scores in category_scores.items():
        composites_all = [s["composite_score"] for s in scores if isinstance(s, dict) and s.get("composite_score") is not None]
        composites_scored = [s["composite_score"] for s in scores if isinstance(s, dict) and s.get("composite_score") is not None and "error" not in s]
        catastrophic = sum(s.get("catastrophic_count", 0) for s in scores if isinstance(s, dict))
        errored = sum(1 for s in scores if isinstance(s, dict) and "error" in s)
        scored = len(scores) - errored

        agg = {
            "count": len(scores),              # all attempts (denominator)
            "scored": scored,                  # extractions that scored cleanly
            "errored": errored,                # missing or errored extractions
            # avg_composite is the headline number: includes errored docs
            # (composite=0), so it reflects the full attempt denominator and
            # isn't inflated by silently dropping failures.
            "avg_composite": round(sum(composites_all) / len(composites_all), 4) if composites_all else 0,
            # avg_composite_scored excludes errored docs. Emitted separately
            # so a researcher cross-checking `scored * avg = sum` against
            # scored-only arithmetic gets a matching number. Most per-metric
            # `avg_*` keys below are scored-only too - avg_composite_scored
            # is the denominator-matched composite.
            "avg_composite_scored": round(sum(composites_scored) / len(composites_scored), 4) if composites_scored else None,
            "min_composite": round(min(composites_all), 4) if composites_all else 0,
            "max_composite": round(max(composites_all), 4) if composites_all else 0,
            "total_catastrophic": catastrophic,
        }
        for k in _PER_METRIC_KEYS:
            v = _avg_present(scores, k)
            if v is not None:
                agg[f"avg_{k}"] = v
        results["aggregate"][cat] = agg

    # Overall
    all_composites = [s["composite_score"] for scores in category_scores.values() for s in scores if isinstance(s, dict) and s.get("composite_score") is not None]
    scored_composites = [s["composite_score"] for scores in category_scores.values() for s in scores if isinstance(s, dict) and s.get("composite_score") is not None and "error" not in s]
    if all_composites:
        total_docs = sum(len(scores) for scores in category_scores.values())
        total_errored = sum(1 for scores in category_scores.values() for s in scores if isinstance(s, dict) and "error" in s)
        results["aggregate"]["overall"] = {
            "total_documents": total_docs,
            "scored_documents": total_docs - total_errored,
            "errored_documents": total_errored,
            "avg_composite": round(sum(all_composites) / len(all_composites), 4),
            "avg_composite_scored": round(sum(scored_composites) / len(scored_composites), 4) if scored_composites else None,
            "total_catastrophic": sum(
                r.get("total_catastrophic", 0)
                for k, r in results["aggregate"].items()
                if isinstance(r, dict) and k != "overall"
            ),
        }

    # Output
    output_path = args.output or (args.extractions / "scores.json")
    output_path.write_text(json.dumps(results, indent=2))

    print(f"\nResults: {output_path}")
    for cat, agg in results["aggregate"].items():
        if isinstance(agg, dict) and "avg_composite" in agg:
            print(f"  {cat}: {agg.get('count', '')} docs, {agg['avg_composite']:.1%} avg, {agg.get('total_catastrophic', 0)} catastrophic")


if __name__ == "__main__":
    main()
