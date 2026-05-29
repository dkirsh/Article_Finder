# COGS 160 Track 2 — Article Finder Module: Deliverable Packet

Author: Dhruv Sood · Module: Track 2 (Article Finder) · Branch: `track2/dhruv-sood`

This folder is the review packet for the Track 2 module: the box diagram, the box
specs, the GitHub branch location, and the supporting materials. The module spans
two forks (Knowledge_Atlas = Task 1; Article_Finder = Tasks 2 & 3).

## Contents

| File | What it is |
|---|---|
| [track2_module_sprints.mermaid](track2_module_sprints.mermaid) / [`.svg`](track2_module_sprints.svg) | The box diagram, organised as the three sprints (= tasks), with real file names. Pink = the last-mile handoff. |
| [box_specs.md](box_specs.md) | Per-box purpose, inputs, outputs, implementing file, contract reference, and status vocabulary. |
| [BRANCH.md](BRANCH.md) | GitHub branch name + fork/upstream/PR locations + push commands. |
| README.md (this file) | Index + remediation-closure summary + how to verify. |

## The module in one paragraph

A contributor submits an article (PDF, citation, or metadata). Task 1's Contribute
Page classifies it, checks it against the corpus for duplicates, scores topic
relevance, and stores on-topic items as `staged_pending_review` — withholding
storage and asking for more when the abstract is missing. Task 2 turns
low-confidence knowledge gaps into ranked search queries. Task 3 runs those
queries, lands every candidate in `article_references`, triages cheaply (metadata,
then abstract, then classifier), acquires PDFs for ACCEPTed papers only, rebuilds
the PRISMA funnel from a single SQL group-by, and — the last mile — writes a
schema-valid handoff artefact (`data/handoff/*.json`) that Article Eater reads.
Collection becomes completion at that handoff.

## How to verify (one command)

```bash
python3 track2/Article_Finder/scripts/verify_track2_workflow.py
```

Runs both per-task suites and asserts the last-mile handoff end-to-end. Current state:

| Suite | Result |
|---|---|
| Task 1 — `Knowledge_Atlas/data/test_pdfs/validate_task1.py` | **40/40** |
| Task 2 + 3 — `Article_Finder/task3/tests_task2_task3.py` | **37/37** |
| Chain + handoff — `Article_Finder/scripts/verify_track2_workflow.py` | **8/8** |

## Remediation closure — audit findings → fix → proof

A senior-panel audit flagged the module as "collection without completion." Every
**confirmed** finding is now closed with a test that goes red if the behavior breaks;
every **overreach** finding (panel-invented, not in the rubric) is documented as a
substitution or descoped against a rubric quote.

| # | Finding (audit) | Verdict | Fix | Proof |
|---|---|---|---|---|
| 1 | No Article Eater handoff anywhere | CONFIRMED | `ae_handoff.py` writes `data/handoff/*.json`; pipeline step 7 | chain verifier 8/8 |
| 2 | Handoff schema undefined | CONFIRMED | §0.1 local 14-field schema in both contracts | `box_specs.md`; verifier asserts schema |
| 3 | §0 tables omit AE | CONFIRMED | AE substitution row added to both §0 tables (with rubric quotes) | contracts §0 |
| 4 | §6 confidence floor unimplemented | CONFIRMED | demotion at verdict assignment | 2A red-then-green |
| 5 | B9 conditional no-op | CONFIRMED | deterministic empty-abstract fixture, unconditional asserts | B9 red-then-green |
| 6 | DB status enum "fictional" | CONFIRMED (clarify) | contract distinguishes DB-status vs response-status | 2C DB-domain test |
| 7 | `lifecycle_transitions` untested | CONFIRMED | transition-sequence + no-orphans test | Task 3 suite |
| 8 | PRISMA under-tested (2 of N) | CONFIRMED | identity + 15-field + 5-bucket disjointness | Task 3 suite (red-then-green) |
| 9 | False "nightly/24-48h" UI copy | CONFIRMED | honest copy on both canonical pages | grep clean; UI review |
| 10 | `needs_more_info` invisible in UI | CONFIRMED | added to label/status + surfaces `next_action`/`evidence_stage` | UI + B9 |
| 11 | §5 checklist unchecked | CONFIRMED | flipped, each box maps to a passing test id | contract §5 |
| 12 | §4 #9 self-contradiction | CONFIRMED | reworded to "session-only" | contract §4 |
| 13 | No chain verifier in track2 | CONFIRMED | `scripts/verify_track2_workflow.py` | runs 8/8 |
| — | 14-field *canonical* schema | OVERREACH | adopted as documented *local* schema (rubric enumerates no fields) | contract §0.1 label |
| — | 9-state machine (`article_eater_*`) | OVERREACH | marked AE-owned, out of AF scope (rubric uses triage_stage/decision) | `track2_hub.html:102` quote |
| — | "60-step trigger" is AF's job | OVERREACH | AF writes the bundle only; AE runs its pipeline | `track2_hub.html:102` quote |

Net: Task 1 29 → 40 checks, Task 2+3 25 → 37 checks, plus a new 8-check chain
verifier. The last-mile trace now resolves end-to-end: ACCEPT row → `ae_handoff.py`
→ `data/handoff/<id>.json` → Article Eater intake.

## Scope honesty

- Sci-Hub / scidownl stays as the rubric specifies (Task 3 last-resort, 4-condition
  gate, default closed) — not expanded.
- The AE dedup probe and handoff use **documented local substitutes** because the
  instructor's `Article_Eater` tree and its absolute paths are not on this checkout;
  both are drop-in when that repo is mounted. See each contract's §0.
