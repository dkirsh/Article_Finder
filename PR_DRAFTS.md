# Pull Request Body Drafts — Track 2 · Dhruv Sood

Paste each block into the matching PR body when opening on GitHub.
Both PRs go on the same `track2/dhruv-sood` branch in this repo.

---

## PR — Track 2 · Tasks 2 & 3: Gap Targeting + Search Triage — Dhruv Sood

```markdown
This PR completes Track 2 Tasks 2 and 3 on a single branch. Reviewers can
scope to commits per task:
- Task 2: 9c2b1d5, 15b8963, b80e9c9, de26708
- Task 3: 1a4e354, 82fe814, 4583241, ef75e08

## Task 2 — Gap Targeting & Query Generation

I built a gap extractor and query generator on top of the canonical PNU
mechanism manifest (Article_Eater is unavailable on this checkout —
`Article_Finder/docs/GAP_EXTRACTOR_CONTRACT_TASK2.md` §0 documents the
substitution).

Files added:
- `gap_extractor.py` extracts low-confidence mechanism steps and scores
  each by VOI (base + centrality + temporal − coverage).
- `query_generator.py` produces matched AI Citation + Boolean queries for
  the top-10 gaps. The mediator-fallback for single-noun-phrase
  mechanisms keeps every sentence grammatical.
- `gap_results.json` (31 gaps over 15 frameworks, sorted by VOI desc).
- `query_results.json` (10 paired queries with `query_quality_flags`,
  `query_terms`, `template_id`, `gap_summary`).
- Contracts in `docs/`:
  - `GAP_EXTRACTOR_CONTRACT_TASK2.md`
  - `QUERY_GENERATOR_CONTRACT_TASK2.md`
  - `QUERY_SPOT_CHECK_TASK2.md` — three queries actually run, top result
    titles recorded
  - `AI_QUERY_QUALITY_REVIEW_TASK2.md` — per-query Strong / OK / Weak
    verdicts (5 / 5 / 0)
  - `SUBMISSION_TASK2.md`

Manual spot-check (3/3 queries returned on-topic primary literature on
the first page):
| # | Gap | Top result |
|---|---|---|
| 1 | INTERO-PP-ALLOSTASIS-001 | "Allostatic interoceptive overload across psychiatric and neurological conditions" (*Biological Psychiatry*, 2024) |
| 2 | MULTISENSORY-CONGRUENCE-001 | "The multifaceted interplay between attention and multisensory integration" (PMC3306770) |
| 3 | CIRCADIAN-DEV-PROGRAM-001 | "Effects of light on human circadian rhythms, sleep and mood" (PMC6751071) |

## Task 3 — Search Execution & Triage

The Stage-1 / Stage-2 / Stage-3 pipeline reads `query_results.json` and
walks each candidate through the triage funnel. Every harvested ref
lands in `article_references`; PRISMA counts come from a single SQL
GROUP BY over that table.

Files added under `task3/`:
- `db_schema.py` — `article_references` (with `reference_id` in
  `REF-YYYY-MM-DD-NNNNNN` format, normalised DOI/title, comma-separated
  `discovered_via` provenance), `lifecycle_transitions` audit log,
  `v_acquisition_queue` view (rubric §3A column names verbatim).
- `search_runner.py` — 4 backends (`serpapi` engine `google_scholar`,
  `scholarly`, `paperscraper`, `mock`); `SERPAPI_API_KEY` from env only;
  insert-or-dedupe path that UPDATEs `discovered_via` instead of
  inserting on DOI hit.
- `abstract_collector.py` — Stage 2A on Stage-1 survivors only. Cascade:
  search_payload → S2 → CrossRef → PubMed → OpenAlex. Rate-limited.
  MISSING_ABSTRACT tagged.
- `abstract_triage.py` — Stage 1 metadata screen + Stage 2B classifier
  with VOI threshold. Verdicts ACCEPT / EDGE_CASE / REJECT /
  MISSING_ABSTRACT, every row gets a non-empty `triage_reason`.
  Emits `task3/data/triage_results.json`.
- `pdf_acquirer.py` — reads `v_acquisition_queue` (ACCEPT only); cascade
  Unpaywall → OpenAlex OA → scidownl. **scidownl 4-condition gate**:
  `--enable-scidownl` flag + `policy_clearance.json` file present + DOI
  + prior cascade exhausted. Default closed; clearance file
  `.gitignore`d.
- `prisma_dashboard.py` — single `PRISMA_SQL` GROUP BY → JSON +
  `prisma_dashboard.html` + `ka_topic_proposer.html`.
- `run_pipeline.py` — end-to-end driver.
- `tests_task2_task3.py` — 25-check rubric checklist.
- Contract in `task3/docs/TASK3_CONTRACT.md` (six sub-contracts A–F with
  §0 substitutions preamble).

### PRISMA funnel (canonical demo, mock backend, top-10 × per-10)

| Stage | Count |
|---|---:|
| Gaps targeted | 10 |
| Queries executed | 10 |
| Records returned | 91 |
| Duplicates removed (provenance merged) | 9 (in `lifecycle_transitions`) |
| Removed at metadata screen (Stage 1) | 9 |
| Abstracts collected | 77 |
| MISSING_ABSTRACT | 5 |
| Screened by classifier | 77 |
| → ACCEPT | 0 |
| → EDGE_CASE | 77 |
| → REJECT (Stage 2) | 0 |
| Stage-3 PDFs acquired | 0 |
| Included in synthesis | **77** |

Why 0 ACCEPT: `atlas_shared/data/question_constitutions_starter.json`
ships only `SQ-ART-001 Nature & Attention`; the mock data scores as
`edge_case` against that single constitution. Documented in
`task3/docs/END_TO_END_TRACE.md`.

### End-to-end trace

```
Gap source: SOCIAL-AFFILIATION-002 (confidence 0.42, VOI 0.61, framework cross_framework)
  → Boolean query:
       ("Architectural signaling of group" OR "social cognition")
       AND ("architectural configuration" OR "social space")
       AND ("Architectural signaling of group" OR "group identity")
       -review
  → Search runner result (backend=mock_synthetic)
  → reference_id: REF-2026-05-08-000002
  → DOI:    10.1234/synth.social-affiliation-002.1.7001
  → Title:  "Biophilic design modulates attention restoration in adults: a empirical study (7001)"
  → discovered_via: mock_synthetic
  → Stage 1 (metadata-only): pass
  → Abstract source: search_payload
  → Stage 2B classifier: topic=Nature and Attention, confidence=0.66
  → VOI score: 0.610
  → Triage decision: EDGE_CASE
       reason: "borderline match on Nature and Attention; hits=[green space,biophilic,attention]"
  → Stage 3 (PDF cascade): NOT TRIGGERED — only ACCEPT rows enter v_acquisition_queue

