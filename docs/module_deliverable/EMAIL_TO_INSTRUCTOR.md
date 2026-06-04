# Email to instructor — Track 2 deliverables

**To:** DK
**Subject:** Track 2 (Article Finder) — box diagram, box specs, branch, and materials
**Attach:** `track2_module_sprints.png` (and optionally the zip of this folder)

---

Hi DK,

Here's everything you asked for on the Track 2 Article Finder module. I've put
the review packet in the repo and attached the diagram so you can skim it
without cloning. Quick map to your four asks:

**1) BOX DIAGRAM (as a set of sprints)** — attached: `track2_module_sprints.png`
Three sprints = the three tasks: Sprint 1 = Task 1 (Contribute Page),
Sprint 2 = Task 2 (Gap Targeting + Query Gen), Sprint 3 = Task 3 (Search →
Triage → Acquire → Handoff). Every box is labeled with the real file that
implements it, and the Article-Finder → Article-Eater boundary (the
`data/handoff/*.json` artefact) is shown explicitly.
Source + SVG: `track2/MODULE_DELIVERABLE/track2_module_sprints.mermaid` / `.svg`

**2) BOX SPECS** — `track2/MODULE_DELIVERABLE/box_specs.md`
Per-box purpose, inputs, outputs, implementing file, contract reference, and
status vocabulary, grouped by sprint.

**3) GITHUB BRANCH (name + location)**
Branch name: **`track2/dhruv-sood`** (same name in both forks)
- Task 1:        github.com/dkirsh/Knowledge_Atlas  → PR #1
- Tasks 2 & 3:   github.com/dkirsh/Article_Finder   → PR #1
Both PRs are open and up to date with the latest work.

**4) OTHER MATERIALS** — `track2/MODULE_DELIVERABLE/README.md` indexes them:
- The four contracts (one per task, plus the Task 3 sub-contracts)
- A one-command verification script (see below)
- The finding → fix → proof closure table
- The branch/PR doc

**On the module meeting its spec / passing a ruthless prompt:**
It does today. Commands are run from each fork's root:

```
# Tasks 2 & 3 — from the Article_Finder repo root
python3 scripts/verify_track2_workflow.py        → CHAIN 9/9   (chain + handoff end-to-end)
python3 task3/tests_task2_task3.py               → 51/51
T2_LIVE=1 python3 task3/tests_task2_task3.py     → 46/46       (real API calls)

# Task 1 — from the Knowledge_Atlas repo root
python3 data/test_pdfs/validate_task1.py         → 40/40
```

I also ran an adversarial pass that actively tries to break it — hostile
inputs to the abstract gate, repeated/forced handoffs for idempotency, the
PRISMA funnel partition, and an Article-Eater-side stub that validates the
handoff artefact is actually consumable. It survived all of them, and the
abstract requirement is a hard gate: a paper with no abstract never produces
a handoff.

One honesty note so nothing's a surprise: the Article Eater repo isn't on my
checkout, so the AE dedup probe and intake are documented local substitutes
(named in each contract's §0) — drop-in when AE is mounted. Sci-Hub/scidownl
stays exactly as the rubric specifies (last-resort, gated, default closed).

Since you're out Tuesday — happy to do a short walkthrough whenever works, or
just reply here and I'll clarify anything. Thanks!

Best,
Dhruv
