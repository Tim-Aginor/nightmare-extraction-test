# Nightmare Extraction Test - Hallucination Rates

Fabricated-value rates measured against the render-source universe (packet ground-truth + per-document generator artifacts: document_truth, field_truth, manifest, packet_truth JSON). A hallucination is an extracted value that doesn't match any value present in the source document or its render-time ground truth, after normalization.

## Configuration

Exact API settings per model. Thinking parameter names and defaults vary by provider.

| Model | API model ID | Default | HIGH | XHIGH |
|---|---|---|---|---|
| GPT-5.5 | `gpt-5.5` | no `reasoning_effort` (thinking off) | `reasoning_effort: "high"` | `reasoning_effort: "xhigh"` |
| GPT-5.4 | `gpt-5.4` | no `reasoning_effort` (thinking off) | `reasoning_effort: "high"` | `reasoning_effort: "xhigh"` |
| Opus 4.7 | `claude-opus-4-7` | no `thinking` param (thinking off) | `thinking: {type:"adaptive"}, output_config: {effort:"high"}` | `thinking: {type:"adaptive"}, output_config: {effort:"xhigh"}` |
| Sonnet 4.6 | `claude-sonnet-4-6` | no `thinking` param (thinking off) | `thinking: {type:"adaptive"}, output_config: {effort:"high"}` | `thinking: {type:"adaptive"}, output_config: {effort:"max"}` (Sonnet's API rejects `xhigh` with a 400; `max` is the Sonnet ceiling) |
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | `thinking_level` unset, defaults to HIGH per Google docs, cannot be disabled | `thinking_level: "HIGH"` | `thinking_budget: 32000` (Gemini has no native XHIGH level) |

**Default-behavior asymmetry to flag explicitly:**

- GPT-5.5, GPT-5.4, Opus 4.7, and Sonnet 4.6 default to thinking OFF when no reasoning parameter is passed. Anthropic's "adaptive" thinking mode is not the default; it requires explicit opt-in via `thinking: {type: "adaptive"}`.
- Gemini 3.x series defaults to thinking-on at HIGH and cannot be disabled. Per Google docs: "use dynamic thinking by default... defaults to high" and "Thinking cannot be turned off for Gemini 3 Pro and Gemini 3.1 Pro."
- Because of this, Gemini 3.1 Pro is excluded from default-effort tables below. The symmetric comparison is GPT/Claude at no-thinking vs each other; Gemini joins the matched HIGH and XHIGH tables.
- Sonnet 4.6's "XHIGH" row is run at `effort: "max"`, not `xhigh`. Sonnet's API does not accept `xhigh`. The label is retained for side-by-side comparison, but Sonnet at XHIGH is structurally capped at its provider's ceiling while GPT-5.4 and Opus 4.7 run at true `xhigh`.

## Numeric hallucination

Per-model run counts. Some docs deterministically time out at higher reasoning efforts even at a 1200s API timeout (Sonnet 4.6 on N4/N5 loss runs, GPT-5.4 on a handful of XHIGH cases).

| Model          | Default | HIGH | XHIGH |
|----------------|---------|------|-------|
| GPT-5.5        | 148     | 148  | 148   |
| GPT-5.4        | 148     | 148  | 148   |
| Opus 4.7       | 148     | 148  | 148   |
| Sonnet 4.6     | 148     | 147  | 144   |
| Gemini 3.1 Pro | 148     | 148  | 148   |

All percentages compute against each model's actual run count. In the per-category and per-difficulty tables below, the "Docs" column is taken from the first model with data at that group (typically GPT-5.4) and does not reflect deeper exclusions for other models. Sonnet 4.6 at XHIGH in particular has rates computed over n=144, smaller than the Docs column suggests.

The smallest per-category cells (Dec Page n=5, Driver Schedule n=4, Engineering Report n=4) carry too few numeric facts per cohort for single-cell model comparisons to be meaningful — a single hallucinated value can move the rate 1-3pp. Use the headline numbers and the per-difficulty tables (each n=25-36) for cross-model claims; the small-N category cells are kept for completeness. v2 fills these in as packet count grows.

### Overall (default effort)

Gemini 3.1 Pro is omitted from this default-only table because its API default is already HIGH (no thinking-off mode), so a default-vs-default row would not be a matched comparison. Gemini's effective-default cell *is* shown in the cross-effort pivot below for completeness, but it represents HIGH-effort behavior, not thinking-off.

| Model      | Docs | Numbers Checked | Hallucinated | Rate  |
|------------|------|-----------------|--------------|-------|
| GPT-5.5    | 148  | 4768            | 543          | 11.4% |
| GPT-5.4    | 148  | 4818            | 571          | 11.9% |
| Opus 4.7   | 148  | 5564            | 190          | 3.4%  |
| Sonnet 4.6 | 148  | 5906            | 309          | 5.2%  |

### By reasoning effort

GPT-5.4 is the only model whose numeric hallucination rate drops with thinking effort, and even at XHIGH it remains 3-4× the Anthropic/Google baseline. GPT-5.5 (released April 23, 2026) does not reproduce that gradient — its rate is essentially flat across effort levels and at HIGH/XHIGH actually exceeds GPT-5.4. Opus, Sonnet, and Gemini show essentially flat behavior across effort levels.

| Model          | Default | HIGH  | XHIGH |
|----------------|---------|-------|-------|
| GPT-5.5        | 11.4%   | 10.7% | 10.7% |
| GPT-5.4        | 11.9%   | 8.6%  | 8.8%  |
| Opus 4.7       | 3.4%    | 4.6%  | 4.2%  |
| Sonnet 4.6     | 5.2%    | 4.7%* | 3.1%* |
| Gemini 3.1 Pro | 3.2%    | 5.4%  | 4.0%  |

\* Sonnet 4.6 HIGH: n=147 (excluded 1 timed-out doc)
\* Sonnet 4.6 XHIGH: n=144 (excluded 4 timed-out docs)

### By category / difficulty - Default effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|---------------------|------|---------|---------|----------|------------|
| ACORD Form          | 67   | 17.4%   | 18.9%   | 1.8%     | 3.6%       |
| Narrative           | 21   | 15.9%   | 14.7%   | 5.2%     | 5.5%       |
| SOV                 | 10   | 13.3%   | 11.5%   | 2.7%     | 4.1%       |
| Financial Statement | 10   | 13.5%   | 10.9%   | 0.5%     | 5.0%       |
| Loss Run            | 15   | 2.7%    | 3.2%    | 9.1%     | 11.8%      |
| Dec Page            | 5    | 2.1%    | 1.4%    | 0.0%     | 0.0%       |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|----------------|------|---------|---------|----------|------------|
| N1 (easy)      | 25   | 0.7%    | 0.7%    | 0.3%     | 0.3%       |
| N2 (normal)    | 25   | 0.6%    | 2.3%    | 0.3%     | 0.3%       |
| N3 (hard)      | 30   | 17.4%   | 18.8%   | 2.0%     | 4.2%       |
| N4 (expert)    | 36   | 13.8%   | 13.8%   | 6.5%     | 9.7%       |
| N5 (nightmare) | 32   | 14.3%   | 14.3%   | 4.0%     | 6.4%       |

### By category / difficulty - HIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| ACORD Form          | 67   | 16.1%   | 14.0%   | 1.7%     | 4.1%       | 3.6%           |
| Narrative           | 21   | 14.8%   | 11.3%   | 5.1%     | 5.4%       | 1.9%           |
| SOV                 | 10   | 13.1%   | 2.7%    | 2.5%     | 1.7%       | 4.4%           |
| Financial Statement | 10   | 10.4%   | 9.7%    | 0.5%     | 8.3%       | 3.9%           |
| Loss Run            | 15   | 3.6%    | 4.9%    | 14.3%    | 8.6%       | 11.6%          |
| Dec Page            | 5    | 2.0%    | 4.4%    | 0.0%     | 0.0%       | 0.0%           |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.2%    | 0.2%    | 0.3%     | 0.3%       | 0.2%           |
| N2 (normal)    | 25   | 0.5%    | 0.5%    | 0.3%     | 0.9%       | 0.5%           |
| N3 (hard)      | 30   | 14.6%   | 7.7%    | 1.6%     | 5.2%       | 3.4%           |
| N4 (expert)    | 36   | 13.5%   | 14.2%   | 9.2%     | 9.0%       | 8.3%           |
| N5 (nightmare) | 32   | 14.3%   | 11.3%   | 5.9%     | 3.8%       | 8.2%           |

### By category / difficulty - XHIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| ACORD Form          | 67   | 15.9%   | 14.3%   | 1.9%     | 3.1%       | 3.7%           |
| Narrative           | 21   | 17.0%   | 13.2%   | 4.8%     | 6.2%       | 1.9%           |
| SOV                 | 10   | 12.8%   | 8.4%    | 4.0%     | 2.8%       | 4.4%           |
| Financial Statement | 10   | 14.2%   | 9.2%    | 2.5%     | 5.0%       | 0.0%           |
| Loss Run            | 15   | 3.5%    | 3.2%    | 11.3%    | 3.4%       | 6.6%           |
| Dec Page            | 5    | 2.1%    | 2.2%    | 0.0%     | 0.0%       | 1.8%           |
| Driver Schedule     | 4    | 0.0%    | 0.3%    | 0.0%     | 0.0%       | 0.0%           |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.2%    | 0.2%    | 0.3%     | 0.3%       | 0.2%           |
| N2 (normal)    | 25   | 0.5%    | 0.5%    | 0.1%     | 0.4%       | 0.2%           |
| N3 (hard)      | 30   | 14.2%   | 12.0%   | 2.6%     | 3.8%       | 3.2%           |
| N4 (expert)    | 36   | 14.5%   | 11.3%   | 7.0%     | 5.3%       | 2.7%           |
| N5 (nightmare) | 32   | 14.0%   | 12.4%   | 5.8%     | 2.8%       | 8.6%           |

## String hallucination (supplementary)

String hallucination is dominated by transcription-like errors on policy and license numbers (single-character OCR errors on identifiers like `BND-88364-6825`). All five models produce similar string-level error rates on adversarial renders; the meaningful model differences live in the numeric table above.

### Overall (default effort)

Gemini 3.1 Pro is omitted from this default-only table — see the note at the top of the numeric section.

| Model      | Docs | Strings Checked | Hallucinated | Rate |
|------------|------|-----------------|--------------|------|
| GPT-5.5    | 148  | 4731            | 276          | 5.8% |
| GPT-5.4    | 148  | 4858            | 288          | 5.9% |
| Opus 4.7   | 148  | 5427            | 133          | 2.5% |
| Sonnet 4.6 | 148  | 5503            | 172          | 3.1% |

### By reasoning effort

String hallucination drops monotonically with thinking effort on GPT-5.4. GPT-5.5 does not reproduce that gradient — its rate barely moves across effort levels and starts higher than GPT-5.4 at every level. Opus, Sonnet, and Gemini remain roughly flat.

| Model          | Default | HIGH  | XHIGH |
|----------------|---------|-------|-------|
| GPT-5.5        | 5.8%    | 6.7%  | 5.9%  |
| GPT-5.4        | 5.9%    | 4.5%  | 4.0%  |
| Opus 4.7       | 2.5%    | 2.5%  | 3.1%  |
| Sonnet 4.6     | 3.1%    | 3.0%* | 2.7%* |
| Gemini 3.1 Pro | 3.7%    | 3.6%  | 2.9%  |

\* Sonnet 4.6 HIGH: n=147 (excluded 1 timed-out doc)
\* Sonnet 4.6 XHIGH: n=144 (excluded 4 timed-out docs)

### By category / difficulty - Default effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|---------------------|------|---------|---------|----------|------------|
| ACORD Form          | 67   | 9.4%    | 11.1%   | 3.4%     | 4.2%       |
| SOV                 | 10   | 5.8%    | 6.7%    | 1.3%     | 2.9%       |
| Narrative           | 21   | 7.1%    | 3.1%    | 3.5%     | 5.1%       |
| Driver Schedule     | 4    | 2.4%    | 2.9%    | 1.9%     | 2.8%       |
| Engineering Report  | 4    | 4.5%    | 1.0%    | 3.8%     | 0.8%       |
| Dec Page            | 5    | 0.9%    | 0.3%    | 2.0%     | 1.9%       |
| Loss Run            | 15   | 1.6%    | 0.2%    | 0.6%     | 1.0%       |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|----------------|------|---------|---------|----------|------------|
| N1 (easy)      | 25   | 0.4%    | 0.3%    | 0.2%     | 0.2%       |
| N2 (normal)    | 25   | 0.6%    | 0.9%    | 0.3%     | 0.2%       |
| N3 (hard)      | 30   | 11.0%   | 9.3%    | 2.3%     | 2.2%       |
| N4 (expert)    | 36   | 6.8%    | 8.9%    | 3.1%     | 5.1%       |
| N5 (nightmare) | 32   | 5.4%    | 5.4%    | 3.3%     | 3.9%       |

### By category / difficulty - HIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| ACORD Form          | 67   | 10.3%   | 7.1%    | 3.4%     | 4.2%       | 5.8%           |
| SOV                 | 10   | 8.9%    | 4.8%    | 1.3%     | 2.0%       | 0.6%           |
| Narrative           | 21   | 5.6%    | 2.5%    | 4.3%     | 3.6%       | 0.0%           |
| Driver Schedule     | 4    | 2.4%    | 1.6%    | 1.9%     | 2.6%       | 1.3%           |
| Engineering Report  | 4    | 1.5%    | 3.3%    | 2.7%     | 9.6%       | 0.0%           |
| Dec Page            | 5    | 0.8%    | 0.0%    | 1.5%     | 1.4%       | 1.4%           |
| Loss Run            | 15   | 3.4%    | 2.3%    | 0.9%     | 0.0%       | 2.7%           |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.4%    | 0.4%    | 0.4%     | 0.2%       | 0.4%           |
| N2 (normal)    | 25   | 1.7%    | 1.2%    | 0.5%     | 1.0%       | 0.4%           |
| N3 (hard)      | 30   | 10.5%   | 7.7%    | 2.4%     | 2.7%       | 1.2%           |
| N4 (expert)    | 36   | 7.2%    | 5.7%    | 2.0%     | 5.2%       | 4.4%           |
| N5 (nightmare) | 32   | 7.5%    | 4.0%    | 4.3%     | 2.9%       | 6.0%           |

### By category / difficulty - XHIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| ACORD Form          | 67   | 10.0%   | 7.0%    | 3.8%     | 3.9%       | 4.4%           |
| SOV                 | 10   | 5.5%    | 3.5%    | 1.3%     | 1.0%       | 0.9%           |
| Narrative           | 21   | 2.5%    | 6.0%    | 3.8%     | 4.8%       | 0.0%           |
| Driver Schedule     | 4    | 4.5%    | 2.4%    | 1.9%     | 0.0%       | 1.9%           |
| Engineering Report  | 4    | 5.0%    | 4.5%    | 2.7%     | 3.7%       | 0.0%           |
| Dec Page            | 5    | 0.8%    | 0.0%    | 1.8%     | 1.6%       | 1.3%           |
| Loss Run            | 15   | 0.8%    | 0.3%    | 2.3%     | 0.0%       | 2.6%           |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.9%    | 0.4%    | 0.2%     | 0.0%       | 0.5%           |
| N2 (normal)    | 25   | 0.8%    | 2.0%    | 0.3%     | 0.3%       | 0.4%           |
| N3 (hard)      | 30   | 9.8%    | 7.5%    | 2.3%     | 3.0%       | 1.3%           |
| N4 (expert)    | 36   | 7.4%    | 4.6%    | 3.9%     | 3.8%       | 4.1%           |
| N5 (nightmare) | 32   | 5.7%    | 3.2%    | 4.5%     | 3.5%       | 4.4%           |

## Field-level error breakdown (recall view)

The headline hallucination rates above are **precision-side**: denominator = values the model emitted, so a model that returns `null` on hard fields gets a smaller denominator and looks better. This section flips to the **recall side**: denominator = GT-populated fields, and a `null` where GT has a value counts as an omission. Reading both together is the honest answer to "does the headline credit models for refusing to answer?"

**Empirically the omission rate is roughly constant across all models (~19-21% of GT-populated fields).** The cross-model spread lives in the wrong-value column, not the omitted column — i.e. models aren't gaming the headline by being selectively silent.

The ~20% omission floor is not a model defect on its own. The per-doc-type extraction prompts deliberately don't ask for every field that GT records (e.g., the SOV prompt asks for the SOV fields, not the producer's mailing address). Fields outside the prompt's scope show up here as omissions because the GT-side denominator covers everything generator-side, not just what we asked the model to extract. The *cross-model* delta is the interpretable signal; the floor is a property of the prompt design.

