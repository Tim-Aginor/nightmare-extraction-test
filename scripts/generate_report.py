#!/usr/bin/env python3
"""Generate the hallucination-focused report for Nightmare Extraction Test.

Reads results/hallucination_report.json and emits a markdown report with
numeric hallucination rates (headline) and string hallucination rates
(supplementary) per model, per category, and per difficulty level. Only
the five published frontier models are included.

Usage:
    python scripts/generate_report.py --results results/ --output report.md
"""

import argparse
import json
from pathlib import Path


PUBLISHED_MODELS = ["gpt55", "gpt54", "opus47", "sonnet", "gemini_pro"]

# Gemini 3 has no thinking-off mode (its API default is already HIGH),
# so we exclude it from default-effort cross-model tables to keep those
# comparisons matched-off. It reappears in the HIGH and XHIGH tables,
# where all five models are at matched effort.
PUBLISHED_MODELS_DEFAULT = ["gpt55", "gpt54", "opus47", "sonnet"]

def _models_for_effort(effort: str) -> list[str]:
    return PUBLISHED_MODELS_DEFAULT if effort == "default" else PUBLISHED_MODELS

MODEL_DISPLAY = {
    "gpt54": "GPT-5.4",
    "gpt55": "GPT-5.5",
    "opus47": "Opus 4.7",
    "sonnet": "Sonnet 4.6",
    "gemini_pro": "Gemini 3.1 Pro",
}

# Reasoning-effort pivot: each base model expands to {default, HIGH, XHIGH}
# keys in the hallucination report. sonnet_xhigh uses effort=max under the
# hood (Opus-only ceiling) but is reported alongside the other XHIGH cells.
EFFORT_LEVELS = ["default", "high", "xhigh"]
EFFORT_DISPLAY = {"default": "Default", "high": "HIGH", "xhigh": "XHIGH"}

def _effort_key(base: str, level: str) -> str:
    return base if level == "default" else f"{base}_{level}"

CATEGORY_ORDER = [
    "sov", "loss_run", "acord_form", "driver_schedule", "dec_page",
    "engineering_report", "financial_statement", "narrative", "workbook",
]
CATEGORY_DISPLAY = {
    "sov": "SOV",
    "loss_run": "Loss Run",
    "acord_form": "ACORD Form",
    "driver_schedule": "Driver Schedule",
    "dec_page": "Dec Page",
    "engineering_report": "Engineering Report",
    "financial_statement": "Financial Statement",
    "narrative": "Narrative",
    "workbook": "Workbook",
}

DIFFICULTY_ORDER = ["N1_easy", "N2_normal", "N3_hard", "N4_expert", "N5_nightmare"]
DIFFICULTY_DISPLAY = {
    "N1_easy": "N1 (easy)",
    "N2_normal": "N2 (normal)",
    "N3_hard": "N3 (hard)",
    "N4_expert": "N4 (expert)",
    "N5_nightmare": "N5 (nightmare)",
}


def _fmt_rate(r: float | None) -> str:
    return f"{r:.1%}" if r is not None else "-"


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_No data available._"
    col_widths = [max(len(headers[i]), max(len(row[i]) for row in rows)) for i in range(len(headers))]
    hdr = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " |"
    sep = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
    data = ["| " + " | ".join(c.ljust(w) for c, w in zip(row, col_widths)) + " |" for row in rows]
    return "\n".join([hdr, sep] + data)


_KIND_KEYS = {
    "numeric": ("numbers_checked", "numbers_hallucinated", "number_hallucination_rate"),
    "string": ("strings_checked", "strings_hallucinated", "string_hallucination_rate"),
}


def field_breakdown_table(breakdown: dict, effort: str) -> str:
    """Recall-side view: for each model at the given effort, show the
    three-way split of GT-populated fields into correct / wrong-value /
    omitted. Addresses the "but what about hallucinations-via-omission?"
    objection: hallucination rate alone is precision-side (denominator =
    values the model emitted), so a model that returns null on hard fields
    gets a smaller denominator. The recall-side numbers below use a fixed
    GT-fields denominator across models so omissions are visible."""
    headers = ["Model", "GT fields", "Correct", "Wrong value", "Omitted", "Any error"]
    models = _models_for_effort(effort)
    rows = []
    for base in models:
        cohort = _effort_key(base, effort)
        c = breakdown.get(cohort, {}).get("overall")
        if not c:
            continue
        rows.append([
            MODEL_DISPLAY[base],
            str(c.get("fields_scored", 0)),
            _fmt_rate(c.get("correctness_rate_micro")),
            _fmt_rate(c.get("wrong_value_rate_micro")),
            _fmt_rate(c.get("omission_rate_micro")),
            _fmt_rate(c.get("any_error_rate_micro")),
        ])
    return _markdown_table(headers, rows)


