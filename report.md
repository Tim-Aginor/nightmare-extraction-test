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
| GPT-5.5    | 148  | 5279            | 150          | 2.8% |
| GPT-5.4    | 148  | 4697            | 152          | 3.2% |
| Opus 4.7   | 148  | 5629            | 24           | 0.4% |
| Sonnet 4.6 | 148  | 5972            | 56           | 0.9% |

### By reasoning effort

GPT-5.4 is the only model whose numeric hallucination rate drops with thinking effort, and even at XHIGH it remains 3-4× the Anthropic/Google baseline. GPT-5.5 (released April 23, 2026) does not reproduce that gradient - its rate is essentially flat across effort levels and at HIGH/XHIGH actually exceeds GPT-5.4. Opus, Sonnet, and Gemini show essentially flat behavior across effort levels.

| Model          | Default | HIGH  | XHIGH |
|----------------|---------|-------|-------|
| GPT-5.5        | 2.8%    | 3.3%  | 2.9%  |
| GPT-5.4        | 3.2%    | 1.6%  | 2.1%* |
| Opus 4.7       | 0.4%    | 0.5%  | 0.6%  |
| Sonnet 4.6     | 0.9%    | 1.0%* | 0.9%* |
| Gemini 3.1 Pro | 0.5%    | 0.9%  | 0.5%  |

\* GPT-5.4 XHIGH: n=146 (excluded 2 timed-out docs)
\* Sonnet 4.6 HIGH: n=147 (excluded 1 timed-out doc)
\* Sonnet 4.6 XHIGH: n=141 (excluded 7 timed-out docs)

### By category / difficulty - Default effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|---------------------|------|---------|---------|----------|------------|
| Narrative           | 21   | 7.2%    | 5.4%    | 1.4%     | 0.4%       |
| ACORD Form          | 67   | 3.6%    | 4.9%    | 0.4%     | 1.1%       |
| Financial Statement | 10   | 4.8%    | 4.7%    | 0.0%     | 1.0%       |
| SOV                 | 10   | 4.9%    | 2.6%    | 0.8%     | 1.8%       |
| Loss Run            | 15   | 0.3%    | 1.5%    | 0.3%     | 0.6%       |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Dec Page            | 5    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|----------------|------|---------|---------|----------|------------|
| N1 (easy)      | 25   | 0.2%    | 0.2%    | 0.0%     | 0.0%       |
| N2 (normal)    | 25   | 0.0%    | 0.8%    | 0.1%     | 0.1%       |
| N3 (hard)      | 30   | 4.3%    | 3.7%    | 0.6%     | 1.4%       |
| N4 (expert)    | 36   | 5.6%    | 6.1%    | 0.8%     | 2.1%       |
| N5 (nightmare) | 32   | 1.9%    | 3.0%    | 0.3%     | 0.5%       |

### By category / difficulty - HIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| Narrative           | 21   | 12.3%   | 4.7%    | 1.3%     | 0.9%       | 1.6%           |
| ACORD Form          | 67   | 3.8%    | 1.9%    | 0.5%     | 1.3%       | 1.2%           |
| Financial Statement | 10   | 4.7%    | 2.1%    | 0.0%     | 3.4%       | 2.9%           |
| SOV                 | 10   | 5.2%    | 2.4%    | 0.7%     | 0.6%       | 1.2%           |
| Loss Run            | 15   | 0.6%    | 0.6%    | 0.6%     | 0.2%       | 0.4%           |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Dec Page            | 5    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 6.4%    | 6.5%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.5%    | 0.5%    | 0.0%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 0.0%    | 0.0%    | 0.1%     | 0.4%       | 0.0%           |
| N3 (hard)      | 30   | 4.8%    | 2.4%    | 0.4%     | 2.1%       | 0.9%           |
| N4 (expert)    | 36   | 6.7%    | 3.2%    | 1.1%     | 1.4%       | 1.2%           |
| N5 (nightmare) | 32   | 2.1%    | 1.2%    | 0.4%     | 0.4%       | 1.4%           |

