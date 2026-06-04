# Track 2 — Deliverable Map & Dependency Contract

Author: Dhruv Sood · Branch: `track2/dhruv-sood` · Updated: 2026-06-03

This is the grader's entry point. It declares (1) exactly how the one external
dependency must be supplied, (2) the verifier commands, and (3) which files are
the deliverable surface vs. support / generated / inherited material.

---

## 1. Dependency contract — `atlas_shared`

The pipeline is **not** fully standalone: the classifier + relevance code lives
in `atlas_shared` (a shared course module, per the assignment setup). It is the
**only** external code dependency. Supply it in **any one** of these ways:

| Mode | How | When the verifier uses it |
|---|---|---|
| **Installed** | `cd atlas_shared && pip install -e .` | nothing extra needed — `import atlas_shared` just works |
| **Env var** | `export KA_ATLAS_SHARED_SRC=/path/to/atlas_shared/src` | prepend to the commands below |
| **Sibling checkout** | clone `atlas_shared` next to `Article_Finder` / `Knowledge_Atlas` | auto-detected |

Resolution order in code (`abstract_triage.py`, `gap_extractor.py`,
`Knowledge_Atlas/data/test_pdfs/validate_task1.py`): **installed → `$KA_ATLAS_SHARED_SRC` → sibling**.
If none resolve, Task 1 SKIPs cleanly (exit 0) with instructions; Task 2/3 surface a clear error.
No `/private/tmp` or other absolute-path assumptions remain.

The two **data** files `atlas_shared` would otherwise supply are **bundled in this repo**
at `task3/fixtures/` (`question_constitutions_starter.json`, `mechanisms.json`), so no
sibling `Knowledge_Atlas` checkout is needed for Task 2/3. Override with
`$KA_CONSTITUTIONS` / `$TRACK2_MECHANISMS` if desired.

---

## 2. Verifier commands

```bash
# --- Article_Finder (Tasks 2 & 3) — from the Article_Finder repo root ---
python3 -m pytest task3/tests_task2_task3.py -q     # collects + passes (1 passed)
python3 task3/tests_task2_task3.py                  # 51/51 offline (deterministic, isolated temp DB)
T2_LIVE=1 python3 task3/tests_task2_task3.py         # 55/55 — real abstract + real OA PDF
python3 scripts/verify_track2_workflow.py            # CHAIN 9/9 (incl. handoff + AE-consume)

# --- Knowledge_Atlas (Task 1) — needs atlas_shared (declared above) ---
KA_ATLAS_SHARED_SRC=/path/to/atlas_shared/src python3 data/test_pdfs/validate_task1.py   # 42/42
```

**Test isolation:** the Task 3 suite runs the pipeline against a per-run temp DB
(`$TRACK2_DB`) and temp outputs (`$TRACK2_OUT`); repeated or parallel runs never
share SQLite state and never modify the committed `task3/data/` tree. No reset
step required.

---

## 3. Deliverable map

### Core grading surface (this is the contribution)
| File | Role |
|---|---|
| `gap_extractor.py` | Task 2 — mechanism-gap extraction + VOI heuristic (+ `voi_breakdown`) |
| `query_generator.py` | Task 2 — AI-Citation + Boolean query generation |
| `task3/run_pipeline.py` | Task 3 — pipeline driver |
| `task3/search_runner.py` | Task 3 — search backends + insert/dedupe into `article_references` |
| `task3/abstract_collector.py` | Task 3 — abstract source cascade (S2/CrossRef/PubMed/OpenAlex) |
| `task3/abstract_triage.py` | Task 3 — Stage 1 metadata screen + Stage 2B classifier triage |
| `task3/pdf_acquirer.py` | Task 3 — gated PDF acquisition (real OA download behind `--enable-network`) |
| `task3/prisma_dashboard.py` | Task 3 — PRISMA funnel from a single SQL `GROUP BY` |
| `task3/ae_handoff.py` | Task 3 — Article Eater handoff artefact writer (local substitute) |
| `task3/db_schema.py` | Task 3 — schema, `article_references`, lifecycle, views |
| `task3/tests_task2_task3.py` | Task 2+3 automated checklist (51/51 · 55/55 live) |
| `scripts/verify_track2_workflow.py` | one-command chain verifier (9/9) |
| `Knowledge_Atlas/ka_article_endpoints.py` + `ka_contribute_public.html` | Task 1 — contribute page |
| `Knowledge_Atlas/data/test_pdfs/validate_task1.py` | Task 1 validator (42/42) |

