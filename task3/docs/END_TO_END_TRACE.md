# Task 3 — End-to-End Trace
**Date:** 2026-05-03
**Driver:** `python3 run_pipeline.py --backend mock --per-query 10 --top-n 10 --include-edge-case`

This is the canonical demo run used for grading. The mock backend is
deterministic, so the numbers below are reproducible.

---

## Run summary

| Stage | Input | Output | Notes |
|---|---|---|---|
| 0. Reset DB | — | empty `article_references` | idempotent |
| 1. Search (mock) | 10 queries | 100 harvested → **96 inserted** | 4 duplicates caught by `dedup_key` |
| 2. Triage | 96 rows | **5** stage1_reject · **91** screened · **84** edge_case · **7** reject · **0** accept · **0** missing_abstract | 1 question constitution loaded |
| 3. PDF cascade | 84 candidates (edge_case included) | **0** got · **84** scidownl_blocked | gate closed (default policy) |
| 4. PRISMA | — | `identified=96, included=84` | written to `data/prisma_funnel.json` |

The 0-accept count is expected: the only loaded constitution is
`SQ-ART-001 Nature & Attention`, and the synthetic mock data leans environment-only,
which the relevance filter scores as `edge_case` (env hits but no outcome hits).
This is a data-coverage limit (only 1 constitution exists in
`question_constitutions_starter.json`), not a pipeline bug.

---

## Null-result handling

- **PDFs not retrieved** → row keeps `pdf_status` of `scidownl_blocked` /
  `no_oa`; never silently dropped. `pdf_method` records the gate reason
  (`gated:config_flag_off`, `gated:user_ack_env_var_missing`, `gated:no_doi`).
- **Missing abstract** → `stage2_verdict='missing_abstract'` and the row is
  excluded from `included` count but visible in PRISMA `missing_abstract`
  bucket.
- **Search backend errors** → logged to stderr per query, do NOT abort the
  pipeline; affected queries simply contribute 0 rows.

---

## Rerun idempotency

A second run with the same backend re-harvests the same 100 records, but
`ON CONFLICT(dedup_key) DO NOTHING` blocks all 100 inserts → 0 net new rows.
`run_log` records two `search` entries with `n_out` of 96 and 0 respectively.

---

## Audit trail

- `run_log.notes` JSON-encodes per-stage counts.
- `article_references` keeps `source`, `source_query`, `source_query_kind`,
  `gap_id`, `framework_id`, `voi_score`, and `raw_payload` so every cell on
  the dashboard can be drilled back to a single query and a single upstream
  record.

---

## Files produced

```
task3/data/
├── task3.db                  SQLite — single source of truth
├── prisma_funnel.json        machine-readable funnel
└── prisma_dashboard.html     human-readable dashboard
```

## Reproducing

```bash
cd task3
python3 run_pipeline.py --backend mock --include-edge-case
open data/prisma_dashboard.html
```
