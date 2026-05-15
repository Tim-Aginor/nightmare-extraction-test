# Examples

Two deep-dive case studies from the writeup, included so readers can
manually verify the specific cases called out. The full corpus (all 5
packets, every document, every per-model extraction) ships in
`packets/` and `results/` alongside this directory. The slices here
give a self-contained view of these two cases without grepping the
larger release tree.

```
examples/
└── hallucinations/
    ├── financial_statement_N3/
    └── acord_45_N5/
```

## hallucinations/

- `financial_statement_N3/`: a $42M annual-revenue figure where
  GPT-5.5 and GPT-5.4 fabricate `net_revenue` at every reasoning
  effort ($35M-$46M range, different value at each effort level),
  while Opus 4.7, Sonnet 4.6, and Gemini 3.1 Pro all return the
  ground-truth $42M correctly across the board.
- `acord_45_N5/`: the invented 9-row building schedule with fabricated
  location names.

Each has `source/` (PDF plus per-doc ground truth, plus OCR text where
relevant) and `extractions/` with raw unedited JSON from every cohort
(5 models × 3 effort levels). Verification commands live inline in the
writeup.