def overall_table(report: dict, kind: str) -> str:
    check_k, hall_k, rate_k = _KIND_KEYS[kind]
    noun = "Numbers" if kind == "numeric" else "Strings"
    headers = ["Model", "Docs", f"{noun} Checked", "Hallucinated", "Rate"]
    rows = []
    for m in PUBLISHED_MODELS_DEFAULT:
        if m not in report:
            continue
        a = report[m]["aggregate"]["overall"]
        rows.append([
            MODEL_DISPLAY[m],
            str(a["docs"]),
            str(a[check_k]),
            str(a[hall_k]),
            _fmt_rate(a[rate_k]),
        ])
    return _markdown_table(headers, rows)


def effort_pivot_table(report: dict, kind: str) -> str:
    """Pivot table: rows = base model, columns = default/HIGH/XHIGH.
    Cells show the hallucination rate at that effort level. An asterisk
    marks cells where the variant excluded docs (timeouts); the table
    footnote lists the adjusted n.
    """
    _, _, rate_k = _KIND_KEYS[kind]
    headers = ["Model"] + [EFFORT_DISPLAY[e] for e in EFFORT_LEVELS]

    rows = []
    footnotes: list[str] = []
    for base in PUBLISHED_MODELS:
        row = [MODEL_DISPLAY[base]]
        for level in EFFORT_LEVELS:
            k = _effort_key(base, level)
            entry = report.get(k, {}).get("aggregate", {}).get("overall")
            if not entry:
                row.append("-")
                continue
            cell = _fmt_rate(entry[rate_k])
            expected_docs = report.get(base, {}).get("aggregate", {}).get("overall", {}).get("docs")
            this_docs = entry.get("docs")
            if expected_docs and this_docs and this_docs < expected_docs:
                cell += f"*"
                footnotes.append(f"{MODEL_DISPLAY[base]} {EFFORT_DISPLAY[level]}: n={this_docs} (excluded {expected_docs - this_docs} timed-out doc{'s' if expected_docs - this_docs != 1 else ''})")
            row.append(cell)
        rows.append(row)

    table = _markdown_table(headers, rows)
    if footnotes:
        table += "\n\n" + "\n".join(f"\\* {f}" for f in footnotes)
    return table


def grouped_rate_table(report: dict, kind: str, group_key: str,
                       order: list[str], display: dict[str, str],
                       label: str, sort_by_signal: bool = False,
                       effort: str = "default") -> str:
    """Per-group (category or difficulty) hallucination rates at the
    given effort level.

    When sort_by_signal is True, rows are ordered by GPT-5.4's rate
    descending (at the default effort level, so ordering is stable
    across the three effort tables) so the strongest-signal rows land
    at the top and zero-signal rows fall to the bottom. Difficulty
    tables still use canonical N1→N5 order (sort_by_signal=False).
    """
    _, _, rate_k = _KIND_KEYS[kind]
    models = _models_for_effort(effort)
    model_keys = [_effort_key(m, effort) for m in models]
    headers = [label, "Docs"] + [MODEL_DISPLAY[m] for m in models]

    present: set[str] = set()
    for mk in model_keys:
        if mk in report:
            present |= set(report[mk]["aggregate"].get(group_key, {}).keys())

    if sort_by_signal:
        # Order by the default-effort GPT rate so rows line up across
        # the three effort-level tables and readers can compare cells
        # at a fixed category.
        def _signal(key: str) -> float:
            entry = report.get("gpt54", {}).get("aggregate", {}).get(group_key, {}).get(key)
            return entry[rate_k] if entry and entry.get(rate_k) is not None else -1.0
        ordered = sorted(present, key=lambda k: (-_signal(k), order.index(k) if k in order else len(order)))
    else:
        ordered = [k for k in order if k in present]

    rows = []
    for k in ordered:
        docs = None
        for mk in model_keys:
            g = report.get(mk, {}).get("aggregate", {}).get(group_key, {})
            if k in g:
                docs = g[k]["docs"]
                break
        row = [display.get(k, k), str(docs) if docs is not None else "-"]
        for mk in model_keys:
            entry = report.get(mk, {}).get("aggregate", {}).get(group_key, {}).get(k)
            row.append(_fmt_rate(entry[rate_k]) if entry else "-")
        rows.append(row)
    return _markdown_table(headers, rows)


