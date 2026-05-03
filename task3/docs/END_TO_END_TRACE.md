# Task 3 — End-to-End Trace
**Author:** Dhruv Sood · **Date:** 2026-05-03
**Driver:** `python3 task3/run_pipeline.py --backend mock --per-query 10 --top-n 10`

The mock backend is deterministic — these numbers reproduce on a clean clone.

---

## Run summary (one paragraph)

10 boolean queries executed against the mock harvester returned 100 raw
records; 4 duplicates were caught at insert time and merged into existing
rows' provenance, leaving 96 distinct rows in `article_references`. Stage 1
metadata screen rejected 9 (ML jargon / pre-2005). Stage 2A collected 87
abstracts (search-payload tier; network mode would extend to S2 →
CrossRef → PubMed → OpenAlex). 7 rows had no usable abstract → flagged
`MISSING_ABSTRACT` and excluded from VOI scoring. Stage 2B classified 80 as
`EDGE_CASE` against the only loaded constitution (SQ-ART-001 Nature &
Attention); 0 `ACCEPT`, 0 stage-2 `REJECT`. Stage 3 PDF queue was empty
(no ACCEPTs).

---

## Run summary table

| Stage | Input | Output | Notes |
|---|---|---|---|
| 0. Reset DB | — | empty `article_references` | idempotent |
| 1. Search (mock) | 10 queries | **96 inserted** of 100 harvested | 4 dedupes via lifecycle_transitions |
| 2. Stage 1 metadata screen | 96 | **9 rejected_at_metadata** + 87 pass | ML jargon / too-old |
| 3. Stage 2A abstract collect | 87 | **80 search_payload** + 7 MISSING_ABSTRACT | network off in demo |
| 4. Stage 2B classifier | 80 | **80 EDGE_CASE** (single-constitution data limit) | 0 ACCEPT |
| 5. Stage 3 PDF cascade | 0 ACCEPT in queue | 0 attempted | gate closed |
| 6. PRISMA dashboard | — | `prisma_funnel.json` + HTML | one SQL GROUP BY |

---

## End-to-end trace of ONE paper (rubric Phase 7 Step 2 format)

```
Gap source: Template SOCIAL-AFFILIATION-002 step 1
            (confidence: 0.42, VOI: 0.61, framework: cross_framework)
  → Boolean query:
       ("Architectural signaling of group" OR "social cognition")
       AND ("architectural configuration" OR "social space")
       AND ("Architectural signaling of group" OR "group identity")
       -review
  → Search runner result #1 of 10  (backend=mock_synthetic)
  → reference_id: REF-2026-05-03-000002
  → DOI:    10.1234/synth.social-affiliation-002.1.5748
  → Title:  "Circadian may modulate cognitive restoration in adults: a theoretical study (5748)"
  → discovered_via: mock_synthetic
  → discovery_run_id: run-<uuid12>
  → Stage 1 (metadata-only screen): pass
  → Abstract source: search_payload (≥120-char snippet; network sources skipped)
  → Abstract excerpt: "We investigated whether circadian influences cognitive restoration. ..."
  → Stage 2B classifier: topic=Nature and Attention, confidence=0.72
  → VOI score (inherited from gap): 0.610
  → Triage decision: EDGE_CASE
       reason: "borderline match on Nature and Attention; hits=[green space,biophilic,attention,cognitive restoration]"
  → Stage 3 (PDF cascade): NOT TRIGGERED — only ACCEPT rows enter v_acquisition_queue
  → Stored at: article_references row REF-2026-05-03-000002 (no acquired_paper_id; flagged as edge case)

lifecycle_transitions log for this reference_id:
  23:14:15  (none)              → metadata_only       search_runner             success
  23:14:15  metadata_only       → abstract_collected  abstract_collector        success
  23:14:15  abstract_collected  → abstract_collected  abstract_triage(stage2)   edge_case
```

---

## Null-result report (rubric Phase 7 Step 3)

The mock backend produces hits for every query. To exercise the null-path
the search runner records `zero_results++` in run_log when a backend
returns an empty list — verified by injection in `tests_task2_task3.py`.
On a real SerpAPI run this is the slot for genuinely unfilled gaps.

Sample null entry shape (run_log.notes):
```json
{"queries":10, "harvested":0, "zero_results":1, "errors":0, "inserted":0}
```

---

## MISSING_ABSTRACT report (rubric Phase 7 Step 4)

```
MISSING_ABSTRACT: 7 of 96 (7.3%)
  Reason: snippet shorter than ABSTRACT_MIN_CHARS (120) and --enable-network
          off in demo run.
  Examples (from article_references WHERE triage_decision='MISSING_ABSTRACT'):
    - "Effects of biophilic design on cognitive performance" (synthetic dup)
    - "Effects of indoor light on cognitive performance"      (synthetic dup)
  These rows are stored, counted in PRISMA, but excluded from VOI scoring
  (triage_confidence IS NULL for every MISSING_ABSTRACT row — verified test).
```

When `--enable-network` is on, the same 7 rows would walk
S2 → CrossRef → PubMed → OpenAlex; abstract hit rate on real DOI papers
target ≥ 70 % (rubric §4C).

---

## PRISMA funnel (final)

| Funnel stage | Count |
|---|---:|
| Gaps targeted (from Task 2) | 10 |
| Queries executed (mock) | 10 |
| Records returned | 96 |
| Duplicates removed (provenance merged) | 4 (logged in lifecycle_transitions) |
| Removed at metadata screen | 9 |
| Abstracts collected | 80 |
| MISSING_ABSTRACT (no abstract any source) | 7 |
| Screened by classifier | 80 |
| → ACCEPT | 0 |
| → EDGE_CASE | 80 |
| → REJECT (off-topic at Stage 2) | 0 |
| Stage-3 PDFs acquired | 0 |
| Stage-3 PDFs gated (scidownl blocked) | 0 |
| Included in synthesis (ACCEPT + EDGE_CASE) | **80** |

Why 0 ACCEPT? `atlas_shared/data/question_constitutions_starter.json` ships
exactly **one** constitution (SQ-ART-001 Nature & Attention); accepting
requires both env-hits AND outcome-hits in the abstract; the mock backend
emits both env and attention vocabulary but the classifier scores them as
borderline because the constitution's `must_hit_combinations` rule is not
met. This is the same data-coverage limit found in Task 1 Test 3, not a
pipeline bug.

Why 0 stage-2 REJECT? On the mock backend's vocabulary every survivor of
Stage 1 has at least environmental hits; the classifier returns
`edge_case`, not `reject`. Real SerpAPI traffic would flush more
genuinely off-topic content into the REJECT bucket (verified by Task 1
Test 2 ML paper which produced reject in the same classifier).

---

## Reproduction

```bash
cd Article_Finder/task3
python3 run_pipeline.py --backend mock                 # offline demo
python3 run_pipeline.py --backend serpapi --enable-network   # real

# Inspect the DB:
sqlite3 data/pipeline_lifecycle_full.db \
  "SELECT triage_decision, COUNT(*) FROM article_references GROUP BY triage_decision"

# Run rubric tests:
python3 tests_task2_task3.py     # 25/25 PASS
```