### Default effort

| Model      | GT fields | Correct | Wrong value | Omitted | Any error |
|------------|-----------|---------|-------------|---------|-----------|
| GPT-5.5    | 5632      | 73.6%   | 7.0%        | 19.4%   | 26.4%     |
| GPT-5.4    | 5710      | 71.9%   | 8.9%        | 19.2%   | 28.1%     |
| Opus 4.7   | 5898      | 71.9%   | 8.7%        | 19.4%   | 28.1%     |
| Sonnet 4.6 | 5866      | 70.8%   | 9.9%        | 19.3%   | 29.2%     |

### HIGH effort

| Model          | GT fields | Correct | Wrong value | Omitted | Any error |
|----------------|-----------|---------|-------------|---------|-----------|
| GPT-5.5        | 5674      | 74.0%   | 6.6%        | 19.4%   | 26.0%     |
| GPT-5.4        | 5611      | 73.5%   | 5.4%        | 21.1%   | 26.5%     |
| Opus 4.7       | 5878      | 72.3%   | 8.9%        | 18.8%   | 27.7%     |
| Sonnet 4.6     | 5671      | 72.4%   | 8.0%        | 19.6%   | 27.7%     |
| Gemini 3.1 Pro | 5875      | 75.8%   | 5.3%        | 19.0%   | 24.2%     |

