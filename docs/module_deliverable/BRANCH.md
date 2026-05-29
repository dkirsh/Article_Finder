# Track 2 — GitHub branch & PR locations

**Branch name (both repos):** `track2/dhruv-sood`

The Track 2 module spans two repositories (each a fork of an upstream `dkirsh` repo).
Work is committed to the same branch name in both.

| Task | Repo (fork) | Upstream | Branch | PR |
|---|---|---|---|---|
| Task 1 — Fix the Contribute Page | `dhruvsood12/Knowledge_Atlas` | `dkirsh/Knowledge_Atlas` | `track2/dhruv-sood` | PR #1 → `dkirsh:main` |
| Task 2 — Gap Targeting & Query Gen | `dhruvsood12/Article_Finder` | `dkirsh/Article_Finder` | `track2/dhruv-sood` | PR #1 → `dkirsh:main` (combined with Task 3) |
| Task 3 — Search / Triage / Acquire / Handoff | `dhruvsood12/Article_Finder` | `dkirsh/Article_Finder` | `track2/dhruv-sood` | PR #1 → `dkirsh:main` (combined with Task 2) |

## Local commit state (as of this deliverable)

The remediation commits are on `track2/dhruv-sood` **locally** in each fork and have
**not been pushed yet** (pending review). Local HEADs:

- Knowledge_Atlas `track2/dhruv-sood` → `36cfcd6`
- Article_Finder `track2/dhruv-sood` → `375d08f`

To update the open PRs after review:

```bash
cd track2/Knowledge_Atlas && git push myfork track2/dhruv-sood
cd track2/Article_Finder && git push myfork track2/dhruv-sood
```

(`myfork` = the `dhruvsood12` fork; `origin` = upstream `dkirsh`.)

## Remediation commits added on top of the original submission

Knowledge_Atlas (Task 1):
- Task 1 contract: AE dedup-probe substitution + §0.1 handoff schema
- Task 1 UI: honest "what happens next" copy + `needs_more_info` handling
- Task 1: enforce §6 confidence floor (accept<0.55 → edge_case)
- Task 1 tests: deterministic B9, 2A confidence floor, 2C DB-status domain, §5 checklist coverage (29 → 40 checks)
- Task 1 contract: response-status vs DB-status clarification; §5 boxes flipped; §4 #9 fixed; duplicate-pointer corrected

Article_Finder (Tasks 2 & 3):
- Task 3 contract: AE handoff substitution + §0.1 schema + abstract-client substitution
- Task 3: `ae_handoff.py` — the last-mile writer (data/handoff/*.json), wired as pipeline step 7
- Task 3 tests: PRISMA identity/completeness + `lifecycle_transitions` + `query_quality_flags` enum (25 → 37 checks)
- Track 2: `scripts/verify_track2_workflow.py` end-to-end chain verifier (8/8)
