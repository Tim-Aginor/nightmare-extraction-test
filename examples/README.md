# Examples

A curated slice of the Nightmare test set with raw extractions inline,
organized into three categories. The full corpus (all 5 packets, every
document, every per-model extraction) is in `packets/` and `results/`
alongside this directory; the slices here exist for readers who want a
self-contained view of specific cases without navigating the larger
release tree.

```
examples/
├── baseline_N1/          # Full N1 (easy) packet, the reproducibility slice
├── hallucinations/       # Two deep-dive anecdotes from the writeup
└── timeouts/             # Docs that reliably time out at high/xhigh effort
```

## baseline_N1/

The full N1_easy packet (lowest-difficulty tier) with source PDFs,
per-packet ground truth, and pre-run extractions from the five blog
models. This is what `run_benchmark.sh` and `scripts/score.py` target
when reproducing the public tier; paths in the repo-root `README.md`
point here.

## hallucinations/

Two documents from the writeup's deep-dive anecdotes, released so
readers can manually verify the specific cases called out:

- `financial_statement_N4/`: the $95M revenue → $40.6M fabrication
- `acord_45_N5/`: the invented 9-row building schedule with fabricated
  location names

Each has `source/` (PDF + per-doc ground truth, plus OCR text where
relevant) and `extractions/` with raw unedited JSON from every cohort
(5 models × 3 effort levels). Verification commands live inline in
the writeup.

## timeouts/

Seven documents that deterministically exceeded the 20-minute client
timeout when run at Anthropic/OpenAI HIGH or XHIGH reasoning effort,
despite extracting cleanly at default effort across all four models.
Released so readers can inspect the failure class directly.

```
timeouts/
├── acord_127_N5/
├── driver_schedule_N5/
├── loss_run_N4/
├── loss_run_csv_N5/
├── loss_run_excel_N4/
├── loss_run_excel_N5/
└── loss_run_N5/
```

Each subdir mirrors the layout of `hallucinations/`: `source/` holds
the PDF/XLSX/CSV the model received plus the per-doc ground truth;
`extractions/` holds the per-cohort outputs for every effort level.
The timeouts themselves are tracked in the per-cohort run summaries
under `../results/{sonnet_high,sonnet_xhigh,gpt54_xhigh}/` (adjacent to
this directory, not inside it).

Pattern: every timeout is a long scan-heavy loss-run or driver-schedule
doc from N4/N5, plus one ACORD 127 from N5. At default effort these
extract in under a minute; at XHIGH the same docs run past 20 minutes
and get dropped.

