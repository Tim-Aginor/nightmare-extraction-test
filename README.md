# Nightmare Extraction Test

Adversarial extraction test for commercial-insurance submission packets.
This release contains **all 5 packets (N1 Easy through N5 Nightmare,
148 documents total)** plus the full scoring pipeline, prompts, and
pre-run extractions from five frontier models at three reasoning effort
levels (15 cohorts total). Re-score everything locally with no API
keys, or re-run extraction against the corpus from scratch.

> Carrier names (AIG, Chubb, Hartford, Liberty Mutual, Nationwide,
> Travelers, Zurich, and others), some addresses, and form-template
> metadata reference real commercial insurance entities. Extractors that
> special-case real-world carriers would otherwise game the test. Every
> policy number, premium, claim value, insured name, loss history, and
> other data point attached to those carriers is synthetic and generated
> programmatically. Nothing in this corpus reflects any real entity's
> actual products, customers, financials, or operations.

Across 148 documents at default reasoning effort, the two OpenAI models
hallucinate numbers at **11.4%** (GPT-5.5) and **11.9%** (GPT-5.4). Opus 4.7
lands at **3.4%**, Sonnet 4.6 at **5.2%**. Gemini 3.1 Pro is at **3.2%**,
but its API default is thinking-on/HIGH (Google's docs are explicit that
it cannot be disabled), so Gemini is reported in the matched HIGH/XHIGH
tables of [`report.md`](report.md) rather than the default-only column.
The default table is GPT/Claude thinking-off versus each other.

Headline rates are precision-side (hallucinated / emitted). The
recall-side complement (correct, wrong-value, and omitted, against
GT-populated fields) lives in `report.md` under "Field-level error
breakdown (recall view)" and in
[`results_aggregate/field_breakdown.json`](results_aggregate/field_breakdown.json).
Omission rates cluster at 19-22% across all 15 model×effort cohorts, so
the cross-model spread on hallucination rate is not explained by some
models being selectively silent. The spread lives in the wrong-value
column.

Full breakdown by reasoning effort, category, difficulty, and recall
view in [`report.md`](report.md).

