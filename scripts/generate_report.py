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
        "(generator ground-truth JSONs + pdftotext + openpyxl cells + OCR fallback). "
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
        "Gemini 3.1 Pro is excluded from default-effort tables - its API "
        "default is HIGH (no thinking-off mode), so a default-vs-default row "
        "would not be a matched comparison. It appears in the matched HIGH "
        "and XHIGH tables below."
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
        "Gemini 3.1 Pro is excluded from default-effort tables - see the "
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

    args.output.write_text("\n".join(lines))
    print(f"Report written to: {args.output}")


if __name__ == "__main__":
    main()