lifecycle_transitions log for this ref:
  21:27:34  (none)              → metadata_only       search_runner             success
  21:27:34  metadata_only       → abstract_collected  abstract_collector        success
  21:27:35  abstract_collected  → abstract_collected  abstract_triage(stage2)   edge_case
```

## Tests
`python3 task3/tests_task2_task3.py` → **25/25 PASS** (covers Task 2 + Task 3).

## Security / policy hygiene
- `SERPAPI_API_KEY` read from env only; not in repo, logs, or JSON.
- `.gitignore` blocks `.env*`, `*.serpapi`, `policy_clearance.json`,
  `task3/data/*.db`.
- scidownl gate closed by default; absent clearance file blocks every
  attempt and logs `outcome='gated'` in `lifecycle_transitions`.
- PDF cascade physically cannot reach REJECT / EDGE_CASE /
  MISSING_ABSTRACT rows — they are absent from `v_acquisition_queue`.

## Known limitations
- Article_Eater offline → using `mechanisms.json` proxy (substitution
  documented in contract §0).
- `pdf_corpus_inventory/latest.csv` not present on this checkout
  (lifecycle DB ships empty); `query_generator.py` reads it when
  available and skips honestly when absent.
- Single-constitution data limit in `atlas_shared` → 0 ACCEPT in mock
  demo (data, not code).

@dkirsh — labels: `track2-task2-review`, `track2-task3-review`
```

---

## Knowledge_Atlas PR — Track 2 · Task 1: Fix the Contribute Page — Dhruv Sood

(Body in `Knowledge_Atlas/PR_DRAFT_TASK1.md`; the PR is already open.)