### XHIGH effort

| Model          | GT fields | Correct | Wrong value | Omitted | Any error |
|----------------|-----------|---------|-------------|---------|-----------|
| GPT-5.5        | 5662      | 73.5%   | 7.3%        | 19.2%   | 26.6%     |
| GPT-5.4        | 5538      | 73.5%   | 5.6%        | 20.9%   | 26.5%     |
| Opus 4.7       | 5764      | 72.9%   | 7.4%        | 19.7%   | 27.1%     |
| Sonnet 4.6     | 4998      | 72.5%   | 5.5%        | 22.1%   | 27.6%     |
| Gemini 3.1 Pro | 5815      | 75.2%   | 5.4%        | 19.4%   | 24.8%     |

## Methodology notes

A few choices worth calling out so reviewers don't have to reverse-engineer them from the code.

- **Universe construction.** For each packet, the analyzer pools the packet GT plus every generator-side `document_truth_*.json`, `field_truth_*.json`, `manifest_*.json`, and `packet_truth.json` under `packets/<difficulty>/doc_<seed>/ground_truth/`. A pre-publish audit on 2026-05-11 caught the path resolver silently failing on the canonical layout — tier-2 ingest was a no-op for several days, which inflated string rates by 4.5–7.9pp and numeric rates by 0.9–2.4pp per model. The numbers in this report are post-fix.

