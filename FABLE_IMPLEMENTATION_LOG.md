# Fable implementation log — Article_Finder_v3_2_3 (2026-08-07)

Read-only-verified then implemented by Fable (COWORK) under David's authorization to implement in unowned repos.
**Not committed** — review with `git diff` and commit when ready. Every change is surgical, syntax-checked, and
tested where noted. Findings tie to the repo goal: a *defensible, complete* corpus handed cleanly to Article_Eater.

## Implemented (verified)
1. **F5 — whole-corpus re-score every run** · `search/discovery_orchestrator.py:337`
   `not p.get('taxonomy_scores')` (a key that exists nowhere) → `p.get('triage_score') is None` (matches
   `triage/scorer.py:190`). Effect: the classify phase now scores only unscored papers, not all 10k each run.
2. **F1 — expansion promotion silently inserted 0 papers** · `search/discovery_orchestrator.py:414-419`
   The promotion dict wrote `discovery_metadata` (not a `papers` column → dynamic INSERT raised, caught as
   `items_failed`) and `triage_decision:'needs_review'` (deprecated per AF_TRIAGE_AND_SCORING_AUTHORITY).
   Fixed: provenance moved into the real, auto-serialized `tags` JSON array (`discovered_from:…`,
   `discovery_type:…`, `relevance_score:…`); vocab → `'review'`. Effect: bounded-expansion discoveries now
   actually enter the corpus, with their discovery provenance preserved.
3. **F2 — ingestion hot-path crashes if the AE repo is absent/renamed** · `core/ae_corpus_dedupe.py`
   `build_paper_dedupe_fields` runs on every `add_paper`; the three AE-DB readers did bare
   `sqlite3.connect()` + SELECT with no guard — a missing path *created an empty decoy DB* and the SELECT then
   raised, failing ALL ingestion. Added `_connect_ro()` (SQLite `mode=ro` URI: never creates a file; returns
   None if absent), wrapped all three readers in try/except→empty, and made the AE repo path env-configurable
   (`AF_AE_REPO`). Effect: a missing/renamed/schema-drifted AE degrades to dedupe status `unmatched` and
   ingestion proceeds. Verified: missing repo, empty/no-table DB, and nonexistent path all safe; no decoy created.
4. **F3 (scorer path) — protected venues were auto-rejected; no PRISMA reason** · new `triage/protection.py`
   + `triage/scorer.py:116`. The HBE/neuroscience allowlists + high-citation floor lived only in
   `scripts/production_run.py`, so the interactive `classify`/`discover` path could auto-reject a protected
   venue (violates AGENTS.md / PRODUCTION_RUN.md "never auto-reject"). New defensive shared guard
   (`venue_protected_reasons`, repo-root-relative paths, missing file = no protection = no crash); scorer now
   downgrades a `reject`→`review` for a protected venue and records `protected:<reasons>` in `triage_reasons`.
   Verified against real allowlist entries (268 HBE / 23 neuro), the `\bbrain`/`\bneuro` regex, unknowns, and None.

## D4-2 — AF-F6 merge-upsert (AUTHORIZED, controls passed) — 2026-08-07
`core/database.py::add_paper` — replaced destructive `INSERT OR REPLACE` with a **sparse merge-upsert**
(`INSERT ... ON CONFLICT(paper_id) DO UPDATE SET <provided cols only>`; new id → plain INSERT). On an existing
paper_id it updates only the columns present in the dict and never NULLs the rest. **Controls (required by
review) — PASSED:** full insert → complete row; sparse reject-style re-add → abstract/venue/pdf_path PRESERVED,
status/triage UPDATED; rerun idempotent; no duplicate rows. sqlite 3.37.2 (UPSERT ok); `paper_id` is PK.
**This unblocks F3b** (a reject re-add can no longer clobber a fuller row) — F3b may be re-enabled on David's nod.

## Reverted (unsafe until dependency lands)
- **F3b (bibliographer PRISMA rejects)** — implemented then **REVERTED** 2026-08-07: persisting a reject via
  `add_paper()` rides the F6 `INSERT OR REPLACE` footgun (a sparse reject row clobbers an existing fuller row —
  confirmed: abstract/pdf_path wiped). Re-do only AFTER F6 merge-upsert lands, with idempotency + status-
  preservation tests. bibliographer.py is back to HEAD.

## Deferred to the canon ledger (higher risk / needs your call — NOT changed)
- **F4** `cli/main.py cmd_build_jobs` never persists `ae_job_path`/`ae_status` (the documented handoff forgets
  the handoff; the only writer `ingest/prepare_for_ae.py` is unwired). Plan filed.
- **F6** `core/database.py:428` blind `INSERT OR REPLACE` can wipe columns on sparse re-ingest — a core
  write-semantics change; too risky to alter unattended. Plan (merge-upsert) filed.
- **F7 SECURITY** `config/settings.yaml:15` committed Semantic Scholar API key — needs **rotation** (yours);
  gitignore-move alone doesn't un-leak git history. Flagged in ledger, not touched (avoids breaking config).
- **F8** version drift (VERSION 3.2.4 vs README 3.2.3 vs cli 3.2.2) — cosmetic; left to avoid touching release
  string parsing blindly.

## Files touched
- `search/discovery_orchestrator.py` (F5, F1)
- `core/ae_corpus_dedupe.py` (F2)
- `triage/scorer.py` (F3-scorer)
- `triage/protection.py` (NEW — shared reject-protection guard)
- `FABLE_IMPLEMENTATION_LOG.md` (this file)