### By category / difficulty - XHIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| Narrative           | 21   | 9.3%    | 6.7%    | 1.5%     | 0.9%       | 1.1%           |
| ACORD Form          | 67   | 3.3%    | 2.1%    | 0.5%     | 1.1%       | 0.7%           |
| Financial Statement | 10   | 4.7%    | 4.1%    | 0.0%     | 1.0%       | 0.5%           |
| SOV                 | 10   | 5.5%    | 4.5%    | 1.8%     | 0.9%       | 0.7%           |
| Loss Run            | 15   | 0.2%    | 0.2%    | 0.4%     | 0.0%       | 0.3%           |
| Driver Schedule     | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Dec Page            | 5    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Engineering Report  | 4    | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 2.9%    | 0.0%    | 5.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.2%    | 0.0%    | 0.3%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 0.1%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| N3 (hard)      | 30   | 3.8%    | 3.4%    | 0.7%     | 1.7%       | 0.9%           |
| N4 (expert)    | 36   | 5.7%    | 4.2%    | 1.2%     | 1.4%       | 0.8%           |
| N5 (nightmare) | 32   | 2.2%    | 1.2%    | 0.5%     | 0.6%       | 0.4%           |

## String hallucination (supplementary)

String hallucination is dominated by transcription-like errors on policy and license numbers (single-character OCR errors on identifiers like `BND-88364-6825`). All five models produce similar string-level error rates on adversarial renders; the meaningful model differences live in the numeric table above.

### Overall (default effort)

Gemini 3.1 Pro is excluded from default-effort tables - see the note at the top of the numeric section.

| Model      | Docs | Strings Checked | Hallucinated | Rate |
|------------|------|-----------------|--------------|------|
| GPT-5.5    | 148  | 5470            | 281          | 5.1% |
| GPT-5.4    | 148  | 4836            | 245          | 5.1% |
| Opus 4.7   | 148  | 5509            | 111          | 2.0% |
| Sonnet 4.6 | 148  | 5606            | 153          | 2.7% |

### By reasoning effort

String hallucination drops monotonically with thinking effort on GPT-5.4. GPT-5.5 does not reproduce that gradient - its rate barely moves across effort levels and starts higher than GPT-5.4 at every level. Opus, Sonnet, and Gemini remain roughly flat.

| Model          | Default | HIGH  | XHIGH |
|----------------|---------|-------|-------|
| GPT-5.5        | 5.1%    | 4.4%  | 4.3%  |
| GPT-5.4        | 5.1%    | 3.3%  | 2.1%* |
| Opus 4.7       | 2.0%    | 2.0%  | 2.7%  |
| Sonnet 4.6     | 2.7%    | 2.2%* | 2.3%* |
| Gemini 3.1 Pro | 1.1%    | 1.1%  | 0.9%  |

\* GPT-5.4 XHIGH: n=146 (excluded 2 timed-out docs)
\* Sonnet 4.6 HIGH: n=147 (excluded 1 timed-out doc)
\* Sonnet 4.6 XHIGH: n=141 (excluded 7 timed-out docs)

### By category / difficulty - Default effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|---------------------|------|---------|---------|----------|------------|
| ACORD Form          | 67   | 6.7%    | 7.4%    | 2.9%     | 3.8%       |
| Narrative           | 21   | 6.2%    | 6.3%    | 2.4%     | 3.0%       |
| Driver Schedule     | 4    | 2.0%    | 4.1%    | 1.5%     | 2.6%       |
| Loss Run            | 15   | 4.5%    | 3.7%    | 0.6%     | 0.9%       |
| SOV                 | 10   | 2.0%    | 3.0%    | 1.0%     | 2.0%       |
| Engineering Report  | 4    | 5.1%    | 1.6%    | 1.9%     | 0.8%       |
| Dec Page            | 5    | 1.1%    | 1.0%    | 2.0%     | 1.9%       |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 |
|----------------|------|---------|---------|----------|------------|
| N1 (easy)      | 25   | 0.0%    | 0.0%    | 0.0%     | 0.0%       |
| N2 (normal)    | 25   | 0.8%    | 0.8%    | 0.0%     | 0.0%       |
| N3 (hard)      | 30   | 7.1%    | 6.9%    | 1.8%     | 1.9%       |
| N4 (expert)    | 36   | 6.7%    | 6.3%    | 2.5%     | 4.5%       |
| N5 (nightmare) | 32   | 6.1%    | 6.5%    | 3.0%     | 3.5%       |

