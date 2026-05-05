# Aggregate Results - 148-document run

Cross-model aggregate outputs from the full 148-document run. These back
the aggregate tables in the blog post (https://www.aginor.ai/extraction-test/)
without releasing per-doc model extractions for the held-back packets
(N2-N5).

## Files

| File                          | What it contains                                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------------------------------- |
| `hallucination_report.json`   | Per-doc, per-model list of flagged fabricated values (numbers + strings). Source for the rate tables.     |
| `paired_stats.json`           | GPT-5.4 vs each comparator: per-doc sign test + bootstrap CIs on fabrication-count deltas.                |
| `scores.json`                 | Per-packet, per-category composite scores aggregate.                                                       |
| `alias_audit.json`            | Token-level coverage audit that filters flagged values against the expanded per-packet universe.          |
| `recall_vs_fabrication.json`  | Per-model extraction volume (strings-per-doc, numbers-per-doc) alongside fabrication rates.               |
| `internal_consistency.json`   | Per-doc internal-consistency checks (e.g. line items that should sum, totals that should match).          |

## How the blog-post tables are derived

- **Headline rates table** (numeric + string hallucination): derive from
  `hallucination_report.json` summed by model, divided by
  `totals.checked_numbers` / `totals.checked_strings` in
  `paired_stats.json`.
- **By-category / by-difficulty rate tables**: re-run
  `scripts/hallucination_analysis.py` grouping by the `category` /
  `difficulty` keys already in `hallucination_report.json`.
- **"Worse than all three on 23 docs"**: direct from
  `paired_stats.json → cross_model_agreement_total`.
- **Paired-comparison counts** (GPT-5.4 worse / better / tied per
  comparator): direct from `paired_stats.json →
  pairwise_total_fabs.<comparator>.{gpt54_more, gpt54_less, tied}`.
- **Fabrications per doc** (Table 3 bottom row): `totals.fab_total /
  n_docs_per_model` from `paired_stats.json`.
- **Gemini extraction-volume claims** (27.6 strings / 26.7 numbers per
  doc): `recall_vs_fabrication.json` per-model averages.

## What's NOT here (and why)

Per-document raw model extractions for N2-N5 stay private. They would
make contamination of the held-back difficulty ladder too easy. The two
deep-dive cases referenced in the writeup have full per-doc raw
extractions under `../examples/` for readers who want to verify those
specific claims. Research-use access to the full raw extractions is
available by email - see the top-level repo README.