**Jump to:** [Repo layout](#repo-layout) · [Reproduce](#reproducing-the-findings) · [What's measured](#whats-measured) · [Re-run on your model](#re-running-on-your-own-model)
**See also:** [Full results tables](report.md) · [Methodology notes](report.md#methodology-notes) · [Two example cases](examples/)

## Repo layout

```
scripts/                  # Extraction + scoring + analysis (full pipeline)
├── run_extraction.py     # Calls OpenAI / Anthropic / Google APIs
├── score.py              # Per-doc composite scores + three-way field classification
├── hallucination_analysis.py
├── omission_breakdown.py # Recall-side aggregation (correct/wrong/omitted by cohort)
├── alias_audit.py
├── paired_stats.py
├── internal_consistency.py
├── recall_vs_fabrication.py
├── token_cap_audit.py
├── smoke_test_reasoning.py
├── generate_ground_truth.py
├── determinism_test.py   # Pre-publish gate: 4x PYTHONHASHSEED, byte-identical output
└── generate_report.py
prompts/                  # One extraction prompt per doc type
configs/models.yaml       # Model IDs + pricing + reasoning variants
schemas/                  # JSON schemas (one per ACORD form + supplemental)
packets/                  # Full corpus (148 docs across 5 packets)
├── N1_easy/doc_70001/{documents,ground_truth}/
├── N2_normal/doc_70002/{documents,ground_truth}/
├── N3_hard/doc_70003/{documents,ground_truth}/
├── N4_expert/doc_70004/{documents,ground_truth}/
└── N5_nightmare/doc_70005/{documents,ground_truth}/
ground_truth/             # Per-packet aggregated GT (one JSON per packet)
└── N{1..5}_*.json
results/                  # Pre-run extractions per cohort (5 models × 3 efforts)
├── gpt55/, gpt55_high/, gpt55_xhigh/
├── gpt54/, gpt54_high/, gpt54_xhigh/
├── opus47/, opus47_high/, opus47_xhigh/
├── sonnet/, sonnet_high/, sonnet_xhigh/
├── gemini_pro/, gemini_pro_high/, gemini_pro_xhigh/
└── analysis/             # Derived analyses (paired stats, recall, alias audit)
examples/
├── hallucinations/       # Two deep-dive cases (financial statement N3, ACORD 45 N5)
└── README.md
results_aggregate/        # Cross-model aggregate outputs (hallucination report, field breakdown, paired stats, etc.)
fields.json               # Field specification
report.md                 # Headline result tables from the full run
requirements.txt
run_benchmark.sh          # End-to-end driver
```

All scripts read `ground_truth/`, `results/`, and `packets/` from the
invoking directory, not from the script's own location. Run them from
this directory (the repo root after clone) and the paths work without
any setup.

## Reproducing the findings

Three levels of effort depending on how deep you want to go. All three
assume you've cloned this repo to `~/nightmare-benchmark` (adjust paths
below if you cloned elsewhere).

The corpus itself (the 148 rendered documents and per-doc generator
truth artifacts) is a fixed snapshot. `packets/` and `ground_truth/`
ship pre-populated, and the generator that produced them is not part
of this release. Re-scoring (Level 2) and re-extraction against the
published corpus (Level 3) are the supported reproducibility paths;
regenerating the corpus from a seed is not.

### Level 1: inspect the aggregate numbers (no install)

Every aggregate number in the writeup is derivable from files checked
in to this repo. No code execution needed.

```bash
cd ~/nightmare-benchmark

# Headline numeric/string hallucination rates + recall-view tables
cat report.md

# Paired stats: per-doc sign tests + cross-model agreement
jq '.pairwise_total_fabs, .cross_model_agreement_total' \
   results_aggregate/paired_stats.json

# Recall-side breakdown: correct / wrong / omitted per cohort
jq '.gpt55.overall, .opus47.overall' \
   results_aggregate/field_breakdown.json

# Per-model extraction volumes (strings/numbers per doc)
jq '.per_model' results_aggregate/recall_vs_fabrication.json

# Per-model composite scores and catastrophic flags
jq '.aggregate' results_aggregate/gpt54_scores.json
```

### Level 2: re-score pre-run extractions (~10 min, no API keys)

Runs the full scoring + hallucination + recall pipeline against the
pre-run extractions for all 15 cohorts (5 models × 3 efforts) across all
148 documents. Produces the per-doc numbers that feed into the aggregate
tables.

Requires Python 3.10+. The v1 analyzer is JSON-only, with no
`pdftotext`, OCR, or `openpyxl` dependencies. The per-packet universe is
built from the generator's own `document_truth_*.json`,
`field_truth_*.json`, and `packet_truth.json` artifacts, not from
re-parsing the rendered PDFs.

```bash
# From this directory (the clone of the public repo)
pip install -r requirements.txt
./run_benchmark.sh --score-only
```

`ground_truth/`, `results/`, and `packets/` are already populated from
the clone. The analyzer reads them in place and writes derived outputs
back to `results/hallucination_report.json`, `results/analysis/`, and
`report.md`. On the full 148-doc corpus the headline rates reproduce
within rounding of `results_aggregate/hallucination_report.json`.

### Level 3: full re-run against the APIs (~3-4 hours, ~$50 to $150)

Same workspace as Level 2 but with the extraction step too. Provide the
three API keys and `run_benchmark.sh` re-runs every document against
GPT-5.5, GPT-5.4, Claude Opus 4.7, Claude Sonnet 4.6, and Gemini 3.1 Pro
at default reasoning effort. (For the HIGH and XHIGH variants, pass
`--reasoning high` or `xhigh` to `run_extraction.py`.)

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...

# Single model spot-check
./run_benchmark.sh gpt54

# Full default-effort cohort across all 5 packets
./run_benchmark.sh
```

The extraction runs hit network timeouts on a handful of long
scan-heavy docs at HIGH/XHIGH effort. Seven repeatable cases, all in
`packets/N4_expert/` and `packets/N5_nightmare/`: `loss_run` and
`loss_run_excel` on N4; `loss_run`, `loss_run_excel`, `loss_run_csv`,
`driver_schedule`, and `acord_127` on N5. Those rows show up as missing
entries in the per-cohort scores rather than failing the whole run.

### Scoring your own extractor against the sample

Drop its outputs into
`./results/<yourmodel>/extraction_N1_easy_70001_<doc_key>.json` matching
the prompt schemas in `prompts/`, then:

```bash
python ~/nightmare-benchmark/scripts/score.py \
    --ground-truth ground_truth \
    --extractions results/<yourmodel> \
    --output results/<yourmodel>_scores.json
```

The 15 frontier-model cohorts under
`results/<model>[_high|_xhigh]/extraction_<packet>_<doc_key>.json` are
the side-by-side comparables.

## What's measured

The headline metric is the numeric hallucination rate: hallucinated
numbers divided by numbers emitted (precision-side, so the denominator
is values the model emitted). "Hallucinated" means the value does not
appear in the per-packet universe (packet GT plus per-document
generator artifacts: document_truth, field_truth, manifest, and
packet_truth JSON). A second pass in `alias_audit.py` re-checks each
flagged value by token-level coverage against that universe, so only
values that fail both passes are counted.

The recall-side complement lives in
[`results_aggregate/field_breakdown.json`](results_aggregate/field_breakdown.json)
and splits every GT-populated field into correct, wrong-value, and
omitted. The denominator is GT-populated fields rather than
model-emitted values, so a `null` where GT has a value counts as a
failure. Omission rates cluster at 19-22% across all 15 cohorts, which
means the cross-model spread on hallucination rate is not explained by
some models being selectively silent. The spread lives in the
wrong-value column.

Supplementary outputs include string hallucination rate, per-category
breakdowns, paired per-doc sign tests, bootstrap CIs,
recall-vs-hallucination Pareto, and per-doc internal-consistency
checks.

See [`report.md`](report.md) for the full results on the complete
5-packet run, including exact API settings per model and per-model run
counts (including timeout exclusions).

## Methodology notes

Full methodology notes live at the bottom of
[`report.md`](report.md#methodology-notes), alongside the tables they
apply to. They cover:

- Universe construction
- Scoring choices: exact-match numeric, exact-token strings, ACORD enum
  aliasing, and the `SKIP_LEAF_NAMES` allowlist
- Provider asymmetries: Anthropic tool_use envelope unwrap, tool_choice
  under reasoning, retry and timeout budgets, default reasoning effort
  across providers
- Statistical choices: single trial per cohort, micro-averaging,
  doc-level independence in the sign test, per-difficulty sample sizes

## Re-running on your own model

All 5 packets and all 15 cohorts ship with this repo, so a new
extractor can be measured against the same universe and the same
per-doc inputs with no further setup. Drop its outputs into
`results/<yourmodel>/extraction_<packet_id>_<doc_key>.json` and re-run
`./run_benchmark.sh --score-only`. The headline tables in `report.md`
will pick up your model in the per-doc and aggregate sections.

If you want help adapting prompts or have questions about the
methodology, email tim@aginor.ai.
