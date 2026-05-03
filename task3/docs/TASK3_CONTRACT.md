# Task 3 Contract — Search, Triage, PDF, PRISMA
**Author:** Dhruv Sood · **Date:** 2026-05-03 · **Repo:** Article_Finder/`task3/`

This contract is the spec the Task 3 implementation is bound to. The grader
should be able to read each section and run the listed test that proves it.

---

## Section 0 — Cardinal rules (rubric, non-negotiable)

1. **Every harvested reference lands in `article_references`.** No
   free-floating JSON. Free-floating outputs do not count for grading.
2. **Never download a PDF to decide relevance.** PDF cascade runs only after
   `triage_decision='ACCEPT'`.
3. **PRISMA counts come from a single SQL `GROUP BY` over
   `article_references`.** No parallel state.
4. **`SERPAPI_API_KEY` is read from the environment only.** Never logged,
   never committed. `.gitignore` blocks `.env`, `serpapi.key`,
   `policy_clearance.json`.
5. **scidownl is gated by 4 conditions.** All four must hold or no call
   happens.

---

## A. Search runner contract

| Section | Spec |
|---|---|
| **Inputs** | `query_results.json` (Task 2 output) — array of `{gap_id, framework_id, voi_score, ai_citation_query, boolean_query, …}` |
| **Processing** | For each query, dispatch to one of 4 backends (`serpapi`, `scholarly`, `paperscraper`, `mock`). SerpAPI uses `engine='google_scholar'`. paperscraper uses the AI Citation form (rubric §2 "preprint channel"). |
| **Outputs** | (1) Rows in `article_references` with full provenance. (2) `task3/data/search_results.json` summary dump. |
| **Success conditions** | (a) SerpAPI engine is `google_scholar`. (b) credit usage tracked in `run_log.notes`. (c) zero-result queries recorded (`run_log.notes.zero_results`). (d) DOI extraction tested on 3 sample URLs. (e) `discovered_via` set correctly: `serpapi_scholar`, `scholarly_search`, `paperscraper_search`, or `mock_synthetic`. |

---

## B. article_references contract (rubric §3A)

| Column | Rule |
|---|---|
| `reference_id` | format `REF-YYYY-MM-DD-NNNNNN`, unique |
| `doi` | normalised by `normalize_doi()` before insert |
| `title_normalized` | populated by `normalize_title()` (regex strip + lowercase) |
| `discovered_via` | comma-separated channel list (rubric §3B preserves multi-channel provenance) |
| `discovered_query`, `discovery_run_id` | every row carries the originating query and run id |
| `triage_stage` | starts at `'metadata_only'`; transitions logged to `lifecycle_transitions` |
| `voi_score` | inherited from the gap that produced the query |

**Dedupe-on-insert:** the helper `insert_or_dedupe()`:
1. normalises DOI
2. looks up by DOI; if hit, **UPDATE** the existing row's `discovered_via` instead of inserting (preserves provenance)
3. else falls back to `title_normalized` match for DOI-less rows
4. else inserts a new row

Verified by `tests_task2_task3.py::duplicate DOI updates provenance`.

---

## C. Abstract collector contract (rubric §4C)

| Section | Spec |
|---|---|
| **Inputs** | rows where `triage_stage='metadata_only'` AND `triage_decision IS NULL` (i.e. survivors of Stage 1) |
| **Processing** | Try in order: search-payload (snippet ≥120 chars), Semantic Scholar, CrossRef, PubMed, OpenAlex |
| **Outputs** | `abstract`, `abstract_source ∈ {search_payload, s2, crossref, pubmed, openalex, none}` |
| **Success** | abstract hit rate ≥ 70 % on rows that have a DOI; rate-limit ≥3.5 s sleep on free S2 tier (≤20 req/min); ambiguous title matches (≥2 candidates) NOT auto-accepted; all-source-empty rows tagged `triage_decision='MISSING_ABSTRACT'` immediately |

---

## D. Abstract triage contract (Stage 1 + Stage 2B)

**Stage 1 (metadata screen)** — runs at `triage_stage='metadata_only'` only:

- Reject if title contains ML jargon (regex set documented in code).
- Reject if `publication_year < min_year` (default 2005).
- Survivors keep `triage_stage='metadata_only'` and proceed to abstract collection.