def overall_table_at(report: dict, kind: str, effort: str) -> str:
    """Same as overall_table but for a specified effort level."""
    check_k, hall_k, rate_k = _KIND_KEYS[kind]
    noun = "Numbers" if kind == "numeric" else "Strings"
    headers = ["Model", "Docs", f"{noun} Checked", "Hallucinated", "Rate"]
    rows = []
    for base in PUBLISHED_MODELS:
        mk = _effort_key(base, effort)
        if mk not in report:
            continue
        a = report[mk]["aggregate"]["overall"]
        rows.append([
            MODEL_DISPLAY[base],
            str(a["docs"]),
            str(a[check_k]),
            str(a[hall_k]),
            _fmt_rate(a[rate_k]),
        ])
    return _markdown_table(headers, rows)


def _emit_breakdowns_for_effort(lines: list[str], report: dict, kind: str, effort: str) -> None:
    """Emit per-category and per-difficulty tables for one effort level."""
    lines.append(grouped_rate_table(report, kind, "by_category",
                                    CATEGORY_ORDER, CATEGORY_DISPLAY, "Category",
                                    sort_by_signal=True, effort=effort))
    lines.append("")
    lines.append("_By difficulty:_")
    lines.append("")
    lines.append(grouped_rate_table(report, kind, "by_difficulty",
                                    DIFFICULTY_ORDER, DIFFICULTY_DISPLAY, "Difficulty",
                                    effort=effort))
    lines.append("")


def configuration_block() -> str:
    """API settings per model. Static text; the parameter strings and
    default-asymmetry caveats are load-bearing for reader trust, so they
    live here rather than being derived from models.yaml.
    """
    return "\n".join([
        "## Configuration",
        "",
        "Exact API settings per model. Thinking parameter names and defaults vary by provider.",
        "",
        "| Model | API model ID | Default | HIGH | XHIGH |",
        "|---|---|---|---|---|",
        "| GPT-5.5 | `gpt-5.5` | no `reasoning_effort` (thinking off) | `reasoning_effort: \"high\"` | `reasoning_effort: \"xhigh\"` |",
        "| GPT-5.4 | `gpt-5.4` | no `reasoning_effort` (thinking off) | `reasoning_effort: \"high\"` | `reasoning_effort: \"xhigh\"` |",
        "| Opus 4.7 | `claude-opus-4-7` | no `thinking` param (thinking off) | `thinking: {type:\"adaptive\"}, output_config: {effort:\"high\"}` | `thinking: {type:\"adaptive\"}, output_config: {effort:\"xhigh\"}` |",
        "| Sonnet 4.6 | `claude-sonnet-4-6` | no `thinking` param (thinking off) | `thinking: {type:\"adaptive\"}, output_config: {effort:\"high\"}` | `thinking: {type:\"adaptive\"}, output_config: {effort:\"max\"}` (Sonnet's API rejects `xhigh` with a 400; `max` is the Sonnet ceiling) |",
        "| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | `thinking_level` unset, defaults to HIGH per Google docs, cannot be disabled | `thinking_level: \"HIGH\"` | `thinking_budget: 32000` (Gemini has no native XHIGH level) |",
        "",
        "**Default-behavior asymmetry to flag explicitly:**",
        "",
        "- GPT-5.5, GPT-5.4, Opus 4.7, and Sonnet 4.6 default to thinking OFF when no reasoning parameter is passed. Anthropic's \"adaptive\" thinking mode is not the default; it requires explicit opt-in via `thinking: {type: \"adaptive\"}`.",
        "- Gemini 3.x series defaults to thinking-on at HIGH and cannot be disabled. Per Google docs: \"use dynamic thinking by default... defaults to high\" and \"Thinking cannot be turned off for Gemini 3 Pro and Gemini 3.1 Pro.\"",
        "- Because of this, Gemini 3.1 Pro is excluded from default-effort tables below. The symmetric comparison is GPT/Claude at no-thinking vs each other; Gemini joins the matched HIGH and XHIGH tables.",
        "- Sonnet 4.6's \"XHIGH\" row is run at `effort: \"max\"`, not `xhigh`. Sonnet's API does not accept `xhigh`. The label is retained for side-by-side comparison, but Sonnet at XHIGH is structurally capped at its provider's ceiling while GPT-5.4 and Opus 4.7 run at true `xhigh`.",
    ])


