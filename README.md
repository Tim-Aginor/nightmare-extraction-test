# Nightmare Extraction Test

Adversarial extraction test for commercial-insurance submission packets.
This release contains **all 5 packets (N1 Easy through N5 Nightmare,
148 documents total)** plus the full scoring pipeline, prompts, and
pre-run extractions from five frontier models at three reasoning effort
levels (15 cohorts total). Re-score everything locally with no API
keys, or re-run extraction against the corpus from scratch.

> **Note on real entity names.** Carrier names (AIG, Chubb, Hartford,
> Liberty Mutual, Nationwide, Travelers, Zurich, and others), some
> addresses, and form-template metadata reference real commercial
> insurance entities for adversarial realism — extractors that special-
> case real-world carriers would otherwise game the test. All policy
> numbers, premiums, claim values, insured names, loss histories, and
> every other data point attached to those carriers is **synthetic and
> generated programmatically**; nothing in this corpus reflects any
> real entity's actual products, customers, financials, or operations.

Across 148 documents at default reasoning effort, the two OpenAI models
hallucinate numbers at **11.4%** (GPT-5.5) and **11.9%** (GPT-5.4); Opus 4.7
at **3.4%**, Sonnet 4.6 at **5.2%**. Gemini 3.1 Pro lands at **3.2%**,
but its API default is thinking-on/HIGH (Google's docs are explicit: it
cannot be disabled), so Gemini is reported in the matched HIGH/XHIGH
tables of [`report.md`](report.md) rather than the default-only column —
the default table is GPT/Claude thinking-off vs each other.

Headline rates are **precision-side** (hallucinated / emitted). The
**recall-side complement** — correct vs wrong-value vs omitted, against
GT-populated fields — is in `report.md` under "Field-level error
breakdown (recall view)" and in
[`results_aggregate/field_breakdown.json`](results_aggregate/field_breakdown.json).
Omission rates cluster at 19-22% across all 15 model×effort cohorts; the
cross-model spread lives in the wrong-value column, not the omitted
column.

Full breakdown by reasoning effort, category, difficulty, and recall
view in [`report.md`](report.md).

