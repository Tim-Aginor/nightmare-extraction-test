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

- **Universe construction.** For each packet, the analyzer pools the packet GT plus every generator-side `document_truth_*.json`, `field_truth_*.json`, `manifest_*.json`, and `packet_truth.json` under `packets/{public,private}/<difficulty>/doc_<seed>/ground_truth/`. A pre-2026-05-11 audit caught the path resolver silently failing on the canonical layout, which had left tier-2 ingest as a no-op and inflated string rates by 4.5–7.9pp and numeric rates by 0.9–2.4pp per model. Numbers below are post-fix.

- **Packet-wide pooling.** Customer info (insured / producer / preparer / carrier) is shared across docs in a packet. The universe is pooled per-packet so a real value modeled in doc-A's GT but not doc-B's doesn't false-flag on doc-B. Trade-off: a fabrication on doc-A that happens to coincide with a real GT value on doc-B passes here. Mitigated by per-doc-type sub-key audits in `internal_consistency.py`.

- **ACORD enum aliasing.** ACORD 125/140/160/24/27/28/45 schemas hard-enum `construction` and `roof_type` to short ACORD-formal lists; SOV/engineering schemas leave them as free strings. OpenAI/Gemini strict-mode silently nulls off-enum values while Anthropic tool_use emits literals. `score.py` accepts the documented abbreviation/full-name mappings in either direction (e.g., `MNC` matches `Masonry Non-Combustible`) so the same building is scored the same way regardless of which schema it appears under.

- **Exact-match numeric scoring.** Both `score.py` and `hallucination_analysis.py` compare numbers by exact equality after `to_float()` normalization ("$1,500,000" → `1500000.0`). v0 carried an inherited ±1% relative tolerance with a 0.5 absolute floor for `|val|<50`; an audit caught it masking real model errors (cents-truncated $153,631 against $153,631.51, $24,344,800 against rendered $24,514,100, year off-by-one silently scored correct). Villify renders exact numeric values and ground truth mirrors them, so any post-normalization mismatch is model error — the band was hiding the exact failure mode the test exists to surface. Numeric hallucination rates moved up 2–8pp per cohort against the tolerance-era numbers.

- **Composite scoring.** `score.py` composite weighting redistributes pro-rata when a component returns None (e.g., no matched locations → no field comparisons available). This means the composite is averaged over present components per-doc; readers comparing composite_score across models should treat it as a supplementary measure. The headline numbers above (hallucination rates) do not use this composite.

- **Micro vs macro averaging.** Headline rates are micro-averaged: `total_hallucinated / total_checked` summed across the 148 docs of a cohort. Per-doc macro averages (mean of per-doc rates) are available in `paired_stats.json → difficulty_bootstrap` and within the per-doc score files; they tell a similar story but weight all docs equally regardless of how many numbers/strings the doc carries.

- **Single trial per (model, effort, doc).** No `seed` is passed on any provider path — the Anthropic API exposes no `seed` parameter as of 2026-05, and reasoning calls also require `temperature=1.0`, so all three providers are equally unseeded for symmetry. Point estimates would shift by ≤0.5pp on a fresh re-run; the bootstrap 95% CIs in `paired_stats.json → difficulty_bootstrap` are the conservative read on that residual noise.

- **Doc-level independence in the sign test.** The sign tests in `paired_stats.json` treat the 148 docs as independent. Customer info is pooled per-packet (insured/producer/preparer shared across the ~25-36 docs in a packet), so errors within a packet correlate slightly. The bootstrap CIs (resampled per-doc) are the right number to cite when within-packet correlation matters.

- **Determinism gate.** `scripts/determinism_test.py` runs the analyzer in four subprocesses with different `PYTHONHASHSEED` values and asserts byte-identical output. rc=0 is a hard pre-publish gate.