- **Determinism gate.** `scripts/determinism_test.py` runs the analyzer in four subprocesses with different `PYTHONHASHSEED` values and asserts byte-identical output (SHA256 match across runs). rc=0 is a hard pre-publish gate.

- **Universe is model-agnostic.** Per-packet universes are built from two sources: packet ground truth, and the generator-side document/field/manifest/packet truth JSON emitted alongside each rendered doc. No model extractions ever feed back into the universe, so one model's hallucinations cannot mask another's. Live PDF/XLSX/OCR parsing was retired 2026-05-08 after a parallel-construction cross-check confirmed the JSON-only path matches the parsed-doc path on 89% of doc verdicts and within ≤0.06pp on aggregate numeric hallucination rates.

- **Packet-wide pooling.** Customer info (insured / producer / preparer / carrier) is shared across docs in a packet. The universe is pooled per-packet so a real value modeled in doc-A's GT but not doc-B's doesn't false-flag on doc-B. Trade-off: a hallucination on doc-A that happens to coincide with a real GT value on doc-B passes here. Mitigated by per-doc-type sub-key audits in `internal_consistency.py`.

- **Exact-match numeric scoring.** Both `score.py` and `hallucination_analysis.py` compare numbers by exact equality after `to_float()` normalization ("$1,500,000" → `1500000.0`). v0 carried an inherited ±1% relative tolerance with a 0.5 absolute floor for `|val|<50`; an audit caught it masking real model errors (cents-truncated $153,631 against $153,631.51, $24,344,800 against rendered $24,514,100, year off-by-one silently scored correct). Villify renders exact numeric values and ground truth mirrors them, so any post-normalization mismatch is model error — the band was hiding the exact failure mode the test exists to surface. Numeric hallucination rates moved up 2–8pp per cohort against the tolerance-era numbers.

