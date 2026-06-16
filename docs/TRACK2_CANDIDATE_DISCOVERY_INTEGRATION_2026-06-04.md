# Track 2 Candidate Discovery Integration

Date: 2026-06-04

## Decision

Do not replace Article Finder's canonical pipeline with the Track 2 branch.
Use the best Track 2 ideas as an upstream candidate-discovery adapter.

Article Finder remains the system of record for:

- the `papers` table and dedupe contract
- canonical triage vocabulary: `pending`, `send_to_eater`, `review`, `reject`
- PDF attachment and quarantine rules
- Zotero and existing acquisition paths
- AF-to-AE job bundles
- AE output parsing and storage
- health checks and repair scripts

The new adapter adds a staging layer before promotion into `papers`.

## Added Files

- `candidate_discovery/buffer.py`
  - SQLite candidate buffer.
  - Stores harvested candidate references before they become AF papers.
  - Keeps source provenance, query provenance, target id, rough VOI fields, triage state, PDF acquisition state, and lifecycle transitions.
  - Dedupes by DOI, exact normalized title, and conservative fuzzy title overlap.

- `candidate_discovery/oa_acquisition.py`
  - Stores verified PDF bytes only after checking `%PDF-`.
  - Computes SHA-256.
  - Registers browser-assisted PDF files honestly as browser-assisted acquisitions.

- `candidate_discovery/adapters.py`
  - Maps candidate decisions into AF's vocabulary.
  - Promotes accepted candidates through `Database.add_paper`, so AF remains canonical.

- `tests/test_candidate_discovery_integration.py`
  - Verifies provenance merge and fuzzy title dedupe.
  - Verifies browser-assisted PDF registration and SHA recording.
  - Verifies promotion into AF's `papers` table and decision mapping.

- `candidate_discovery/sources.py`
  - Wraps the existing AF OpenAlex client.
  - Harvests OpenAlex works into the candidate buffer instead of bypassing AF.

- `candidate_discovery/triage.py`
  - Provides a deterministic keyword gate for the candidate stage.
  - This is a reviewable first-pass gate, not a replacement for AF's richer
    taxonomy/embedding triage.

- `candidate_discovery/run.py`
  - Runs one target-driven slice: harvest, triage, optional OA PDF acquisition,
    and promotion into AF.

- `scripts/run_candidate_discovery.py`
  - CLI entrypoint for one target-driven candidate discovery pass.

## Decision Mapping

Track 2 candidate decisions are not allowed to leak directly into AF.

| Candidate decision | AF triage decision | AF status |
| --- | --- | --- |
| `ACCEPT` | `send_to_eater` | `candidate`, or `downloaded` if a PDF is attached |
| `EDGE_CASE` | `review` | `candidate` |
| `REJECT` | `reject` | `rejected` |
| `MISSING_ABSTRACT` | `pending` | `candidate` |
| unset | `pending` | `candidate` |

By default, only `ACCEPT` candidates are promoted. Edge cases can be promoted
only by explicitly passing `include_edge_cases=True`.

## Why This Shape

Track 2's useful contribution is not its whole pipeline. Its strongest idea is
that target-driven article hunting should have durable intermediate state:
what was searched, why it was searched, what was found, how it was judged, and
what happened to the PDF acquisition attempt.

Article Finder already has more mature downstream machinery. Swapping the whole
Track 2 workflow into AF would duplicate or weaken that machinery. A staging
adapter keeps the useful part while preserving the parts of AF that already
work.

## Current Verification

Run from `/Users/davidusa/REPOS/Article_Finder_v3_2_3`:

```bash
python3 -m pytest tests/test_candidate_discovery_integration.py -q
python3 -m pytest tests/test_database_add_paper_dedupe.py tests/test_title_metadata_repair.py -q
```

Current result after the second increment:

- candidate discovery integration: `4 passed`
- database/metadata regression subset: `4 passed`
- CLI help check: passes

Live smoke test against isolated `/tmp` databases:

```bash
python3 scripts/run_candidate_discovery.py \
  --query "daylight attention office" \
  --target-id Q-DAYLIGHT-ATTENTION \
  --target-type question \
  --accept-terms "daylight,attention,office" \
  --reject-terms "thermal" \
  --limit 3 \
  --candidate-db /tmp/af_candidate_live_smoke.db \
  --af-db /tmp/af_candidate_live_af.db
```

Result:

- OpenAlex returned 3 candidates.
- The candidate triage gate marked 1 `ACCEPT` and 2 `MISSING_ABSTRACT`.
- The accepted candidate was promoted into the isolated AF database.
- The configured OpenAlex API key was rejected, but AF fell back to unauthenticated
  OpenAlex successfully.

## Panel Review Timing

Use two panel reviews.

First, run a brief design-gate panel now. The question is not whether this is
production-ready. The question is whether the boundary is right:

- Is candidate discovery properly upstream of AF's canonical `papers` table?
- Is the state model sufficient for target-driven retrieval?
- Are decision mappings honest and reversible enough?
- Are provenance and lifecycle records adequate for debugging?

Second, run the ruthless go/no-go panel after the next integration increment:

- one real target-driven search writes candidates into the buffer
- one candidate is promoted into AF
- one acquired PDF path is attached and verified
- one promoted paper is prepared for AE using the existing AF handoff path

The first two conditions are now satisfied in an isolated live smoke test. The
PDF attachment and AE handoff conditions are still the remaining threshold for a
strict go/no-go panel.

## Next Increment

The next implementation step is to connect one real search source to
`CandidateBuffer.add_candidate`. Do not build a second AF. The contract should
be:

1. A query planner receives a target question, theory, or gap.
2. It searches one source, such as OpenAlex or Semantic Scholar.
3. It writes all returned references into the candidate buffer with provenance.
4. A triage scorer marks each candidate as `ACCEPT`, `EDGE_CASE`, `REJECT`, or
   `MISSING_ABSTRACT`.
5. Only accepted candidates are promoted into AF.
6. AF performs the existing PDF, handoff, AE, and storage work.

Success condition: a reviewer can start with a target question and inspect the
full chain from query, to candidate, to triage, to promoted AF paper, without
guessing where a paper came from or why it entered the corpus.
