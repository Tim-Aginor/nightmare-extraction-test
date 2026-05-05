# Nightmare Extraction Test

Adversarial extraction test for commercial-insurance submission packets.
This release contains **one sample packet (N1 Easy, ~25 docs)** plus the
full scoring pipeline and prompts. The remaining four packets (N2 Normal
through N5 Nightmare) are held privately; see "Full test set" below.

Across 148 documents, **GPT-5.5 fabricates numbers at 2.8% (default), 3.3% (HIGH), 2.9% (XHIGH)** - worse than its predecessor GPT-5.4 (3.2% / 1.6% / 2.1%) at HIGH and XHIGH, and 3-7x the Anthropic and Google flagship rates: Opus 4.7 (0.4% / 0.5% / 0.6%), Sonnet 4.6 (0.9% / 1.0% / 0.9%), Gemini 3.1 Pro (0.5% / 0.9% / 0.5%). Full breakdown by reasoning effort, category, and difficulty in [`report.md`](report.md).

**Jump to:** [Repo layout](#repo-layout) · [Reproduce](#reproducing-the-findings) · [What's measured](#whats-measured) · [Methodology](#methodology-notes) · [Full test set](#full-test-set) · [Acknowledgements](#acknowledgements)

## Repo layout

```
scripts/                  # Extraction + scoring + analysis (full pipeline)
├── run_extraction.py     # Calls OpenAI / Anthropic / Google APIs
├── score.py              # Per-doc composite scores
├── hallucination_analysis.py
├── alias_audit.py
├── paired_stats.py
├── internal_consistency.py
├── recall_vs_fabrication.py
├── token_cap_audit.py
├── smoke_test_reasoning.py
├── generate_ground_truth.py
└── generate_report.py
prompts/                  # One extraction prompt per doc type
configs/models.yaml       # Model IDs + pricing + reasoning variants
examples/
├── baseline_N1/          # N1 Easy packet (25 docs), source + pre-run extractions
├── hallucinations/       # Two deep-dive cases (financial statement, ACORD 45)
├── timeouts/             # Source PDFs for the docs that timed out at HIGH/XHIGH
└── README.md
results_aggregate/        # Cross-model aggregate outputs (hallucination report, paired stats, etc.)
fields.json               # Field specification
report.md                 # Headline result tables from the full run
requirements.txt
run_benchmark.sh          # End-to-end driver
```

All scripts read `ground_truth/` and `results/` **from the invoking
directory**, not from the script's own location. You reproduce the test by
running from a directory that contains your own `ground_truth/` and
`results/` subfolders.

## Reproducing the findings

Three levels of effort depending on how deep you want to go. All three
assume you've cloned this repo to `~/nightmare-benchmark` (adjust paths
below if you cloned elsewhere).

### Level 1: inspect the aggregate numbers (no install)

Every aggregate number in the writeup is derivable from files checked
in to this repo. No code execution needed.

```bash
cd ~/nightmare-benchmark

# Headline numeric/string hallucination rates by model, category, difficulty
cat report.md

# Paired stats: per-doc sign tests + cross-model agreement
jq '.pairwise_total_fabs, .cross_model_agreement_total' \
   results_aggregate/paired_stats.json

# Per-model extraction volumes (strings/numbers per doc)
jq '.per_model' results_aggregate/recall_vs_fabrication.json

# Per-model composite scores and catastrophic flags
jq '.aggregate' results_aggregate/gpt54_scores.json
```

### Level 2: re-score pre-run extractions (~5 min, no API keys)

Runs the full scoring + hallucination pipeline against the five
frontier models' pre-run extractions (default / HIGH / XHIGH efforts)
on the N1 sample packet. Produces the per-doc numbers that feed into
the aggregate tables.

**Prerequisites:** Python 3.10+, `poppler-utils` for `pdftotext`
(`apt install poppler-utils` on Debian/Ubuntu, `brew install poppler` on
macOS).

```bash
# Python deps (easyocr will download ~100 MB of PyTorch models on first run)
pip install -r ~/nightmare-benchmark/requirements.txt

# Fresh workspace
mkdir -p ~/nightmare-run && cd ~/nightmare-run

# Wire the sample packet GT into a ground_truth/ dir the scripts will glob
mkdir -p ground_truth
ln -s ~/nightmare-benchmark/examples/baseline_N1/N1_easy_70001/source/ground_truth.json \
      ground_truth/N1_easy_70001.json

# Copy pre-run extractions into the layout the scripts expect
# (examples/baseline_N1/.../extractions/<model>/<doc>.json  ->  results/<model>/extraction_N1_easy_70001_<doc>.json)
for model in gpt55 gpt54 opus47 sonnet gemini_pro \
             gpt55_high gpt54_high opus47_high sonnet_high gemini_pro_high \
             gpt55_xhigh gpt54_xhigh opus47_xhigh sonnet_xhigh gemini_pro_xhigh; do
    mkdir -p results/$model
    for src in ~/nightmare-benchmark/examples/baseline_N1/N1_easy_70001/extractions/$model/*.json; do
        cp "$src" results/$model/extraction_N1_easy_70001_$(basename "$src")
    done
done

# Score + hallucination analysis (no API keys needed)
~/nightmare-benchmark/run_benchmark.sh --score-only
```