- **Exact-token composed-string acceptance.** For multi-token string values, `hallucination_analysis.py` (`string_in_universe`) accepts only when EVERY token appears in the source universe. v0 used an 80%-of-tokens fuzzy rule that admitted a single hallucinated token inside a long compound string (e.g. `"9900 state road philadelphia pa 19136"` against a rendered `"8717 ..."`); audit on 2026-05-12 caught that admitting real errors, one-sided against the over-emitting (typically OpenAI) cohorts. Same failure mode as the dropped numeric tolerance. Legitimate concatenations like `"LOC-001: Preston Center Tower, 8117 Preston Road, Dallas, TX 75225"` still pass because every component IS in the source. String hallucination rates moved up 0.2 to 1.5pp per cohort (OpenAI side hit ~3x harder, matching the asymmetry the v0 rule was hiding).

- **ACORD enum aliasing.** ACORD 125/140/160/24/27/28/45 schemas hard-enum `construction` and `roof_type` to short ACORD-formal lists; SOV/engineering schemas leave them as free strings. OpenAI/Gemini strict-mode silently nulls off-enum values while Anthropic tool_use emits literals. `score.py` accepts the documented abbreviation/full-name mappings in either direction (e.g., `MNC` matches `Masonry Non-Combustible`) so the same building is scored the same way regardless of which schema it appears under.