**Stage 2B (decision)** — runs at `triage_stage='abstract_collected'`:

| Verdict | Rule |
|---|---|
| ACCEPT | `relevance.verdict='accept'` AND `voi_score ≥ voi_threshold` (default 0.50) |
| EDGE_CASE | `relevance.verdict='accept'` AND `voi_score < voi_threshold`, **or** `relevance.verdict='edge_case'` |
| REJECT | `relevance.verdict='reject'` |
| MISSING_ABSTRACT | already set by collector — never re-scored |

Every triaged row gets a non-empty `triage_reason`. `triage_confidence` is
populated for ACCEPT/EDGE_CASE/REJECT but NOT for MISSING_ABSTRACT (verified test).

---

## E. PDF acquisition contract (Stage 3)

- Reads from `v_acquisition_queue` (= `WHERE triage_decision='ACCEPT' AND acquired_paper_id IS NULL`, ORDER BY voi_score DESC).
- Cascade: **Unpaywall → OpenAlex OA → scidownl**.
- Every attempt logs to `lifecycle_transitions` and increments `pdf_acquisition_attempts`.
- On success, sets `acquired_paper_id` and `triage_stage='acquired'`.
- **Never** processes EDGE_CASE / REJECT / MISSING_ABSTRACT rows (verified test).

### scidownl 4-condition gate (rubric §5B)

All four must hold:

1. `--enable-scidownl` flag passed at the CLI.
2. `policy_clearance.json` exists at the repo root (file is `.gitignore`d).
3. The row has a DOI.
4. Both Unpaywall and OpenAlex OA already failed for this `reference_id`.

Failure on any of these sets `pdf_acquisition_last_source='gated:<reason>'`
and logs an `outcome='gated'` transition. No network call to scidownl is
made.

---

## F. PRISMA dashboard contract (rubric §6)

- `prisma_dashboard.py` runs **one** SQL query against `article_references`
  (`PRISMA_SQL`); supplemental queries only count `lifecycle_transitions`
  dedup events and distinct-query counts (also via `article_references`).
- Counts surfaced: gaps_targeted, queries_executed, records_returned,
  removed_at_metadata, abstracts_collected, missing_abstract,
  screened_by_classifier, accept, edge_case, reject_topic, pdf_acquired,
  pdf_gated, dedup_provenance_merges, dedupe_skipped, included.
- Output `prisma_funnel.json` is the persisted state — survives page
  refresh.

---

## Success conditions (combined)

1. `python3 run_pipeline.py --backend mock` runs end-to-end without error.
2. `tests_task2_task3.py` reports **25/25 PASS**.
3. PRISMA `included == accept + edge_case`.
4. `lifecycle_transitions` has at least one row per `reference_id`.
5. `v_acquisition_queue` returns 0 rows when no ACCEPT exists; > 0 when ACCEPT exists.
6. `policy_clearance.json` is git-ignored AND its absence blocks every
   scidownl attempt.
7. SerpAPI key, if set, is read only via `os.environ.get("SERPAPI_API_KEY")`.

---

## Test checklist (rubric § 4 — "tests before build")

- [x] SerpAPI call uses `engine='google_scholar'` (search_runner.py:67)
- [x] `SERPAPI_API_KEY` read from env only (verified via grep test)
- [x] zero-result query is recorded (`run_log.notes`)
- [x] DOI regex extracts 3 sample URLs (test PASS)
- [x] duplicate DOI updates provenance instead of inserting (test PASS)
- [x] no abstract → MISSING_ABSTRACT (verified)
- [x] fallback chain tries S2 → CrossRef → PubMed → OpenAlex
- [x] every triage row has `triage_decision` and `triage_reason` (test PASS)
- [x] MISSING_ABSTRACT skips VOI scoring (test PASS)
- [x] ACCEPT appears in `v_acquisition_queue`, others do not (test PASS)
- [x] PDF acquisition refuses non-ACCEPT rows (test PASS)
- [x] scidownl cannot run unless all 4 policy conditions pass (test PASS)
- [x] dashboard counts match a separate manual GROUP BY (test PASS)
- [x] one paper traceable end-to-end (END_TO_END_TRACE.md)