### By category / difficulty - HIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| ACORD Form          | 67   | 5.7%    | 3.4%    | 2.8%     | 3.3%       | 1.2%           |
| Narrative           | 21   | 5.3%    | 2.6%    | 2.9%     | 1.6%       | 2.5%           |
| Driver Schedule     | 4    | 2.1%    | 2.2%    | 1.7%     | 2.3%       | 1.5%           |
| Loss Run            | 15   | 3.5%    | 4.4%    | 0.9%     | 0.0%       | 0.7%           |
| SOV                 | 10   | 2.9%    | 1.7%    | 1.0%     | 1.3%       | 0.3%           |
| Engineering Report  | 4    | 1.8%    | 3.7%    | 0.0%     | 0.9%       | 0.0%           |
| Dec Page            | 5    | 1.2%    | 1.3%    | 1.5%     | 1.4%       | 1.4%           |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.0%    | 0.0%    | 0.2%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 0.5%    | 0.7%    | 0.0%     | 0.0%       | 0.0%           |
| N3 (hard)      | 30   | 6.5%    | 4.5%    | 1.5%     | 1.6%       | 1.2%           |
| N4 (expert)    | 36   | 5.8%    | 2.9%    | 1.5%     | 4.3%       | 0.6%           |
| N5 (nightmare) | 32   | 5.0%    | 5.2%    | 4.0%     | 2.3%       | 2.3%           |

### By category / difficulty - XHIGH effort

| Category            | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|---------------------|------|---------|---------|----------|------------|----------------|
| ACORD Form          | 67   | 5.1%    | 3.1%    | 3.5%     | 3.4%       | 0.9%           |
| Narrative           | 21   | 4.0%    | 2.5%    | 3.0%     | 1.7%       | 1.8%           |
| Driver Schedule     | 4    | 2.4%    | 0.6%    | 1.7%     | 0.0%       | 1.1%           |
| Loss Run            | 15   | 4.2%    | 0.3%    | 2.3%     | 0.0%       | 0.6%           |
| SOV                 | 10   | 2.3%    | 2.6%    | 0.6%     | 0.7%       | 0.7%           |
| Engineering Report  | 4    | 3.1%    | 5.6%    | 0.0%     | 0.9%       | 0.0%           |
| Dec Page            | 5    | 2.1%    | 1.8%    | 1.3%     | 1.6%       | 1.4%           |
| Financial Statement | 10   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |
| Workbook            | 12   | 0.0%    | 0.0%    | 0.0%     | 0.0%       | 0.0%           |

_By difficulty:_

| Difficulty     | Docs | GPT-5.5 | GPT-5.4 | Opus 4.7 | Sonnet 4.6 | Gemini 3.1 Pro |
|----------------|------|---------|---------|----------|------------|----------------|
| N1 (easy)      | 25   | 0.0%    | 0.2%    | 0.2%     | 0.0%       | 0.0%           |
| N2 (normal)    | 25   | 0.4%    | 0.7%    | 0.0%     | 0.0%       | 0.0%           |
| N3 (hard)      | 30   | 7.3%    | 3.8%    | 1.5%     | 2.1%       | 1.2%           |
| N4 (expert)    | 36   | 5.1%    | 3.4%    | 3.4%     | 4.3%       | 0.4%           |
| N5 (nightmare) | 32   | 4.8%    | 1.2%    | 4.4%     | 2.8%       | 1.8%           |