- **Fields excluded from the precision-side universe check.** A fixed allowlist of leaf names is skipped in `hallucination_analysis.py: SKIP_LEAF_NAMES` (lines 408-428): schema enums whose value is constrained at the API level rather than drawn from document text (`coverage_type`, `entity_type`, `mvr_status`, `sex`, `license_state`, `priority`, `status`, `category`, `risk_level`, `insurability`, `period_type`, `statement_type`, `construction`, `occupancy`, ...); ACORD form metadata (`form_number`, `form_edition`, `form_title`); producer fields not modeled in GT; and free-text summary prose (`summary`, `description`, `notes`, `remarks`, `executive_summary`, `operations_description`, `safety_programs`, `claims_narrative`, `nature_of_business`, `loss_history_summary`). Either the value is constrained by strict-mode so universe-match is meaningless, or the field is summary prose that won't appear word-for-word in the source. Applied uniformly across all five cohorts. Recall-side scoring (`field_breakdown.json`) still catches wrong values on the strict-enum fields — they're omitted only from the precision-side hallucination universe, not from the broader correct/wrong/omitted accounting.

- **Composite scoring.** `score.py` composite weighting redistributes pro-rata when a component returns None (e.g., no matched locations → no field comparisons available). This means the composite is averaged over present components per-doc; readers comparing composite_score across models should treat it as a supplementary measure. The headline numbers above (hallucination rates) do not use this composite.