def per_model_counts_block(report: dict) -> str:
    """Per-model run counts at each effort, plus the convention for
    interpreting the "Docs" column in the per-category/per-difficulty
    tables. Pulled from the report so it stays in sync if rerun counts
    change.
    """
    headers = ["Model"] + [EFFORT_DISPLAY[e] for e in EFFORT_LEVELS]
    rows = []
    for base in PUBLISHED_MODELS:
        row = [MODEL_DISPLAY[base]]
        for level in EFFORT_LEVELS:
            mk = _effort_key(base, level)
            entry = report.get(mk, {}).get("aggregate", {}).get("overall", {})
            docs = entry.get("docs")
            row.append(str(docs) if docs is not None else "-")
        rows.append(row)
    table = _markdown_table(headers, rows)

    sonnet_xhigh_n = (
        report.get("sonnet_xhigh", {}).get("aggregate", {}).get("overall", {}).get("docs")
    )
    sonnet_caveat = (
        f" Sonnet 4.6 at XHIGH in particular has rates computed over n={sonnet_xhigh_n}, "
        "smaller than the Docs column suggests."
        if sonnet_xhigh_n is not None else ""
    )

    intro = (
        "Per-model run counts. Some docs deterministically time out at higher "
        "reasoning efforts even at a 1200s API timeout (Sonnet 4.6 on N4/N5 "
        "loss runs, GPT-5.4 on a handful of XHIGH cases)."
    )
    outro = (
        "All percentages compute against each model's actual run count. "
        "In the per-category and per-difficulty tables below, the \"Docs\" "
        "column is taken from the first model with data at that group "
        "(typically GPT-5.4) and does not reflect deeper exclusions for "
        f"other models.{sonnet_caveat}"
        "\n\n"
        "The smallest per-category cells (Dec Page n=5, Driver Schedule n=4, "
        "Engineering Report n=4) carry too few numeric facts per cohort for "
        "single-cell model comparisons to be meaningful — a single hallucinated "
        "value can move the rate 1-3pp. Use the headline numbers and the "
        "per-difficulty tables (each n=25-36) for cross-model claims; the "
        "small-N category cells are kept for completeness. v2 fills these in "
        "as packet count grows."
    )
    return f"{intro}\n\n{table}\n\n{outro}"