> The `Knowledge_Atlas/…` rows live in the **sibling Knowledge_Atlas repo** (Task 1), relative to the `track2` parent dir — not under `Article_Finder/`. Run them from the Knowledge_Atlas repo root (see §2).

### Evidence & integration proofs (runnable)
| File | Role |
|---|---|
| `demo.sh` | one-command narrated end-to-end demo of **Tasks 1, 2 & 3** (`./demo.sh`, or `--live` to download a real OA PDF); Task 1 runs from the sibling Knowledge_Atlas repo. Isolated temp DB, restores both trees on exit. Captured run + annotations: `docs/DEMO_TRANSCRIPT.md` |
| `task3/eval_triage.py` | labeled triage eval — 30 abstracts incl. 6 within-domain hard near-misses; lenient **P 0.765 / R 0.929**, strict ACCEPT-only **P 1.0**; reports false-accept/reject + EDGE_CASE→human-review routing |
| `task3/ae_ingest_smoke.py` | gated **real** Article-Eater ingestion smoke test (SKIPs cleanly with no AE; performs a real ingestion when `$AE_INGEST_CMD`/`$AE_INBOX` is set) |
| `TRACK2_VOI_COMPARISON.md` | Track 2 heuristic VOI vs Article Eater/BN structural + epistemic VOI |

### Support fixtures (small, committed on purpose)
- `task3/fixtures/question_constitutions_starter.json`, `task3/fixtures/mechanisms.json` — bundled
  copies so Task 2/3 needs no sibling repo. Regenerate by copying from `atlas_shared` / `Knowledge_Atlas`.
- `Knowledge_Atlas/data/question_constitutions_starter.json`, `Knowledge_Atlas/data/contracts/` — Task 1 bundled assets + the Kaden-attributed schema.

### Generated outputs (regenerated each run — NOT hand-authored)
- `task3/data/*.json`, `task3/data/*.html` (search_results, triage_results, prisma_funnel, dashboards).
  Provenance: produced by `python3 task3/run_pipeline.py --backend mock`. During tests these route to a
  temp dir, so committed copies are stable evidence snapshots, not test state.
- `gap_results.json`, `query_results.json` — produced by `gap_extractor.py` / `query_generator.py`.

### Contracts & docs (supporting)
- `task3/docs/TASK3_CONTRACT.md`, `docs/GAP_EXTRACTOR_CONTRACT_TASK2.md`, `docs/QUERY_GENERATOR_CONTRACT_TASK2.md`
- `docs/module_deliverable/` — sprint diagram, box specs, self-audit, VOI comparison
- `TRACK2_VOI_COMPARISON.md` — Track 2 heuristic VOI vs Article Eater/BN VOI

### Inherited / unmodified scaffolding (NOT part of this deliverable)
- `article_finder_v2/`, `cli/`, `core/`, `ui/`, `search/`, `ingest/`, and other pre-existing Article Finder
  modules are upstream scaffolding, not the Track 2 contribution. The Track 2 surface is the list above.

---

## 4. Honest boundaries
- **Article Eater handoff** is a documented **local substitute** (`ae_handoff.py` writes
  `data/handoff/*.json`; `ae_inbox_stub.py` validates it). The **real delivery seam is built**
  (`ae_handoff.deliver_to_ae()` + `task3/ae_ingest_smoke.py`): on a machine with AE, set
  `AE_INGEST_CMD` or `AE_INBOX` and it performs a real ingestion; on this checkout (no AE repo)
  it SKIPs cleanly. The seam mechanics are unit-tested offline. It is **not** a verified
  ingestion against the real AE here. See `task3/docs/TASK3_CONTRACT.md §0`.
- **VOI** is a first-stage search-ranking **heuristic**, not the full Article Eater/BN VOI model.
  See `TRACK2_VOI_COMPARISON.md`.
- **scidownl** stays gated + default-closed (not a live downloader).
- Live abstract/PDF proofs are opt-in (`T2_LIVE=1`); the captured evidence (PLOS OA PDF, 829,365 B,
  sha `616f6081…`) is recorded in the self-audit.