- **Anthropic tool_use envelope unwrap.** Anthropic's `tool_use` enforces JSON shape best-effort, not strictly. On a non-trivial fraction of documents Opus 4.7 wraps the schema payload in a single-key envelope — observed keys include `data`, `input`, `extract`, `document`, `extracted_data`, and more (an allowlist kept growing per run, so detection is by shape, not key name). `run_extraction.py` (lines 328-337) detects an envelope when the only top-level key is NOT a schema property AND the inner dict has ≥2 keys that ARE schema properties, and unwraps. OpenAI's strict mode and Gemini's structured output prevent the envelope from forming in the first place, so this fix-up fires only on the Anthropic path. Called out because it materially changes how many Anthropic responses parse cleanly into the expected shape; without it the Anthropic numbers would be inflated by parse failures rather than reflecting model behavior.

- **Anthropic tool_choice asymmetry under reasoning.** With reasoning off, the Anthropic call uses `tool_choice: {type: "tool", name: "extract"}` — the model is required to call the tool, which makes schema enforcement as strict as OpenAI/Gemini strict modes. With reasoning on, that combination is rejected by the API. Per [Anthropic's extended-thinking docs](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking): "Tool use with thinking only supports `tool_choice: {"type": "auto"}` ... Using `tool_choice: {"type": "any"}` or `tool_choice: {"type": "tool", "name": "..."}` will result in an error because these options force tool use, which is incompatible with extended thinking." Anthropic HIGH and XHIGH therefore run with `tool_choice: auto`. The schema is still attached and the model still calls the tool in practice, but enforcement is advisory rather than strict at HIGH/XHIGH. OpenAI and Gemini keep strict schema enforcement on under reasoning, so the strict-mode asymmetry exists only at HIGH/XHIGH on the Anthropic path.

- **Token-cap audit.** Default-mode output caps are 32K on OpenAI and Anthropic, 128K on Gemini — i.e. Gemini has 4× the default-mode headroom. Reasoning-mode caps are 128K on all three providers (matched). `scripts/token_cap_audit.py` reports per-doc total tokens; on GPT-5.4 the max across 148 docs is ~15,700 tokens (about 49% of the cap), with zero docs above 75% of cap. No completion approached its configured ceiling on v1, so the default-mode asymmetry didn't bite, but it's disclosed because we couldn't match it without subsidizing one provider.

- **Retry budgets.** On transient errors (429 / 5xx) OpenAI and Anthropic each run a 5-attempt outer loop (~90s exponential backoff, 60s cap) on top of the SDK's own retry layer (`max_retries=2` is the default for both providers' Python SDKs), so a single transient can be retried up to ~15 times before the outer loop gives up — same shape on both. Gemini's outer loop runs 7 attempts (~250s). The Gemini extra is in-code-justified by N1/N2 ACORDs hitting deterministic 503 "high demand" windows; without it Gemini would lose docs to vendor flakiness rather than capability. The outer-loop asymmetry (5 / 5 / 7) is a choice, not a wash. See [methodology](https://aginor.ai/extraction-test-methodology/#choices) for the full list of provider-side asymmetries.

