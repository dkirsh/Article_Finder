# AF Artifact Catalog Contract (2026-06-16)

**Owner:** CW  **Scope:** Article Finder (AF) repo.  **Status:** Active.
**Canonical code:** `scripts/artifact_catalog.py` (shared tool, copied into AF for self-containment).
**Tests:** `tests/test_artifact_catalog.py` (contract-derived, traceability-gated).
**Companion (AE side):** `../Article_Eater_PostQuinean_v1_recovery/contracts/ARTIFACT_CATALOG_CONTRACT_2026-06-16.md`.

## Purpose

Give the AF repo the same single source of truth for "which artifact is canonical per role" so AF's
databases are positioned correctly (canonical / superseded / stray / deprecated), nothing dangles in a
catch-all, and conformity is enforceable. AF is a separate checkout from AE; this contract governs AF's
own artifact landscape.

## Success conditions (machine-verified by `tests/test_artifact_catalog.py`)

| ID | Condition | Verification |
|----|-----------|--------------|
| SC-AC-1 | Every singleton role has at most one `canonical`; sets have none. | `artifact_catalog.py doctor` exits 0; `test_doctor_*` |
| SC-AC-2 | Distinct databases get distinct roles (no false "superseded copy"). | `test_distinct_dbs_not_conflated` |
| SC-AC-3 | A byte-identical copy can never overwrite the canonical's row. | `test_identical_copy_does_not_clobber_canonical` |
| SC-AC-4 | No singleton canonical resolves to a backup/transient location. | `doctor` + `test_backup_never_canonical` |
| SC-AC-5 | A run whose declared outputs are unregistered FAILS the gate. | `artifact_catalog.py check <paths>`; `test_enforcement_flags_unregistered` |
| SC-AC-6 | A changed file updates its recorded `content_sha256`. | `test_changed_content_updates_same_location` |
| SC-AC-7 | `run()` auto-registers outputs and records input→output lineage. | `test_run_context_records_lineage` |
| SC-AC-8 | Byte-identical copies are grouped and reclaimable bytes computed. | `dupes`; `test_dupes_reports_reclaimable` |
| SC-AC-9 | An empty file is marked `stray`, never canonical. | `test_empty_duplicate_is_stray`, `test_empty_sole_file_never_canonical` |

## AF last-mile success conditions (verified against the live AF repo)

- **LM-AF-1:** `CANONICAL_ARTIFACTS.json` exists at AF repo root, generated from a crawl.
- **LM-AF-2:** `article_finder_db` canonical resolves to `data/article_finder.db` (the 541 MB live DB).
- **LM-AF-3:** `data/article_finder.pre_integrity_repair_2026-05-10.db` is `superseded` (a backup, never canonical).
- **LM-AF-4:** the empty `articles.db` (0 bytes) is `stray`, not canonical.
- **LM-AF-5:** `doctor` exits 0 against the live AF catalog (current run: PASS).

## Verification command

```bash
cd /Users/davidusa/REPOS/Article_Finder_v3_2_3
PYTHONPATH=. pytest tests/test_artifact_catalog.py -q
PYTHONPATH=. ARTIFACT_CATALOG_DB=/tmp/af.db ARTIFACT_CATALOG_HOST="$PWD" python3 scripts/artifact_catalog.py crawl
PYTHONPATH=. ARTIFACT_CATALOG_DB=/tmp/af.db python3 scripts/artifact_catalog.py doctor   # exit 0
```