**Jump to:** [Repo layout](#repo-layout) · [Reproduce](#reproducing-the-findings) · [What's measured](#whats-measured) · [Methodology](#methodology-notes) · [Full test set](#full-test-set)

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
├── baseline_N1/          # Slice copy of N1 Easy with extractions inline
├── hallucinations/       # Two deep-dive cases (financial statement, ACORD 45)
├── timeouts/             # Source PDFs for the docs that timed out at HIGH/XHIGH
└── README.md
results_aggregate/        # Cross-model aggregate outputs (hallucination report, field breakdown, paired stats, etc.)
fields.json               # Field specification
report.md                 # Headline result tables from the full run
requirements.txt
run_benchmark.sh          # End-to-end driver
```

All scripts read `ground_truth/`, `results/`, and `packets/` **from the
invoking directory**, not from the script's own location. Run them
from this directory (the repo root after clone) and the paths just
work; nothing to wire up.

## Reproducing the findings

Three levels of effort depending on how deep you want to go. All three
assume you've cloned this repo to `~/nightmare-benchmark` (adjust paths
below if you cloned elsewhere).

The corpus itself (the 148 rendered documents + per-doc generator
truth artifacts) is a fixed snapshot — `packets/` and `ground_truth/`
both ship pre-populated, and the generator that produced them is not
part of this release. Re-scoring (Level 2) and re-extraction against
the published corpus (Level 3) are the supported reproducibility
paths; regenerating the corpus from a seed is not.

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

**Prerequisites:** Python 3.10+. The v1 analyzer is JSON-only — no
`pdftotext`, OCR, or `openpyxl` dependencies. The per-packet universe is
built from the generator's own `document_truth_*.json` /
`field_truth_*.json` / `packet_truth.json` artifacts, not from re-parsing
the rendered PDFs.

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
scan-heavy docs at HIGH/XHIGH effort (see `examples/timeouts/` for the
seven repeatable cases) — those rows show up as missing entries in the
per-cohort scores rather than failing the whole run.

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
the side-by-side comparables. The convenience slice under
`examples/baseline_N1/N1_easy_70001/extractions/<model>/<doc_key>.json`
keeps the N1 cohort in one place if you only want to spot-check that
tier.

## What's measured

**Headline metric: numeric hallucination rate** = hallucinated numbers /
numbers emitted (precision-side, denominator = values the model emitted).
"Hallucinated" means the value does not appear in the per-packet universe
(packet GT + per-document generator artifacts: document_truth,
field_truth, manifest, packet_truth JSON). A second pass
(`alias_audit.py`) double-checks each flagged value by token-level
coverage against that universe; only values that fail both passes are
counted.

**Recall-side complement: field-level error breakdown**
(`results_aggregate/field_breakdown.json`) splits every GT-populated
field into correct / wrong-value / omitted. The denominator is
GT-populated fields (not model-emitted values), so a `null` where GT has
a value counts as a failure. Empirically, omission rates cluster at
19-22% across all 15 cohorts, so the cross-model spread on hallucination
rate is not explained by some models being selectively silent — the
spread lives in the wrong-value column.

**Supplementary:** string hallucination rate, per-category breakdowns,
paired per-doc sign tests, bootstrap CIs, recall-vs-hallucination Pareto,
and per-doc internal-consistency checks.

See [`report.md`](report.md) for the full results on the complete
5-packet run, including exact API settings per model and per-model run
counts (including timeout exclusions).

## Methodology notes

A few choices worth calling out so reviewers don't have to reverse-engineer
them from the code.

**Universe construction.** For each packet, the analyzer pools the
packet GT plus every generator-side `document_truth_*.json`,
`field_truth_*.json`, `manifest_*.json`, and `packet_truth.json` under
`packets/<difficulty>/doc_<seed>/ground_truth/`. A pre-publish audit on
2026-05-11 caught the path resolver silently failing on the canonical
layout — tier-2 ingest was a no-op for several days, which inflated
string rates by 4.5-7.9pp and numeric rates by 0.9-2.4pp per model.
The numbers in `report.md` are post-fix.

**Determinism gate.** `scripts/determinism_test.py` runs the analyzer in
four subprocesses with different `PYTHONHASHSEED` values and asserts
byte-identical output (SHA256 match across runs). rc=0 is a hard
pre-publish gate.

**Packet-wide pooling.** Customer info (insured / producer / preparer /
carrier) is shared across docs in a packet. The universe is pooled
per-packet so a real value modeled in doc-A's GT but not doc-B's doesn't
false-flag on doc-B. Trade-off: a hallucination on doc-A that happens to
coincide with a real GT value on doc-B passes here. Mitigated by
per-doc-type sub-key audits in `internal_consistency.py`.

**Exact-token composed-string acceptance.** For multi-token string
values, `hallucination_analysis.py` (`string_in_universe`) accepts only
when EVERY token appears in the source universe. v0 used an 80%-of-tokens
fuzzy rule that admitted a single hallucinated token inside a long
compound string (e.g. `"9900 state road philadelphia pa 19136"` against a
rendered `"8717 ..."`); audit on 2026-05-12 caught that admitting real
errors, one-sided against the over-emitting (typically OpenAI) cohorts.
Same failure mode as the dropped numeric tolerance. Legitimate
concatenations like `"LOC-001: Preston Center Tower, 8117 Preston Road,
Dallas, TX 75225"` still pass because every component IS in the source.
String hallucination rates moved up 0.2 to 1.5pp per cohort (OpenAI side
hit ~3x harder, matching the asymmetry the v0 rule was hiding).

**ACORD enum aliasing.** ACORD 125/140/160/24/27/28/45 schemas hard-enum
`construction` and `roof_type` to short ACORD-formal lists;
SOV/engineering schemas leave them as free strings. OpenAI/Gemini
strict-mode silently nulls off-enum values while Anthropic tool_use
emits literals. `score.py` accepts the documented abbreviation/full-name
mappings in either direction (e.g., `MNC` matches `Masonry
Non-Combustible`) so the same building is scored the same way regardless
of which schema it appears under.

**Anthropic tool_use envelope unwrap.** Anthropic's `tool_use` enforces
JSON shape best-effort, not strictly. On a non-trivial fraction of
documents Opus 4.7 wraps the schema payload in a single-key envelope —
observed keys include `data`, `input`, `extract`, `document`,
`extracted_data`, and more (an allowlist kept growing per run, so
detection is by shape, not key name). `run_extraction.py` (lines
328-337) detects an envelope when the only top-level key is NOT a
schema property AND the inner dict has ≥2 keys that ARE schema
properties, and unwraps. OpenAI's strict mode and Gemini's structured
output prevent the envelope from forming in the first place, so this
fix-up fires only on the Anthropic path. Called out because it
materially changes how many Anthropic responses parse cleanly into the
expected shape; without it the Anthropic numbers would be inflated by
parse failures rather than reflecting model behavior.

**Anthropic tool_choice asymmetry under reasoning.** With reasoning
off, the Anthropic call uses `tool_choice: {type: "tool", name:
"extract"}` — the model is required to call the tool, which makes
schema enforcement as strict as OpenAI/Gemini strict modes. With
reasoning on, that combination is rejected by the API. Per
[Anthropic's extended-thinking docs](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking):
"Tool use with thinking only supports `tool_choice: {"type": "auto"}`
... Using `tool_choice: {"type": "any"}` or `tool_choice: {"type":
"tool", "name": "..."}` will result in an error because these options
force tool use, which is incompatible with extended thinking." Anthropic
HIGH and XHIGH therefore run with `tool_choice: auto`. The schema is
still attached and the model still calls the tool in practice, but
enforcement is advisory rather than strict at HIGH/XHIGH. OpenAI and
Gemini keep strict schema enforcement on under reasoning, so the
strict-mode asymmetry exists only at HIGH/XHIGH on the Anthropic path.

**Exact-match numeric scoring.** Both `score.py` and
`hallucination_analysis.py` compare numbers by exact equality after
`to_float()` normalization ("$1,500,000" → `1500000.0`). v0 carried an
inherited ±1% relative tolerance with a 0.5 absolute floor for
`|val|<50`; an audit caught it masking real model errors (cents-truncated
$153,631 against $153,631.51, $24,344,800 against rendered $24,514,100,
year off-by-one silently scored correct). Villify renders exact numeric
values and ground truth mirrors them, so any post-normalization mismatch
is model error — the band was hiding the exact failure mode the test
exists to surface. Numeric hallucination rates moved up 2–8pp per cohort
against the tolerance-era numbers.

**Fields excluded from the precision-side universe check.** A fixed
allowlist of leaf names is skipped in
`hallucination_analysis.py: SKIP_LEAF_NAMES` (lines 408-428): schema
enums whose value is constrained at the API level rather than drawn
from document text (`coverage_type`, `entity_type`, `mvr_status`, `sex`,
`license_state`, `priority`, `status`, `category`, `risk_level`,
`insurability`, `period_type`, `statement_type`, `construction`,
`occupancy`, ...); ACORD form metadata (`form_number`, `form_edition`,
`form_title`); producer fields not modeled in GT; and free-text summary
prose (`summary`, `description`, `notes`, `remarks`,
`executive_summary`, `operations_description`, `safety_programs`,
`claims_narrative`, `nature_of_business`, `loss_history_summary`).
Either the value is constrained by strict-mode so universe-match is
meaningless, or the field is summary prose that won't appear word-for-
word in the source. Applied uniformly across all five cohorts.
Recall-side scoring (`field_breakdown.json`) still catches wrong values
on the strict-enum fields — they're omitted only from the
precision-side hallucination universe, not from the broader
correct/wrong/omitted accounting.

**Universe is model-agnostic.** Per-packet universes are built from two
sources: packet ground truth, and the generator-side
document/field/manifest/packet truth JSON emitted alongside each
rendered doc. No model extractions ever feed back into the universe, so
one model's hallucinations cannot mask another's. Live PDF/XLSX/OCR
parsing was retired 2026-05-08 after a parallel-construction
cross-check confirmed the JSON-only path matches the parsed-doc path on
89% of doc verdicts and within ≤0.06pp on aggregate numeric
hallucination rates.

**Token-cap audit.** Default-mode output caps are 32K on OpenAI and
Anthropic, 128K on Gemini — i.e. Gemini has 4× the default-mode
headroom. Reasoning-mode caps are 128K on all three providers (matched).
`scripts/token_cap_audit.py` reports per-doc total tokens; on GPT-5.4
the max across 148 docs is ~15,700 tokens (about 49% of the cap), with
zero docs above 75% of cap. No completion approached its configured
ceiling on v1, so the default-mode asymmetry didn't bite, but it's
disclosed because we couldn't match it without subsidizing one provider.

**Retry budgets.** On transient errors (429 / 5xx) OpenAI and
Anthropic each run a 5-attempt outer loop (~90s exponential backoff,
60s cap) on top of the SDK's own retry layer (`max_retries=2` is the
default for both providers' Python SDKs), so a single transient can be
retried up to ~15 times before the outer loop gives up — same shape on
both. Gemini's outer loop runs 7 attempts (~250s). The Gemini extra is
in-code-justified by N1/N2 ACORDs hitting deterministic 503 "high
demand" windows; without it Gemini would lose docs to vendor flakiness
rather than capability. The outer-loop asymmetry (5 / 5 / 7) is a
choice, not a wash. See
[methodology](https://aginor.ai/extraction-test-methodology/#choices)
for the full list of provider-side asymmetries.

**Per-request timeouts.** OpenAI and Gemini use SDK defaults.
Anthropic is set explicitly to 300s in default mode and 1200s under
reasoning — Sonnet 4.6 on N4/N5 loss runs at high effort exceeds the
SDK default deterministically. The 1200s ceiling covers the slowest
observed cases; runs above it are reported as timeouts (see `examples/
timeouts/`). Provider-side asymmetry; called out because we couldn't
match it without losing Anthropic reasoning runs to the client.

**Reasoning effort and provider defaults.** The full run tested each
model at default, HIGH, and XHIGH effort. Default behavior is not
symmetric across providers: GPT-5.5, GPT-5.4, Opus 4.7, and Sonnet 4.6
default to thinking *off* (no reasoning parameter passed); Gemini 3.x
defaults to thinking *on* at HIGH and cannot be disabled per Google's
docs. The default-only tables in `report.md` therefore exclude Gemini
(it has no matching thinking-off mode), and the matched HIGH and XHIGH
tables include all five. Sonnet 4.6 also has no `xhigh` API level — its
"XHIGH" row runs at `effort: "max"`, the Sonnet ceiling. Full per-model
API settings are in [`report.md`](report.md#configuration).

**Micro- vs macro-averaging.** Headline rates are micro-averaged:
`total_hallucinated / total_checked` summed across the 148 docs of a
cohort. Per-doc macro averages (mean of per-doc rates) are available in
`paired_stats.json → difficulty_bootstrap` and within the per-doc score
files; they tell a similar story but weight all docs equally regardless
of how many numbers/strings the doc carries.

**Single trial per (model, effort, doc).** No `seed` is passed on any
provider path — the Anthropic API exposes no `seed` parameter as of
2026-05, and reasoning calls also require `temperature=1.0`, so all
three providers are equally unseeded for symmetry. Point estimates
would shift by ≤0.5pp on a fresh re-run; the bootstrap 95% CIs in
`paired_stats.json → difficulty_bootstrap` are the conservative read
on that residual noise.

**Doc-level independence in the sign test.** The sign tests in
`paired_stats.json` treat the 148 docs as independent. Customer info is
pooled per-packet (insured/producer/preparer shared across the ~25-36
docs in a packet), so errors within a packet correlate slightly. The
bootstrap CIs (resampled per-doc) are the right number to cite when
within-packet correlation matters.

**Difficulty-level sample sizes.** Per-difficulty rates in the headline
tables reflect 25 (N1, N2), 30 (N3), 36 (N4), and 32 (N5) documents
respectively. Within-difficulty comparisons are paired across models.
Bootstrap 95% CIs on those rates are in [`results_aggregate/paired_stats.json`](results_aggregate/paired_stats.json)
under `difficulty_bootstrap`.

**Category-level ranking is not monotone with the headline.** At
default effort the loss-run category inverts the cross-model order:
Opus 4.7 and Sonnet 4.6 hallucinate at 9.1% and 11.8% on loss-run
numbers, vs 2.7% and 3.2% for GPT-5.5 and GPT-5.4 (full table in
`report.md`). The other six categories track the headline direction.
Per-category cells run on n=4-15 docs at N=1 trial per (model, effort,
doc), so single-cell model comparisons carry more Monte Carlo noise
than headline or per-difficulty rates (n=25-36). Worth knowing about,
but the headline and per-difficulty numbers are the load-bearing
comparisons.

## Re-running on your own model

All 5 packets and all 15 cohorts ship with this repo, so a new extractor
can be measured against the same universe and the same per-doc inputs
without back-and-forth. Drop its outputs into
`results/<yourmodel>/extraction_<packet_id>_<doc_key>.json` and re-run
`./run_benchmark.sh --score-only`. The headline tables in `report.md`
will pick up your model in the per-doc + aggregate sections.

If you want help adapting prompts or have questions about the
methodology, email tim@aginor.ai.