def main():
    parser = argparse.ArgumentParser(description="Generate Nightmare hallucination report")
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--output", type=Path, default=Path("report.md"))
    args = parser.parse_args()

    report_path = args.results / "hallucination_report.json"
    if not report_path.exists():
        print(f"ERROR: {report_path} not found. Run hallucination_analysis.py first.")
        return

    report = json.loads(report_path.read_text())

    # Recall-side breakdown is optional — only emitted if scoring +
    # omission_breakdown.py have been run. Headline hallucination
    # tables stand alone if the file is missing.
    breakdown_path = args.results / "analysis" / "field_breakdown.json"
    breakdown = json.loads(breakdown_path.read_text()) if breakdown_path.exists() else None
    loaded = [m for m in PUBLISHED_MODELS if m in report]
    variants_present = sum(
        1 for base in PUBLISHED_MODELS for level in EFFORT_LEVELS
        if _effort_key(base, level) in report
    )
    print(f"Loaded hallucination data for {len(loaded)} models "
          f"({variants_present}/{len(PUBLISHED_MODELS)*len(EFFORT_LEVELS)} effort variants): "
          f"{', '.join(loaded)}")

    lines: list[str] = []
    lines.append("# Nightmare Extraction Test - Hallucination Rates")
    lines.append("")
    lines.append(
        "Fabricated-value rates measured against the render-source universe "
        "(packet ground-truth + per-document generator artifacts: "
        "document_truth, field_truth, manifest, packet_truth JSON). "
        "A hallucination is an extracted value that doesn't match any value present "
        "in the source document or its render-time ground truth, after normalization."
    )
    lines.append("")

    lines.append(configuration_block())
    lines.append("")

    lines.append("## Numeric hallucination")
    lines.append("")
    lines.append(per_model_counts_block(report))
    lines.append("")
    lines.append("### Overall (default effort)")
    lines.append("")
    lines.append(
        "Gemini 3.1 Pro is omitted from this default-only table because "
        "its API default is already HIGH (no thinking-off mode), so a "
        "default-vs-default row would not be a matched comparison. "
        "Gemini's effective-default cell *is* shown in the cross-effort "
        "pivot below for completeness, but it represents HIGH-effort "
        "behavior, not thinking-off."
    )
    lines.append("")
    lines.append(overall_table(report, "numeric"))
    lines.append("")
    lines.append("### By reasoning effort")
    lines.append("")
    lines.append(
        "GPT-5.4 is the only model whose numeric hallucination rate "
        "drops with thinking effort, and even at XHIGH it remains 3-4× "
        "the Anthropic/Google baseline. GPT-5.5 (released April 23, 2026) "
        "does not reproduce that gradient — its rate is essentially flat "
        "across effort levels and at HIGH/XHIGH actually exceeds GPT-5.4. "
        "Opus, Sonnet, and Gemini show essentially flat behavior across "
        "effort levels."
    )
    lines.append("")
    lines.append(effort_pivot_table(report, "numeric"))
    lines.append("")
    for level in EFFORT_LEVELS:
        lines.append(f"### By category / difficulty - {EFFORT_DISPLAY[level]} effort")
        lines.append("")
        _emit_breakdowns_for_effort(lines, report, "numeric", level)

    lines.append("## String hallucination (supplementary)")
    lines.append("")
    lines.append(
        "String hallucination is dominated by transcription-like errors on "
        "policy and license numbers (single-character OCR errors on identifiers "
        "like `BND-88364-6825`). All five models produce similar string-level "
        "error rates on adversarial renders; the meaningful model differences "
        "live in the numeric table above."
    )
    lines.append("")
    lines.append("### Overall (default effort)")
    lines.append("")
    lines.append(
        "Gemini 3.1 Pro is omitted from this default-only table — see the "
        "note at the top of the numeric section."
    )
    lines.append("")
    lines.append(overall_table(report, "string"))
    lines.append("")
    lines.append("### By reasoning effort")
    lines.append("")
    lines.append(
        "String hallucination drops monotonically with thinking effort on "
        "GPT-5.4. GPT-5.5 does not reproduce that gradient — its rate barely "
        "moves across effort levels and starts higher than GPT-5.4 at every "
        "level. Opus, Sonnet, and Gemini remain roughly flat."
    )
    lines.append("")
    lines.append(effort_pivot_table(report, "string"))
    lines.append("")
    for level in EFFORT_LEVELS:
        lines.append(f"### By category / difficulty - {EFFORT_DISPLAY[level]} effort")
        lines.append("")
        _emit_breakdowns_for_effort(lines, report, "string", level)

    if breakdown is not None:
        lines.append("## Field-level error breakdown (recall view)")
        lines.append("")
        lines.append(
            "The headline hallucination rates above are **precision-side**: "
            "denominator = values the model emitted, so a model that returns "
            "`null` on hard fields gets a smaller denominator and looks better. "
            "This section flips to the **recall side**: denominator = "
            "GT-populated fields, and a `null` where GT has a value counts as "
            "an omission. Reading both together is the honest answer to \"does "
            "the headline credit models for refusing to answer?\""
        )
        lines.append("")
        lines.append(
            "**Empirically the omission rate is roughly constant across all "
            "models (~19-21% of GT-populated fields).** The cross-model spread "
            "lives in the wrong-value column, not the omitted column — i.e. "
            "models aren't gaming the headline by being selectively silent."
        )
        lines.append("")
        lines.append(
            "The ~20% omission floor is not a model defect on its own. The "
            "per-doc-type extraction prompts deliberately don't ask for every "
            "field that GT records (e.g., the SOV prompt asks for the SOV "
            "fields, not the producer's mailing address). Fields outside the "
            "prompt's scope show up here as omissions because the GT-side "
            "denominator covers everything generator-side, not just what we "
            "asked the model to extract. The *cross-model* delta is the "
            "interpretable signal; the floor is a property of the prompt "
            "design."
        )
        lines.append("")
        for level in EFFORT_LEVELS:
            lines.append(f"### {EFFORT_DISPLAY[level]} effort")
            lines.append("")
            lines.append(field_breakdown_table(breakdown, level))
            lines.append("")

    lines.append("## Methodology notes")
    lines.append("")
    lines.append(
        "- **Universe construction.** For each packet, the analyzer pools "
        "the packet GT plus every generator-side `document_truth_*.json`, "
        "`field_truth_*.json`, `manifest_*.json`, and `packet_truth.json` "
        "under `packets/{public,private}/<difficulty>/doc_<seed>/ground_truth/`. "
        "A pre-2026-05-11 audit caught the path resolver silently failing on "
        "the canonical layout, which had left tier-2 ingest as a no-op and "
        "inflated string rates by 4.5–7.9pp and numeric rates by 0.9–2.4pp "
        "per model. Numbers below are post-fix."
    )
    lines.append("")
    lines.append(
        "- **Packet-wide pooling.** Customer info (insured / producer / preparer "
        "/ carrier) is shared across docs in a packet. The universe is pooled "
        "per-packet so a real value modeled in doc-A's GT but not doc-B's "
        "doesn't false-flag on doc-B. Trade-off: a fabrication on doc-A that "
        "happens to coincide with a real GT value on doc-B passes here. "
        "Mitigated by per-doc-type sub-key audits in `internal_consistency.py`."
    )
    lines.append("")
    lines.append(
        "- **ACORD enum aliasing.** ACORD 125/140/160/24/27/28/45 schemas "
        "hard-enum `construction` and `roof_type` to short ACORD-formal lists; "
        "SOV/engineering schemas leave them as free strings. OpenAI/Gemini "
        "strict-mode silently nulls off-enum values while Anthropic tool_use "
        "emits literals. `score.py` accepts the documented "
        "abbreviation/full-name mappings in either direction (e.g., `MNC` "
        "matches `Masonry Non-Combustible`) so the same building is scored "
        "the same way regardless of which schema it appears under."
    )
    lines.append("")
    lines.append(
        "- **Exact-match numeric scoring.** Both `score.py` and "
        "`hallucination_analysis.py` compare numbers by exact equality "
        "after `to_float()` normalization (\"$1,500,000\" → `1500000.0`). "
        "v0 carried an inherited ±1% relative tolerance with a 0.5 "
        "absolute floor for `|val|<50`; an audit caught it masking real "
        "model errors (cents-truncated $153,631 against $153,631.51, "
        "$24,344,800 against rendered $24,514,100, year off-by-one "
        "silently scored correct). Villify renders exact numeric values "
        "and ground truth mirrors them, so any post-normalization "
        "mismatch is model error — the band was hiding the exact failure "
        "mode the test exists to surface. Numeric hallucination rates "
        "moved up 2–8pp per cohort against the tolerance-era numbers."
    )
    lines.append("")
    lines.append(
        "- **Composite scoring.** `score.py` composite weighting "
        "redistributes pro-rata when a component returns None (e.g., no "
        "matched locations → no field comparisons available). This means the "
        "composite is averaged over present components per-doc; readers "
        "comparing composite_score across models should treat it as a "
        "supplementary measure. The headline numbers above (hallucination "
        "rates) do not use this composite."
    )
    lines.append("")
    lines.append(
        "- **Micro vs macro averaging.** Headline rates are micro-averaged: "
        "`total_hallucinated / total_checked` summed across the 148 docs of "
        "a cohort. Per-doc macro averages (mean of per-doc rates) are "
        "available in `paired_stats.json → difficulty_bootstrap` and within "
        "the per-doc score files; they tell a similar story but weight all "
        "docs equally regardless of how many numbers/strings the doc "
        "carries."
    )
    lines.append("")
    lines.append(
        "- **Single trial per (model, effort, doc).** No `seed` is passed "
        "on any provider path — the Anthropic API exposes no `seed` "
        "parameter as of 2026-05, and reasoning calls also require "
        "`temperature=1.0`, so all three providers are equally unseeded "
        "for symmetry. Point estimates would shift by ≤0.5pp on a fresh "
        "re-run; the bootstrap 95% CIs in "
        "`paired_stats.json → difficulty_bootstrap` are the conservative "
        "read on that residual noise."
    )
    lines.append("")
    lines.append(
        "- **Doc-level independence in the sign test.** The sign tests in "
        "`paired_stats.json` treat the 148 docs as independent. Customer "
        "info is pooled per-packet (insured/producer/preparer shared "
        "across the ~25-36 docs in a packet), so errors within a packet "
        "correlate slightly. The bootstrap CIs (resampled per-doc) are "
        "the right number to cite when within-packet correlation matters."
    )
    lines.append("")
    lines.append(
        "- **Determinism gate.** `scripts/determinism_test.py` runs the "
        "analyzer in four subprocesses with different `PYTHONHASHSEED` "
        "values and asserts byte-identical output. rc=0 is a hard "
        "pre-publish gate."
    )
    lines.append("")

    args.output.write_text("\n".join(lines))
    print(f"Report written to: {args.output}")


if __name__ == "__main__":
    main()
