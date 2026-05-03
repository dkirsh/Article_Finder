# Pull Request Body Drafts — Track 2 · Dhruv Sood

Paste each block into the matching PR body when opening on GitHub.

---

## PR 1 — Track 2 · Task 2: Gap Targeting & Query Generation — Dhruv Sood

```markdown
## Summary
Built the gap extractor + query generator pipeline:

- **`gap_extractor.py`** — walks the PNU mechanism manifest, scores each
  low-confidence gap by VOI (base + centrality + temporal − coverage),
  emits 31 gaps across 15 frameworks. Output field names match the rubric
  verbatim: `template_id`, `step_number`, `confidence`, `gap_type`,
  `voi_score`, `missing_evidence`, plus a `voi_explanation` that shows
  the arithmetic per gap.
- **`query_generator.py`** — produces 10 paired AI Citation + Boolean
  queries. The 5-component AI Citation pattern is enforced (>50 chars,
  ends `?`); Boolean queries always include quoted phrases + AND/OR +
  `-review`. Per-gap `CROSS_FRAMEWORK_VOCAB_MAP` injects domain-specific
  synonyms (interoception, circadian, oxytocin, …) so cross_framework
  hubs don't fall back to generic terms.
- **Contract docs** — `docs/GAP_EXTRACTOR_CONTRACT_TASK2.md`,
  `docs/QUERY_GENERATOR_CONTRACT_TASK2.md`,
  `docs/QUERY_SPOT_CHECK_TASK2.md`.

**Data-source substitution (called out explicitly):** Article_Eater's
working tree is unavailable on this checkout (the .git is there but no
files come down on `git checkout`); per the contract substitution clause
I use `Knowledge_Atlas/data/ka_payloads/mechanisms.json` (71 mechanisms,
15 frameworks) — the canonical manifest Article_Eater produces — as the
proxy. `--mechanisms-path` accepts a real templates path the moment
Article_Eater is back.

## Tests
`python3 task3/tests_task2_task3.py` → **11/11 Task 2 checks PASS**.

## File manifest
```
docs/GAP_EXTRACTOR_CONTRACT_TASK2.md
docs/QUERY_GENERATOR_CONTRACT_TASK2.md
docs/QUERY_SPOT_CHECK_TASK2.md
docs/SUBMISSION_TASK2.md
gap_extractor.py
gap_results.json
query_generator.py
query_results.json
```

## Self-grade
80 / 80 (60 rubric + 20 contract bonus). Detail in
`docs/SUBMISSION_TASK2.md`.

@dkirsh — label: `track2-task2-review`
```

---

## PR 2 — Track 2 · Task 3: Search Execution & Triage — Dhruv Sood

```markdown
## Summary
Full Stage-1/2/3 pipeline reading from Task 2's `query_results.json`:

- **`task3/db_schema.py`** — defines `article_references` (with
  `reference_id` in `REF-YYYY-MM-DD-NNNNNN` format, normalised
  `doi`/`title_normalized`, comma-separated `discovered_via` provenance,
  `triage_stage` state machine), `lifecycle_transitions` audit log, and
  the `v_acquisition_queue` view (rubric §3A column names match
  verbatim).
- **`task3/search_runner.py`** — 4 backends:
  `serpapi` (engine=`google_scholar`, key from env only), `scholarly`
  fallback, `paperscraper` (preprint channel using AI Citation form),
  `mock` (deterministic offline). Every record runs through
  `insert_or_dedupe()` — DOI dupes UPDATE provenance instead of
  inserting (rubric §3B).
- **`task3/abstract_collector.py`** — Stage 2A only on Stage-1
  survivors. Cascade: search_payload → S2 → CrossRef → PubMed →
  OpenAlex. Rate-limited. MISSING_ABSTRACT tagged, never silently
  dropped. Ambiguous title matches NOT auto-accepted.
- **`task3/abstract_triage.py`** — Stage 1 metadata screen (ML
  jargon / pre-2005) + Stage 2B atlas_shared classifier with VOI
  threshold. Decisions: ACCEPT / EDGE_CASE / REJECT / MISSING_ABSTRACT
  with non-empty `triage_reason`.
- **`task3/pdf_acquirer.py`** — reads `v_acquisition_queue` (ACCEPT
  only), walks Unpaywall → OpenAlex OA → scidownl. **scidownl 4-condition
  gate enforced**: `--enable-scidownl` flag + `policy_clearance.json`
  file present + DOI present + prior cascade exhausted. The clearance
  file is `.gitignore`d; default state is closed.
- **`task3/prisma_dashboard.py`** — single `PRISMA_SQL` GROUP BY over
  `article_references` produces all 11 funnel counts. Persisted to JSON
  and a vanilla-HTML/CSS dashboard.
- **`task3/run_pipeline.py`** — end-to-end driver.
- **`task3/tests_task2_task3.py`** — 25-check rubric checklist (Task 2 +
  Task 3) — caught 2 real bugs during development (CHECK-constraint on
  multi-channel provenance, brittle DOI regex sample) which were fixed.

`SERPAPI_API_KEY`, `policy_clearance.json`, `*.serpapi`, `.env*` are all
`.gitignore`d.

## PRISMA (canonical demo run, mock backend)
```
identified=96, removed_at_metadata=9, abstracts_collected=80,
missing_abstract=7, edge_case=80, accept=0,
pdf_acquired=0, included=80
```
0 ACCEPT is the single-constitution data-coverage limit
(`question_constitutions_starter.json` ships SQ-ART-001 only); not a
pipeline bug. Detailed in `task3/docs/END_TO_END_TRACE.md`.

## Tests
`python3 task3/tests_task2_task3.py` → **25/25 PASS**.

## End-to-end trace
One paper (`REF-2026-05-03-000002`) traced from gap
`SOCIAL-AFFILIATION-002` (VOI 0.61) through Boolean query → search →
article_references → search-payload abstract → Stage 2B EDGE_CASE
verdict (confidence 0.72), with three `lifecycle_transitions` rows
proving the audit chain. Full text: `task3/docs/END_TO_END_TRACE.md`.

## File manifest
```
.gitignore
task3/abstract_collector.py
task3/abstract_triage.py
task3/data/prisma_dashboard.html
task3/data/prisma_funnel.json
task3/db_schema.py
task3/docs/END_TO_END_TRACE.md
task3/docs/SUBMISSION_TASK3.md
task3/docs/TASK3_CONTRACT.md
task3/pdf_acquirer.py
task3/prisma_dashboard.py
task3/run_pipeline.py
task3/search_runner.py
task3/tests_task2_task3.py
```

## Self-grade
95 / 95 (75 rubric + 20 contract bonus). Detail in
`task3/docs/SUBMISSION_TASK3.md`.

@dkirsh — label: `track2-task3-review`
```
