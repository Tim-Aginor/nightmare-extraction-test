# Nightmare Extraction Test - Hallucination Rates

Fabricated-value rates measured against the render-source universe (generator ground-truth JSONs + pdftotext + openpyxl cells + OCR fallback). A hallucination is an extracted value that doesn't match any value present in the source document or its render-time ground truth, after normalization.

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
| GPT-5.4        | 148     | 148  | 146   |
| Opus 4.7       | 148     | 148  | 148   |
| Sonnet 4.6     | 148     | 147  | 141   |
| Gemini 3.1 Pro | 148     | 148  | 148   |

All percentages compute against each model's actual run count. In the per-category and per-difficulty tables below, the "Docs" column is taken from the first model with data at that group (typically GPT-5.4) and does not reflect deeper exclusions for other models. Sonnet 4.6 at XHIGH in particular has rates computed over n=141, smaller than the Docs column suggests.

### Overall (default effort)

Gemini 3.1 Pro is excluded from default-effort tables - its API default is HIGH (no thinking-off mode), so a default-vs-default row would not be a matched comparison. It appears in the matched HIGH and XHIGH tables below.

| Model      | Docs | Numbers Checked | Hallucinated | Rate |
|------------|------|-----------------|--------------|------|
| GPT-5.5    | 148  | 5279            | 193          | 3.7% |
| GPT-5.4    | 148  | 4697            | 184          | 3.9% |
| Opus 4.7   | 148  | 5629            | 36           | 0.6% |
| Sonnet 4.6 | 148  | 5972            | 82           | 1.4% |

### By reasoning effort

GPT-5.4 is the only model whose numeric hallucination rate drops with thinking effort, and even at XHIGH it remains 3-4× the Anthropic/Google baseline. GPT-5.5 (released April 23, 2026) does not reproduce that gradient — its rate is essentially flat across effort levels and at HIGH/XHIGH actually exceeds GPT-5.4. Opus, Sonnet, and Gemini show essentially flat behavior across effort levels.

| Model          | Default | HIGH  | XHIGH |
|----------------|---------|-------|-------|
| GPT-5.5        | 3.7%    | 4.2%  | 3.9%  |
| GPT-5.4        | 3.9%    | 2.5%  | 3.1%* |
| Opus 4.7       | 0.6%    | 0.7%  | 1.0%  |
| Sonnet 4.6     | 1.4%    | 1.5%* | 1.4%* |
| Gemini 3.1 Pro | 0.8%    | 1.2%  | 0.9%  |

\* GPT-5.4 XHIGH: n=146 (excluded 2 timed-out docs)
\* Sonnet 4.6 HIGH: n=147 (excluded 1 timed-out doc)
\* Sonnet 4.6 XHIGH: n=141 (excluded 7 timed-out docs)

### By category / difficulty - Default effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|---------------------|------|---------|---------|----------|------------|
| Narrative           | 21   | 8.9%    | 8.1%    | 1.9%     | 1.8%       |
| ACORD Form          | 67   | 4.9%    | 6.1%    | 0.9%     | 1.8%       |
| Financial Statement | 10   | 4.8%    | 4.7%    | 0.0%     | 1.0%       |
| SOV                 | 10   | 5.0%    | 2.8%    | 0.8%     | 2.0%       |
| Loss Run            | 15   | 0.8%    | 1.7%    | 0.2%     | 0.5%       |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Dec Page            | 5    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|----------------|------|---------|---------|----------|------------|
| N1 (easy)      | 25   | 0.2%    | 0.2%    | 0.0%     | 0.0%       |
| N2 (normal)    | 25   | 3.0%    | 2.4%    | 1.5%     | 1.9%       |
| N3 (hard)      | 30   | 4.9%    | 4.2%    | 0.7%     | 1.5%       |
| N4 (expert)    | 36   | 6.0%    | 6.5%    | 0.8%     | 2.3%       |
| N5 (nightmare) | 32   | 2.6%    | 3.8%    | 0.3%     | 0.9%       |

