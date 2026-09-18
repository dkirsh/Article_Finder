# Article_Finder Currency Audit vs Live Article_Eater — 2026-09-08

*Produced by a read-only survey agent (CW session, 2026-09-08) at David Kirsh's request: what in AF is
still current, and what needs updating given parallel work in AE. Every claim below carries its file:line
evidence; the lifecycle DB was read read-only. Boundary of verification is stated in §(c).*

The short version: **AF's internal contracts are healthy and its 2026-08 state model is honest; what has
decayed is everything about the boundary.** AE stopped being a black box behind `article_eater eat` and
became a set of read-only reconciliation gates over shared SQLite — it froze the registry DB AF still
reads, forked AF's corpus into `article_finder_legacy.db` and mirrored it as `af_*` tables with a
1,126-row `af_identity_bridge` AF has never heard of, and published five AF-facing contracts AF doesn't
list. The highest-value single fix is STALE #1 + #2 together: retire `pipeline_registry_unified.db` from
`core/ae_corpus_dedupe.py:16` and reconcile `ae_corpus_match_paper_id` against `af_identity_bridge`,
because those two are now the same fact stored in two places with no arbiter.

---

## 1. AF spec inventory (docs/ + contracts/)

**`/Users/davidusa/REPOS/Article_Finder_v3_2_3/contracts/`** — the AE-facing governance layer:

| File | Date | Interface described |
|---|---|---|
| `AF_AE_HANDOFF_AUTHORITY_2026-05-10.md` | 2026-05-10 (+ FSM amendment 2026-08-07) | AF→AE job/output bundle handoff; `papers.ae_*` fields; `contracts/fsm/ae_handoff.fsm.json` |
| `AF_AE_RESULT_INGESTION_AUTHORITY_2026-05-10.md` | 2026-05-10 | AE result state vocabulary (`pending/SUCCESS/PARTIAL_SUCCESS/FAIL`) + `result.json` truthfulness |
| `AF_AE_CORPUS_DEDUPE_AUTHORITY_2026-05-10.md` | 2026-05-10 | AF dedupe against AE corpus; names the AE DBs/tables it reads |
| `AF_ARTIFACT_CATALOG_CONTRACT_2026-06-16.md` | 2026-06-16 | Artifact canonicality; paired with AE's `contracts/ARTIFACT_CATALOG_CONTRACT_2026-06-16.md` |
| `AF_PAPER_STATUS_AUTHORITY_2026-08-07.md` | 2026-08-07 | `papers.status` FSM; `rejected` outranks re-admission to `queued_for_eater` |
| `AF_PIPELINE / TRIAGE_AND_SCORING / SCHEMA_AND_MIGRATION / PDF_ATTACHMENT_INTEGRITY / QUARANTINE_AND_RECOVERY / SHARED_INTAKE_CLASSIFICATION / SYSTEM_HEALTH / WEEKLY_SYSTEM_HEALTH` | all 2026-05-10 | AF-internal; no AE dependency |
| `contracts/fsm/{ae_handoff,paper_status}.fsm.json`, `ports.json` | 2026-08-07 / — | executable declarations |

**`/Users/davidusa/REPOS/Article_Finder_v3_2_3/docs/`** — 21 markdown docs. AE-relevant:
`REPO_STATE_MODEL_AND_PLAN.md` (STATE_AS_OF 2026-08-05, JUDGED 2026-08-06 — newest and most accurate),
`PROJECT_GUIDE_FOR_HUMANS.md` (undated), the `TOPIC_ADMISSION_*` set +
`TOPIC_ADMISSION_TRANCHE_2_VALIDATION_2026-08-29.md` (newest doc in repo),
`TRACK2_CANDIDATE_DISCOVERY_INTEGRATION_2026-06-04.md`, `QUESTION_FILTER_WITH_AG_2026-04-07.md`.
Clearly aged: `SYSTEM_ARCHITECTURE_REVIEW_2026_01_25.md`, `CLAUDE_CODE_HANDOFF_v2.7.0.md` (Apr 2026),
`TOPIC_TRIAGE_CRITERIA_2026-02-11.md`, `TIGHT_ACCEPTANCE_REPORT_2026-02-14.md`,
`USER_GUIDE.md`/`EXPERT_PANEL_REVIEW.md` (marked v3.2.2).

