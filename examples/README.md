# Examples

Public-release slice of the Nightmare test set, organized into three
categories that each serve a different purpose.

```
examples/
├── baseline_N1/          # Full N1 (easy) packet, the reproducibility slice
├── hallucinations/       # Two deep-dive anecdotes from the writeup
└── timeouts/             # Docs that reliably time out at high/xhigh effort
```

The remaining private material (N2 through N5 packets other than the
specific docs released here) stays in `packets/private/` per the release
policy; see the repo root README.

## baseline_N1/

The full N1_easy packet (lowest-difficulty tier) with source PDFs,
per-packet ground truth, and pre-run extractions from the five blog
models at all three reasoning efforts (default / HIGH / XHIGH = 15
variants × 25 docs = 375 extraction files). This is what
`run_benchmark.sh` and `scripts/score.py` target when reproducing the
public tier; paths in the repo-root `README.md` point here.

## hallucinations/

Two documents from the writeup's deep-dive anecdotes, released so
readers can manually verify the specific cases called out:

- `financial_statement_N4/`: the $95M revenue → $40.6M fabrication
- `acord_45_N5/`: the invented 9-row building schedule with fabricated
  location names

Each has `source/` (PDF + per-doc ground truth, plus OCR text where
relevant) and `extractions/` with raw unedited JSON from all five blog
models at all three reasoning efforts (15 files per case). Verification
commands live inline in the writeup.

## timeouts/

Seven documents that deterministically exceeded the 20-minute client
timeout when run at Anthropic/OpenAI HIGH or XHIGH reasoning effort,
despite extracting cleanly at default effort across all five models.
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
`extractions/` holds all 15 model×effort outputs. The timeouts themselves
are visible directly in those dirs as error-stub files: `sonnet_xhigh.json`
on every loss-run case plus `acord_127_N5` and `driver_schedule_N5`,
`sonnet_high.json` on `loss_run_N5`, and `gpt54_xhigh.json` on
`loss_run_N5` and `driver_schedule_N5`. Default-effort runs all
succeeded across every case.

Pattern: every timeout is a long scan-heavy loss-run or driver-schedule
doc from N4/N5, plus one ACORD 127 from N5. At default effort these
extract in under a minute; at XHIGH the same docs run past 20 minutes
and get dropped.

