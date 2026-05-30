# Track 2 — Article Finder Module: Box Specifications

Companion to `track2_module_sprints.mermaid`. Each box in the diagram is
specified below: purpose, inputs, outputs, the file that implements it, the
contract section it answers to, and the status vocabulary it writes. Organised
by sprint (= the three graded Track 2 tasks).

**Branch:** `track2/dhruv-sood` — see [BRANCH.md](BRANCH.md).
**One-command proof:** `python3 track2/Article_Finder/scripts/verify_track2_workflow.py`

---

## Sprint 1 — Task 1: Fix the Contribute Page  (repo: Knowledge_Atlas)

| Box | Purpose | Input | Output | File | Contract |
|---|---|---|---|---|---|
| Contribute UI | Capture a submission (PDF / citation / metadata), show honest per-item status | user form (file/citation/email) | multipart POST | `ka_contribute_public.html`, `ka_contribute.html` | §3 |
| `/api/articles/suggest` | Orchestrate validate → dedup → classify → store | multipart form | JSON `items[]` | `ka_article_endpoints.py` | §1, §2 |
| validate PDF | Reject non-PDF/oversize; hash | PDF bytes | `%PDF` ok + SHA-256, else `rejected_bad_file` | `ka_article_endpoints.py` | §2 Step 1 |
| dedup probe | Block anything already in corpus before storing | SHA / DOI / title | `duplicate` (+ pointer to existing id) or pass | `_check_duplicate()` (local substitute for `probe_pdf_against_article_eater`) | §0 (AE row), §2 Step 2 |
| classify + assess | Article type + question relevance; apply confidence floor | title + abstract + text | `verdict` + type + topic + confidence | `_run_classifier_and_assess()` → `AdaptiveClassifierSubsystem`, `QuestionArticleRelevanceFilter` | §2 Steps 4–6, **§6 (accept<0.55 → edge_case)** |
| store | Persist accepted/edge rows + audit | verdict + payload | `articles` row, quarantine PDF, `audit_log` | `ka_article_endpoints.py` | §3 |
| no-store | Return reason, write nothing | verdict | response only | `ka_article_endpoints.py` | §2 Step 6 |

**Status vocabulary (Task 1).**
- **Response `verdict`** ∈ `accept | edge_case | reject | duplicate | rejected_bad_file | needs_more_info`
- **Response `status`** ∈ `staged_pending_review | needs_more_info | rejected_not_stored`
- **DB `articles.status`** (stored rows only) = `staged_pending_review` *(the other response values mean "no row by design" — see contract §6 "Status semantics")*
- `needs_more_info` is surfaced in the UI with `next_action` + `evidence_stage`.

---

## Sprint 2 — Task 2: Gap Targeting & Query Generation  (repo: Article_Finder)

| Box | Purpose | Input | Output | File | Contract |
|---|---|---|---|---|---|
| gap_extractor | Find low-confidence knowledge gaps; score by Value of Information | mechanism manifest | ranked `gap_results.json` | `gap_extractor.py` | GAP_EXTRACTOR_CONTRACT_TASK2.md |
| query_generator | Turn each gap into an AI-Citation + Boolean query with quality flags | gaps | `query_results.json` | `query_generator.py` | QUERY_GENERATOR_CONTRACT_TASK2.md |

**Status vocabulary (Task 2).** `query_quality_flags` (closed enum):
`degenerate_dv, no_question_mark, too_short, no_synonyms, single_term_only, exceeds_length_limit, no_review_filter`.

---

## Sprint 3 — Task 3: Search → Triage → Acquire → Handoff  (repo: Article_Finder/task3)

| Box | Purpose | Input | Output | File | Contract |
|---|---|---|---|---|---|
| search_runner | Harvest candidates; every ref lands in the buffer | `query_results.json` | rows in `article_references` | `search_runner.py` | §A, §B |
| triage Stage 1 | Cheap metadata screen | metadata rows | `rejected_at_metadata` or pass | `abstract_triage.py` | §D |
| abstract_collector | Acquire abstract (S2→CrossRef→PubMed→OpenAlex); **gate** | survivors | `abstract` or `triage_decision=MISSING_ABSTRACT` | `abstract_collector.py` | §C, §0 (abstract-client row) |
| triage Stage 2B | Classifier decision | rows w/ abstract | `ACCEPT / EDGE_CASE / REJECT` | `abstract_triage.py` | §D |
| pdf_acquirer | Acquire PDF for ACCEPT only; scidownl gated | `v_acquisition_queue` | `acquired_paper_id`, `pdf_path` | `pdf_acquirer.py` | §E |
| prisma_dashboard | Funnel from a single GROUP BY | `article_references` | `prisma_funnel.json` (15 fields) | `prisma_dashboard.py` | §F |
| **ae_handoff (LAST MILE)** | Write the AE job bundle for handed-off papers | ACCEPT + abstract rows | `data/handoff/<reference_id>.json` + `handoff_log` row + `handed_off` txn | `ae_handoff.py` | **§0 (AE handoff row), §0.1 (schema)** |

**Status vocabulary (Task 3).**
- `triage_stage` ∈ `metadata_only | abstract_collected | rejected_at_metadata | acquired` (+ `handed_off` logged in `lifecycle_transitions`)
- `triage_decision` ∈ `ACCEPT | EDGE_CASE | REJECT | MISSING_ABSTRACT`
- `handoff_log.handoff_status` = `written`
- **Out of AF scope (AE-owned):** `article_eater_running | article_eater_complete | article_eater_failed`

**Handoff artefact (local schema, `data/handoff/<reference_id>.json`).** 14 fields:
`handoff_id, article_id, citation, title, doi, abstract, article_type, topic, subfocus_area, source_note, handoff_status, blocked_reason, created_at, updated_at`. The rubric names the path (`ka_track2_setup.html:101-102`) but enumerates no fields; this is AF's documented local schema. **Abstract is required** — a `MISSING_ABSTRACT` paper never yields a handoff file (the gate).

---

## Cross-cutting boxes

| Box | Purpose | File |
|---|---|---|
| `lifecycle_transitions` | Append-only audit of every stage change | `db_schema.py` (table) |
| `v_acquisition_queue` | View: ACCEPT rows with no PDF yet — the only rows PDF acquisition can see | `db_schema.py` |
| chain verifier | One command: runs both suites + asserts the last-mile handoff end-to-end (incl. AE consume) | `scripts/verify_track2_workflow.py` |
| AE inbox stub | Article Eater's intake side: reads + validates `data/handoff/*.json` (proves consumability) | `task3/ae_inbox_stub.py` |
| Task 1→3 bridge | Documented data seam: maps a Task-1 `articles` row to a Task-3 `article_references` candidate | `task3/contribute_bridge.py` |

## The Article Finder → Article Eater boundary

AF's deliverable to AE is the **handoff artefact** (`data/handoff/*.json`), nothing
more. `track2_hub.html:102`: *"AF's contract with AE is the job bundle and its
metadata, not the extraction result."* AE reads the artefact and runs its own
pipeline; those downstream states are AE-owned and intentionally outside this module.
