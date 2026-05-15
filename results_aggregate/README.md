# Aggregate Results - 148-document run

Cross-model aggregate outputs from the full 148-document run. These back
the aggregate tables in the blog post (https://www.aginor.ai/extraction-test/)
without releasing per-doc model extractions for the held-back packets
(N2-N5).

## Files

| File                          | What it contains                                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| `hallucination_report.json`   | Per-doc, per-model list of flagged hallucinated values (numbers + strings). Source for the rate tables.     |
| `paired_stats.json`           | All-pairs (10 pairs × 5 models) per-doc sign tests + bootstrap CIs on hallucination-count deltas, run separately at default / HIGH / XHIGH effort, with Holm-Bonferroni corrected p-values. |
| `<model>_scores.json`         | Per-packet, per-category composite scores for one cohort (15 files: 5 models × 3 effort levels). Each cohort's `aggregate` block also carries the per-field `correct/wrong/omitted` micro-counts that feed `field_breakdown.json`. |
| `field_breakdown.json`        | Recall-side error breakdown per cohort: GT-populated fields split into correct / wrong-value / omitted. Complements the precision-side hallucination rates with an answer to "does the headline credit models for refusing to answer?" |
| `alias_audit.json`            | Token-level coverage audit that filters flagged values against the expanded per-packet universe.          |
| `recall_vs_fabrication.json`  | Per-model extraction volume (strings-per-doc, numbers-per-doc) alongside hallucination rates.              |
| `internal_consistency.json`   | Per-doc internal-consistency checks (e.g. line items that should sum, totals that should match).          |

## How the blog-post tables are derived

- **Headline rates table** (numeric + string hallucination): each cohort
  has `aggregate.overall.number_hallucination_rate` and
  `string_hallucination_rate` in `hallucination_report.json` (top-level
  keys are the 15 cohorts: `gpt55`, `gpt55_high`, `gpt55_xhigh`,
  `gpt54`, ..., `gemini_pro_xhigh`).
- **By-category / by-difficulty rate tables**: under
  `aggregate.by_category` and `aggregate.by_difficulty` inside each
  cohort block of `hallucination_report.json`.
- **Paired-comparison counts** (model A worse / better / tied vs model
  B): under `paired_stats.json → <effort> → pairwise_total_fabs →
  <a>_vs_<b> → {a_more, a_less, tied, sign_test}`. Effort key is one of
  `default`, `high`, `xhigh`; pair keys cover all 10 model pairs. (The
  `pairwise_total_fabs` key name is the on-disk schema; the numbers it
  carries are hallucination counts.)
- **Per-model dominance counts** (docs where model A hallucinates more
  than every other model): `paired_stats.json → <effort> →
  dominance_total`.
- **Per-difficulty bootstrap CIs**: `paired_stats.json → <effort> →
  difficulty_bootstrap`.
- **Hallucinations per doc**: `totals.<model>.fab_total /
  n_docs_per_model.<model>` from `paired_stats.json`.
- **Per-model extraction-volume claims** (strings-per-doc,
  numbers-per-doc): `recall_vs_fabrication.json` per-model averages.
  (Default-effort only.)
- **Recall-side error breakdown** (correct / wrong-value / omitted per
  GT-field, per cohort): `field_breakdown.json → <cohort> → overall`.
  Available at all three effort levels.

## What's NOT here (and why)

Per-document raw model extractions for N2-N5 stay private alongside the
N2-N5 source PDFs. The two deep-dive cases referenced in the writeup have
full per-doc raw extractions under `../examples/` for readers who want
to verify those specific claims. Access to the full raw extractions is
available by email — see the top-level repo README.
