# Topic Admission Subsystem Contract v1

## Authority boundary

Article Finder owns orchestration and persistence. `atlas_shared` owns the
pre-extraction decision vocabulary and classification logic. Article Eater may
submit a candidate to this subsystem but may not implement a second gate.

## Inputs

Only pre-extraction evidence is permitted: bibliographic identity, source and
PDF provenance, title, abstract, author or repository keywords, supplied article
type, and first-page text. Article Eater extracted variables, measures, claims,
or conclusions are forbidden.

## Processing contract

1. Persist the candidate and its canonical JSON hash.
2. Resolve minimum identity before external collection.
3. Execute independent evidence collectors concurrently.
4. Persist every attempt, result, warning, source version, identity-match score,
   raw-response hash, normalized evidence item, and state transition.
5. Hold the candidate on collector failure or identity disagreement.
6. Pass the completed evidence packet to the shared Atlas intake gate.
7. Persist the decision and the exact evidence-set hash.
8. Reconstruct and verify the run from SQLite before issuing a non-authorizing
   review snapshot.

## Success conditions

A run succeeds only when it reaches `verified` and:

- all required collectors have terminal `ok` attempts;
- candidate, evidence, evidence-set, and decision hashes recompute;
- every persisted state transition is legal;
- the decision uses the shared intake vocabulary;
- independent verification records no finding.

`hold` and `failed` are safe terminal outcomes, not successful admissions.
This prototype emits no Article Eater authorization. It may emit only a
`topic_admission_integrity_snapshot_v1`, explicitly marked non-authorizing.

## Monitoring

Monitoring reports counts by state, stale nonterminal runs, failed collector
attempts, and failed verification records. A nonzero failure or stale count is
an attention condition. The database is the authority; logs are supplementary.

## Provenance database

The subsystem uses its own SQLite database during validation. Its tables are:

- `admission_run`
- `state_transition`
- `collector_attempt`
- `evidence_record`
- `admission_decision`
- `verification_record`
- `schema_version`

No table is an opaque cache: each table represents a declared entity, activity,
decision, or verification event.

## Operator controls

```bash
python -m topic_admission.cli --db PATH monitor
python -m topic_admission.cli --db PATH verify RUN_ID
python -m topic_admission.cli --db PATH snapshot RUN_ID
```

The monitor and verifier return a nonzero status when attention is required.