Outputs land in `./results/` and `./report.md`. On the N1 sample you
should see numeric-hallucination rates around 0.0 to 0.2% across all five
models (matches the "N1 (easy)" row of `report.md`).

**Note:** N1 is the easy tier, and all five frontier models extract it
near-cleanly. The cross-model gap (the OpenAI models at 3-6× the
Anthropic/Google rates) shows up starting at N2 and widens through N5.
The N1 sample validates the pipeline; the headline gap lives in
[`report.md`](report.md), not in what you can run locally.

### Level 3: full re-run against the APIs (~15 min, ~$5 to $15)

Same workspace as Level 2, minus the extraction-copy step, plus three
API keys. Re-runs extraction on every document in the N1 sample against
GPT-5.5, GPT-5.4, Claude Opus 4.7, Claude Sonnet 4.6, and Gemini 3.1 Pro.

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...

# Run a single model if you want to spot-check
~/nightmare-benchmark/run_benchmark.sh gpt55

# Or all five
~/nightmare-benchmark/run_benchmark.sh
```

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

The five frontier-model extractions across three reasoning efforts (15
variants total) under
`examples/baseline_N1/N1_easy_70001/extractions/<model>/<doc_key>.json`
are side-by-side comparables.

## What's measured

Headline metric: **numeric hallucination rate** = fabricated numbers /
numbers emitted, where "fabricated" means the value does not appear in
the expanded per-packet universe (packet GT + generator source-of-truth
JSON + rendered PDF/XLSX text via pdftotext, with OCR fallback for
image-only scans). A second pass (`alias_audit.py`) double-checks each
flagged value by token-level coverage against that universe; only values
that fail both passes are counted.

Supplementary: string hallucination rate, per-category breakdowns, paired
per-doc sign tests, bootstrap CIs, recall-vs-fabrication Pareto, and
per-doc internal-consistency checks.

See [`report.md`](report.md) for the full results on the complete 5-packet run,
including exact API settings per model and per-model run counts
(including timeout exclusions).

## Methodology notes

A few choices worth calling out so reviewers don't have to reverse-engineer
them from the code:

**Composed-string acceptance.** For string values with five or more tokens,
`hallucination_analysis.py` (`string_in_universe`) accepts a value if 80%
or more of its tokens individually appear in the source universe. This
catches legitimate model concatenations like
`"LOC-001: Preston Center Tower, 8117 Preston Road, Dallas, TX 75225"`
where every component is in the source but the combined form isn't. The
rule can admit a single fabricated token inside a long compound string.
The bias is conservative: it only under-counts the flagged model's
fabrication rate, never inflates it. Short values and two-token strings
require all tokens to match.

**Universe is model-agnostic.** The per-packet universe is built from
exactly three sources: packet ground truth, generator render-source JSON,
and rendered-document text (PDF via `pdftotext`, XLSX cells, CSV rows,
OCR fallback for image-layer-only scans). No model extractions ever feed
back into the universe, so one model's hallucinations cannot mask
another's.

**Token-cap audit.** All five models ran at `max_tokens = 32000` at
default effort (Gemini uncapped); the OpenAI and Anthropic models bump
to 64K-128K when reasoning is enabled, so the cap doesn't constrain
thinking budget. `scripts/token_cap_audit.py` reports per-doc total
tokens; on GPT-5.4 the max across 148 docs is ~15,700 tokens (about 49%
of the cap), with zero docs above 75% of cap. GPT-5.4 had ~49% headroom,
so truncation isn't explaining its fabrication rate.

**Reasoning effort and provider defaults.** The full run tested each
model at default, HIGH, and XHIGH effort. Default behavior is not
symmetric across providers: GPT-5.5, GPT-5.4, Opus 4.7, and Sonnet 4.6
default to thinking *off* (no reasoning parameter passed); Gemini 3.x
defaults to thinking *on* at HIGH and cannot be disabled per Google's
docs.
Because of this, Gemini is excluded from default-effort comparisons in
`report.md` and only appears in the matched HIGH/XHIGH tables. Sonnet
4.6 also has no `xhigh` API level - its "XHIGH" row runs at
`effort: "max"`, the Sonnet ceiling. Full per-model API settings are
in [`report.md`](report.md#configuration).

**Difficulty-level sample sizes.** Per-difficulty rates in the headline
tables reflect 25 (N1, N2), 30 (N3), 36 (N4), and 32 (N5) documents
respectively. Within-difficulty comparisons are paired across models.
Bootstrap 95% CIs on those rates are in [`results_aggregate/paired_stats.json`](results_aggregate/paired_stats.json)
under `difficulty_bootstrap`.

## Full test set

N2 through N5 are held back so the dataset stays uncontaminated. Email
tim@aginor.ai with which packets you want (N2 normal, N3 hard, N4 very
hard, N5 nightmare) and what you're testing. Default turnaround 2-3 days.

## Acknowledgements

Thanks to our reviewer (who wishes to remain anonymous) for pointing out
the thinking-default gap in the original version of the test. The
matched-effort framing (HIGH/XHIGH tables, with Gemini included) was
added in response.

Thanks to Apurv Gandhi at Reducto for catching ghost data in the Excel ground-truth files that were inflating the hallucination rates. The numbers in this repo reflect the cleaned data.