- **Per-request timeouts.** OpenAI and Gemini use SDK defaults. Anthropic is set explicitly to 300s in default mode and 1200s under reasoning — Sonnet 4.6 on N4/N5 loss runs at high effort exceeds the SDK default deterministically. The 1200s ceiling covers the slowest observed cases; runs above it are reported as timeouts (the seven repeatable timeout docs: `loss_run` + `loss_run_excel` on N4; `loss_run` + `loss_run_excel` + `loss_run_csv` + `driver_schedule` + `acord_127` on N5). Provider-side asymmetry; called out because we couldn't match it without losing Anthropic reasoning runs to the client.

- **Reasoning effort and provider defaults.** The full run tested each model at default, HIGH, and XHIGH effort. Default behavior is not symmetric across providers: GPT-5.5, GPT-5.4, Opus 4.7, and Sonnet 4.6 default to thinking *off* (no reasoning parameter passed); Gemini 3.x defaults to thinking *on* at HIGH and cannot be disabled per Google's docs. The default-only tables above therefore exclude Gemini (it has no matching thinking-off mode), and the matched HIGH and XHIGH tables include all five. Sonnet 4.6 also has no `xhigh` API level — its "XHIGH" row runs at `effort: "max"`, the Sonnet ceiling. Full per-model API settings are in [Configuration](#configuration).

- **Micro- vs macro-averaging.** Headline rates are micro-averaged: `total_hallucinated / total_checked` summed across the 148 docs of a cohort. Per-doc macro averages (mean of per-doc rates) are available in `paired_stats.json → difficulty_bootstrap` and within the per-doc score files; they tell a similar story but weight all docs equally regardless of how many numbers/strings the doc carries.

- **Single trial per (model, effort, doc).** No `seed` is passed on any provider path — the Anthropic API exposes no `seed` parameter as of 2026-05, and reasoning calls also require `temperature=1.0`, so all three providers are equally unseeded for symmetry. Point estimates would shift by ≤0.5pp on a fresh re-run; the bootstrap 95% CIs in `paired_stats.json → difficulty_bootstrap` are the conservative read on that residual noise.

- **Doc-level independence in the sign test.** The sign tests in `paired_stats.json` treat the 148 docs as independent. Customer info is pooled per-packet (insured/producer/preparer shared across the ~25-36 docs in a packet), so errors within a packet correlate slightly. The bootstrap CIs (resampled per-doc) are the right number to cite when within-packet correlation matters.

- **Difficulty-level sample sizes.** Per-difficulty rates in the headline tables reflect 25 (N1, N2), 30 (N3), 36 (N4), and 32 (N5) documents respectively. Within-difficulty comparisons are paired across models. Bootstrap 95% CIs on those rates are in [`results_aggregate/paired_stats.json`](results_aggregate/paired_stats.json) under `difficulty_bootstrap`.

- **Category-level ranking is not monotone with the headline.** At default effort the loss-run category inverts the cross-model order: Opus 4.7 and Sonnet 4.6 hallucinate at 9.1% and 11.8% on loss-run numbers, vs 2.7% and 3.2% for GPT-5.5 and GPT-5.4 (full table above). The other six categories track the headline direction. Per-category cells run on n=4-15 docs at N=1 trial per (model, effort, doc), so single-cell model comparisons carry more Monte Carlo noise than headline or per-difficulty rates (n=25-36). Worth knowing about, but the headline and per-difficulty numbers are the load-bearing comparisons.
