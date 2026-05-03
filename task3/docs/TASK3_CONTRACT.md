# Task 3 Contract — Search, Triage, PDF, PRISMA
**Author:** Dhruv Sood
**Date:** 2026-05-03
**Repo:** Article_Finder · `task3/`

---

## 1. Inputs

| File | Source | Notes |
|---|---|---|
| `../query_results.json` | Task 2 Phase 3 | top-N gaps with paired AI Citation + Boolean queries |
| `atlas_shared/src/atlas_shared/data/question_constitutions_starter.json` | atlas_shared | question constitutions for relevance classifier |

---

## 2. Pipeline (one driver, one DB)

```
query_results.json
        │
        ▼
search_runner.py     ── inserts every harvested ref into article_references
        │              (dedupe-on-insert via `dedup_key` UNIQUE)
        ▼
abstract_triage.py   ── Stage 1 (metadata screen) → Stage 2A (abstract collect)
        │              → Stage 2B (atlas_shared classifier)
        ▼
pdf_acquirer.py      ── Unpaywall → S2 → publisher → scidownl (gated)
        │
        ▼
prisma_dashboard.py  ── single GROUP BY over article_references → JSON + HTML
```

Driver: `run_pipeline.py --backend {mock,serpapi,scholarly}` runs all stages
in order against a fresh DB.

---

## 3. Storage rule (non-negotiable)

**Every harvested reference must land as a row in `article_references`.**
No free-floating JSON, no skipping the table. The funnel is reconstructed only
from this table (see Section 5).

`dedup_key` = `doi:<doi>` if DOI present, else `title:<sha1(lower(title))[:16]>`.
Inserts use `ON CONFLICT(dedup_key) DO NOTHING` so re-running is idempotent.

---

## 4. scidownl policy gate (4 conditions, ALL required)

| Condition | Default | How to satisfy |
|---|---|---|
| `--enable-scidownl` CLI flag | off | pass the flag explicitly |
| `SCIDOWNL_USER_ACK=1` env var | unset | user must export it |
| DOI present on the row | varies | required for sci-hub lookup |
| Prior cascade exhausted | enforced | unpaywall + s2 + publisher all missed |

If any condition fails, the row gets `pdf_status='scidownl_blocked'` with the
specific reason recorded in `pdf_method` (e.g. `gated:config_flag_off`). No
network call to scidownl is made.

---

## 5. PRISMA funnel from one SQL GROUP BY

The dashboard uses exactly one statement:

```sql
SELECT COUNT(*) AS identified,
       SUM(CASE WHEN stage1_screen='reject_metadata' THEN 1 ELSE 0 END) AS removed_metadata,
       SUM(CASE WHEN stage1_screen='pass'            THEN 1 ELSE 0 END) AS screened,
       SUM(CASE WHEN stage2_verdict='missing_abstract' THEN 1 ELSE 0 END) AS missing_abstract,
       SUM(CASE WHEN stage2_verdict='reject'          THEN 1 ELSE 0 END) AS reject_topic,
       SUM(CASE WHEN stage2_verdict='edge_case'       THEN 1 ELSE 0 END) AS edge_case,
       SUM(CASE WHEN stage2_verdict='accept'          THEN 1 ELSE 0 END) AS accept,
       SUM(CASE WHEN pdf_status='got'                 THEN 1 ELSE 0 END) AS pdf_got,
       SUM(CASE WHEN pdf_status='scidownl_blocked'    THEN 1 ELSE 0 END) AS pdf_blocked,
       SUM(CASE WHEN pdf_status='no_oa'               THEN 1 ELSE 0 END) AS pdf_no_oa
FROM article_references
```

`included = accept + edge_case`.

---

## 6. Backends

| Backend | Auth | Used by | Cost |
|---|---|---|---|
| `mock`     | none | demo / CI | $0, deterministic, offline |
| `serpapi`  | `SERPAPI_API_KEY` env | real Google Scholar | $$ per call |
| `scholarly`| none | fallback | rate-limited |

The mock backend produces a 60/20/10/10 mix of empirical / theoretical / ML /
duplicates so dedupe + Stage 1 + Stage 2 all exercise meaningful branches.

---

## 7. Success Conditions

1. `python3 run_pipeline.py --backend mock` runs end-to-end without error.
2. Every harvested row appears in `article_references`.
3. `dedup_key` is UNIQUE; re-running inserts 0 new rows.
4. PRISMA `identified == removed_metadata + screened`.
5. PRISMA `screened == reject_topic + edge_case + accept + missing_abstract`.
6. PRISMA `included == accept + edge_case`.
7. With scidownl gate closed, no `pdf_status='got'` from the scidownl method.
8. `prisma_dashboard.html` and `prisma_funnel.json` written and parseable.

---

## 8. Test Checklist

- [x] Reset DB and re-run idempotent (commit dedupe rate stays > 0)
- [x] Stage 1 rejects every row whose title contains ML jargon
- [x] Stage 2 reject ≠ Stage 1 reject (no double-counting)
- [x] PRISMA `identified` equals row count of `article_references`
- [x] scidownl gate refuses with reason recorded in `pdf_method`
- [x] HTML dashboard renders without external assets (no JS framework)