### By category / difficulty - HIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| Narrative           | 21   | 15.4%   | 5.8%    | 1.8%     | 1.4%       | 2.7%           |
| ACORD Form          | 67   | 5.3%    | 3.6%    | 0.9%     | 2.3%       | 2.1%           |
| Financial Statement | 10   | 4.7%    | 2.1%    | 0.0%     | 3.4%       | 2.9%           |
| SOV                 | 10   | 5.5%    | 2.4%    | 0.7%     | 0.7%       | 1.2%           |
| Loss Run            | 15   | 0.8%    | 0.8%    | 0.6%     | 0.0%       | 0.3%           |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Dec Page            | 5    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 6.4%    | 6.5%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.5%    | 0.5%    | 0.0%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 4.1%    | 3.0%    | 1.5%     | 2.2%       | 2.0%           |
| N3 (hard)      | 30   | 5.6%    | 3.6%    | 0.5%     | 2.7%       | 1.0%           |
| N4 (expert)    | 36   | 7.0%    | 3.3%    | 1.2%     | 1.6%       | 1.2%           |
| N5 (nightmare) | 32   | 2.6%    | 1.7%    | 0.4%     | 0.8%       | 1.5%           |

### By category / difficulty - XHIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| Narrative           | 21   | 11.3%   | 9.4%    | 2.0%     | 1.3%       | 2.1%           |
| ACORD Form          | 67   | 5.0%    | 3.9%    | 1.3%     | 2.0%       | 1.8%           |
| Financial Statement | 10   | 5.2%    | 4.6%    | 0.0%     | 1.0%       | 0.5%           |
| SOV                 | 10   | 6.3%    | 4.7%    | 2.0%     | 1.1%       | 0.8%           |
| Loss Run            | 15   | 0.3%    | 0.0%    | 0.2%     | 0.0%       | 0.2%           |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Dec Page            | 5    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 2.9%    | 0.0%    | 5.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.2%    | 0.0%    | 0.3%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 3.9%    | 4.0%    | 2.7%     | 1.7%       | 2.0%           |
| N3 (hard)      | 30   | 5.0%    | 3.9%    | 0.9%     | 2.2%       | 1.2%           |
| N4 (expert)    | 36   | 6.4%    | 4.8%    | 1.2%     | 1.6%       | 0.8%           |
| N5 (nightmare) | 32   | 2.7%    | 1.6%    | 0.5%     | 1.2%       | 0.6%           |

## String hallucination (supplementary)

String hallucination is dominated by transcription-like errors on policy and license numbers (single-character OCR errors on identifiers like `BND-88364-6825`). All five models produce similar string-level error rates on adversarial renders; the meaningful model differences live in the numeric table above.

### Overall (default effort)

Gemini 3.1 Pro is excluded from default-effort tables - see the note at the top of the numeric section.

| Model      | Docs | Strings Checked | Hallucinated | Rate |
|------------|------|-----------------|--------------|------|
| GPT-5.5    | 148  | 5470            | 385          | 7.0% |
| GPT-5.4    | 148  | 4836            | 332          | 6.9% |
| Opus 4.7   | 148  | 5509            | 186          | 3.4% |
| Sonnet 4.6 | 148  | 5606            | 242          | 4.3% |

### By reasoning effort

String hallucination drops monotonically with thinking effort on GPT-5.4. GPT-5.5 does not reproduce that gradient — its rate barely moves across effort levels and starts higher than GPT-5.4 at every level. Opus, Sonnet, and Gemini remain roughly flat.

| Model          | Default | HIGH  | XHIGH |
|----------------|---------|-------|-------|
| GPT-5.5        | 7.0%    | 6.3%  | 6.3%  |
| GPT-5.4        | 6.9%    | 4.7%  | 2.7%* |
| Opus 4.7       | 3.4%    | 3.0%  | 4.3%  |
| Sonnet 4.6     | 4.3%    | 3.9%* | 4.6%* |
| Gemini 3.1 Pro | 2.6%    | 2.1%  | 2.4%  |

\* GPT-5.4 XHIGH: n=146 (excluded 2 timed-out docs)
\* Sonnet 4.6 HIGH: n=147 (excluded 1 timed-out doc)
\* Sonnet 4.6 XHIGH: n=141 (excluded 7 timed-out docs)

