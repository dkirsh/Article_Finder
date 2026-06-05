# Lifecycle DB snapshot

The pipeline's working DB lives at `task3/data/pipeline_lifecycle_full.db`, but
`data/` is **gitignored**, so the live DB is not on GitHub. This folder is a
**tracked snapshot** so the database is available without running the pipeline.

## Files
- `pipeline_lifecycle_full.sql` — portable text dump (recommended; loads anywhere).
- `pipeline_lifecycle_full.db` — the same DB as a binary SQLite file.

`pdf_path` values here are **repo-relative** (e.g. `task3/data/pdfs/REF-RM-001.pdf`)
so they resolve on any checkout (the live DB stores absolute local paths).

## Load it
```bash
# from a text dump into a fresh DB:
sqlite3 lifecycle.db < task3/db_snapshot/pipeline_lifecycle_full.sql
# or just open the binary copy:
sqlite3 task3/db_snapshot/pipeline_lifecycle_full.db
```

## What's inside
- `article_references` (55) — one row per candidate: doi, title, abstract,
  `triage_decision` (ACCEPT/EDGE_CASE/REJECT/MISSING_ABSTRACT), `triage_stage`,
  `voi_score`, `discovered_via`, `acquired_paper_id`, `pdf_path`, `pdf_sha256`.
- `lifecycle_transitions` (148) — per-row stage history (the audit trail).
- `run_log` — per-stage run summaries. Views: `v_acquisition_queue` (ACCEPT awaiting PDF).
- The 4 acquired "room height & creativity" papers are `REF-RM-001..003` +
  `REF-10-3390-S21062193` (`triage_stage='acquired'`, real `pdf_sha256`).
  `discovered_via='claude_in_chrome'` marks the two retrieved via the browser-assisted
  path (publisher-blocked OA).

## Schema source / regenerate
The authoritative schema is `task3/db_schema.py` (the DB is created by `open_db()`).
To rebuild a fresh DB from scratch:
```bash
cd task3
python3 db_schema.py --reset                       # empty DB with the schema
python3 run_pipeline.py --backend mock             # populate (offline, deterministic)
# or:  python3 run_pipeline.py --backend mock --enable-network   # live abstracts + OA PDFs
```

## PDFs
The acquired PDF files (~20 MB total) live in `task3/data/pdfs/` (gitignored). The
open-access ones re-download via `pdf_acquirer.py --enable-network`; the
publisher-blocked ones via `browser_acquire.py` (see `docs/BROWSER_ACQUISITION.md`).
Happy to send the PDFs directly if useful.