## 2(a). CURRENT — verified still aligned

- **`data/article_eater_lifecycle.db` as the AE corpus surface.** `core/ae_corpus_dedupe.py:17` and
  `contracts/AF_AE_CORPUS_DEDUPE_AUTHORITY_2026-05-10.md:16-17`. DB exists (364 MB, mtime 2026-08-07);
  both named tables live: `paper_metadata` (332 rows), `paper_supersessions` (590). Matches AE `data/DB_REGISTRY.md:20`.
- **AE repo root path** resolved correctly in `core/ae_corpus_dedupe.py:15`, `ingest/ae_waiting_room_probe.py:19`,
  `triage/registry_sink.py:9`, `scripts/artifact_catalog.py:25`, `scripts/prevention/state_model_freshness_check.py:132`,
  `scripts/compare_topic_admission_20_gold.py:26`; `ae_corpus_dedupe` honours an env override.
- **Waiting-room probe** (`ingest/ae_waiting_room_probe.py:20,51` → AE `scripts/course_scaffolding.py`,
  subcommand registered at :68,138).
- **`triage/registry_sink.py:62`** imports AE `src/services/notify_registry.notify_registry` — module exists
  (2026-06-13), signature still accepts `classification_fact`. (Its DB targets are STALE #4.)
- **`PDF-nnnn` paper-ID convention** — still AE's live ID form.
- **`web_persistence_v7.db` mapping** in `scripts/artifact_catalog.py:36` — file exists (82 MB, 2026-08-05); still registered.
- **`AF_ARTIFACT_CATALOG_CONTRACT_2026-06-16.md`** — AE companion exists at stated path; LM-AF-2/3/4 hold
  (`data/article_finder.db` 541 MB live; superseded snapshot marked; root `articles.db` still 0 bytes).
- **`REPO_STATE_MODEL_AND_PLAN.md:48-54` "inbound uncontracted coupling"** — understated but true: ~29 AE
  `.py`/`.sh` files hardcode `/Users/davidusa/REPOS/Article_Finder_v3_2_3` (incl. `scripts/coordination/pdf_feeder.py`,
  `build_af_corpus_reconciliation_gate.py`, `run_af_download_suppression_apply.py`, `run_cross_repo_system_health_monitor.py`).
- **Handoff/result status vocabulary** — consistent with AE `contracts/ae_af/README.md:163-172`. No contradiction found.

## 2(b). STALE — AF references to AE artifacts that moved, froze, or were superseded

1. **`pipeline_registry_unified.db` is FROZEN — AF still reads it as a canonical dedupe surface.**
   `core/ae_corpus_dedupe.py:16`; `contracts/AF_AE_CORPUS_DEDUPE_AUTHORITY_2026-05-10.md:15`. AE
   `data/DB_REGISTRY.md:40-43` marks it frozen/legacy with a `DEPRECATED_DO_NOT_WRITE.md` marker
   (last written 2026-05-31). The dedupe surface should collapse to the lifecycle DB alone; the contract's
   rule 1 ("combined surface") no longer has a combined surface to refer to.
2. **AE absorbed AF's tables into the lifecycle DB; AF knows nothing about it.** Live lifecycle DB carries
   `af_papers` (16,257 rows), `af_facets`, `af_facet_nodes`, `af_node_centroids`, `af_paper_facet_scores`,
   `af_citations`, `af_expansion_queue`, `af_claims` (0), `af_rules` (0), `af_paper_embeddings`,
   `af_extracted_tables`, `af_schema_version`, and **`af_identity_bridge` (1,126 rows;
   af_paper_id / ae_paper_id / match_method / matched_at / note)**. `af_schema_version` annotated
   "L3 per David Q1-accept 2026-07-30; source=article_finder_legacy.db". Zero AF files mention any `af_*`
   table. **`ae_corpus_match_paper_id` and `af_identity_bridge` are two unreconciled answers to the same question.**
3. **AE no longer treats AF's repo as its system of record for discovery.** AE
   `contracts/ARTICLE_FINDER_CONTRACT_2026-06-05.md:13-16` declares AE-local `data/article_finder_legacy.db`
   (16,257 rows, read-only, 2026-07-30) the system of record, resolved via `db_locator.resolve_article_finder_db()`
   (AE `src/services/db_locator.py:464-470`, with adversarial tests). Nothing in AF records that AE forked a
   snapshot of AF's corpus; `docs/REPO_STATE_MODEL_AND_PLAN.md:39-54` and `docs/PROJECT_GUIDE_FOR_HUMANS.md:40`
   still describe a single live AF corpus AE consumes.
4. **`triage/registry_sink.py` defaults route writes into the deprecated DB.** `registry_sink.py:46-47`
   passes `registry_db=None` and AE `src/services/notify_registry.py:114` defaults `_REGISTRY_DB_DEFAULT`
   to the frozen `pipeline_registry_unified.db`. (Lifecycle half fine: :454 resolves via db_locator.)
5. **`knowledge/theory_search.py:17` inserts a nonexistent path** (`…/REPOS/article_eater`) into sys.path —
   dead since the repo rename; silent no-op.
6. **AF carries v1 claim/rule schemas; AE's cross-repo matrix asserts AF is on v2 "active / 100%".**
   AF has only `schemas/ae.*.v1.schema.json`; AE `contracts/cross_repo/version_matrix.json:26-49,189-204`
   records `ae.claim.v2`/`ae.rule.v2` as active for AF, and `contracts/ae_af/README.md:124-125,241-243`
   requires v2 validation of output bundles. One of the two is lying; `REPO_STATE_MODEL_AND_PLAN.md:52-53`
   flags it; unfixed.
7. **`article_eater` is not on PATH.** `config/settings.yaml:42-43`, `cli/main.py:59`, `ui/pages/3_triage.py:46`,
   `eater_interface/invoker.py:60,77` default to a bare executable; the binary lives at
   `/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery/bin/article_eater`. Consistent with real
   traffic having moved to the uncontracted door.
8. **`scripts/artifact_catalog.py:25` defaults `ARTIFACT_CATALOG_HOST` to the AE repo** — ad-hoc runs
   silently catalog Article_Eater.
9. **AF is blind to the gold registry and the S0–S7 canonical path**, and to five AF-facing AE contracts
   (`AF_CORPUS_RECONCILIATION_GATE_CONTRACT_2026-06-11.md`, `AF_DOWNLOAD_SUPPRESSION_APPLY_CONTRACT_2026-06-11.md`,
   `AF_AMBIGUOUS_MATCH_RESOLUTION_CONTRACT_2026-06-11.md`, `AF_DUPLICATE_PDF_CLEANUP_PLAN_CONTRACT_2026-06-11.md`,
   `AF_TO_V7_GROWTH_RECONCILIATION_CONTRACT_2026-06-14.md`). The reconciliation gate's Layer 3 explicitly
   declares AF's `ae_corpus_match_status` insufficient evidence ("CURRENT: VIOLATED") — a live challenge to
   `AF_AE_CORPUS_DEDUPE_AUTHORITY` rule 4. AF's contracts/README.md lists none of them.
10. **Dated-doc drift**: `SYSTEM_ARCHITECTURE_REVIEW_2026_01_25.md:865` points at the dead pre-recovery repo;
    `CLAUDE_CODE_HANDOFF_v2.7.0.md` names a `pdf_lifecycle.db` that exists in neither repo;
    `REPO_STATE_MODEL_AND_PLAN.md:132,154` says 516 MB where the DB is 541 MB.

## 2(c). UNKNOWN — could not verify

- Whether `af_papers`/`af_identity_bridge` are still refreshed from AF or are a frozen 2026-07-30 snapshot
  (no sync script surfaced; needs the AE-side loader identified).
- Whether AF's `ae_corpus_match_paper_id` values agree with `af_identity_bridge` (needs a cross-DB join).
- Whether AF's persisted dedupe state predates AE's 307→19→0 suppression sequence (Layer 6, 2026-06-12).
- Whether AE's `contracts/ae_af/README.md` (2026-02-11) or the 2026-06 AF_* coordination contracts take
  precedence — they describe incompatible worlds (bundle-passing black box vs read-only reconciliation
  gates) and nothing dates their precedence.
- `ports.json` currency against any running AE service.