### By category / difficulty - Default effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|---------------------|------|---------|---------|----------|------------|
| Driver Schedule     | 4    | 5.9%    | 9.8%    | 4.3%     | 5.1%       |
| ACORD Form          | 67   | 9.6%    | 9.6%    | 4.8%     | 5.9%       |
| Narrative           | 21   | 4.9%    | 6.7%    | 3.3%     | 4.5%       |
| Loss Run            | 15   | 4.8%    | 4.4%    | 0.6%     | 1.0%       |
| SOV                 | 10   | 2.3%    | 3.6%    | 1.3%     | 2.9%       |
| Engineering Report  | 4    | 8.5%    | 2.5%    | 3.8%     | 6.2%       |
| Dec Page            | 5    | 1.1%    | 1.6%    | 2.0%     | 1.9%       |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|----------------|------|---------|---------|----------|------------|
| N1 (easy)      | 25   | 1.0%    | 0.0%    | 0.0%     | 0.2%       |
| N2 (normal)    | 25   | 1.7%    | 1.0%    | 0.2%     | 0.2%       |
| N3 (hard)      | 30   | 8.0%    | 7.8%    | 2.8%     | 3.4%       |
| N4 (expert)    | 36   | 10.1%   | 8.8%    | 4.9%     | 7.2%       |
| N5 (nightmare) | 32   | 8.1%    | 9.8%    | 4.5%     | 5.1%       |

### By category / difficulty - HIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| Driver Schedule     | 4    | 2.5%    | 4.5%    | 2.6%     | 6.2%       | 3.4%           |
| ACORD Form          | 67   | 8.8%    | 5.1%    | 4.4%     | 5.4%       | 3.4%           |
| Narrative           | 21   | 4.3%    | 2.6%    | 2.9%     | 4.8%       | 2.5%           |
| Loss Run            | 15   | 3.9%    | 5.0%    | 0.9%     | 0.0%       | 0.7%           |
| SOV                 | 10   | 3.3%    | 2.7%    | 1.3%     | 2.0%       | 1.0%           |
| Engineering Report  | 4    | 8.3%    | 13.0%   | 2.7%     | 5.2%       | 1.0%           |
| Dec Page            | 5    | 2.1%    | 1.3%    | 1.5%     | 1.4%       | 1.4%           |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 1.0%    | 0.0%    | 0.2%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 1.7%    | 0.7%    | 0.3%     | 0.0%       | 0.0%           |
| N3 (hard)      | 30   | 8.9%    | 6.6%    | 2.7%     | 2.8%       | 2.2%           |
| N4 (expert)    | 36   | 7.5%    | 5.1%    | 2.1%     | 7.4%       | 2.2%           |
| N5 (nightmare) | 32   | 7.3%    | 6.8%    | 5.5%     | 4.3%       | 3.7%           |

### By category / difficulty - XHIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| Driver Schedule     | 4    | 3.9%    | 0.6%    | 3.9%     | 4.5%       | 4.0%           |
| ACORD Form          | 67   | 8.2%    | 4.3%    | 5.7%     | 6.0%       | 3.7%           |
| Narrative           | 21   | 3.1%    | 2.5%    | 4.3%     | 3.4%       | 3.2%           |
| Loss Run            | 15   | 4.6%    | 0.3%    | 2.5%     | 0.0%       | 0.7%           |
| SOV                 | 10   | 2.9%    | 3.3%    | 1.0%     | 0.7%       | 0.7%           |
| Engineering Report  | 4    | 13.3%   | 6.7%    | 7.2%     | 13.8%      | 3.1%           |
| Dec Page            | 5    | 2.1%    | 0.9%    | 1.8%     | 1.6%       | 1.4%           |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 1.0%    | 0.2%    | 0.2%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 1.8%    | 1.0%    | 1.0%     | 0.0%       | 0.0%           |
| N3 (hard)      | 30   | 9.1%    | 4.5%    | 3.7%     | 4.3%       | 2.0%           |
| N4 (expert)    | 36   | 8.1%    | 4.1%    | 4.2%     | 8.3%       | 2.6%           |
| N5 (nightmare) | 32   | 6.9%    | 2.1%    | 7.0%     | 5.8%       | 4.4%           |
