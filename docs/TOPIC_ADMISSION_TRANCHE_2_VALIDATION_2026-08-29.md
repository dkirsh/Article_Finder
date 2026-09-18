# Topic Admission Tranche 2 Validation — 2026-08-29

## Implemented scope

- Versioned identity-resolution contract and deterministic component scores.
- Persisted collector plan before network execution.
- Credential-free OpenAlex DOI-singleton request provenance.
- Content-addressed raw-response storage and database registration.
- Hierarchical OpenAlex topic assertions with stable IDs and authority class.
- Plan/attempt/observation/identity/raw-artifact verification.
- Monitoring of missing observations, unresolved identity, missing raw bytes and
  byte-level raw corruption.
- Live external validator with a process-level wall-clock deadline.
- Per-collector process isolation with enforced wall deadlines.

No Article Eater authorization or integration was added.

## Test–replan cycles

1. Initial implementation: 26 focused tests passed.
2. Live validation exposed that two sequential requests could exceed the intended
   wall duration. The validator was replanned to make one external request,
   perform the negative comparison locally against the retained raw record, and
   enforce a process-level alarm.
3. Live validation then passed. It resolved DOI `10.1021/ja02261a002` to OpenAlex
   work `W2010861052`, field Chemistry, with identity score 1.0; the misleading
   environmental-psychology title produced `conflict`.
4. Full repository test: 112 passed, one skipped.
5. Self-review found and corrected contradictory-identity adjudication, unknown
   statuses, discarded selected HTTP metadata and future-schema acceptance.
6. Focused retest after correction: 30 passed.
7. First independent three-reviewer panel: **rejected** the tranche. Ordinary
   tests had missed fail-open deletion of identity/raw/transition rows, hard
   identity conflicts, secret-bearing exceptions, hostile numeric values,
   symlink escapes, ineffective deadlines and a false migration fixture.
8. Those attacks were promoted into permanent regression tests. The correction
   pass added set equality and ledger replay, mandatory identity assertions,
   conflict-first resolution, bounded/typed OpenAlex parsing, credential-echo
   rejection, raw-path containment, monitor hashing, a realistic v1 migration
   fixture and process termination at deadline.
9. Corrected focused suite: 45 passed. Corrected full repository suite: 131
   passed, one skipped.
10. Second panel cycle found further failures: missing-row monitor blind spots,
    credential echoes in allowlisted response headers, request-URL substitution,
    cross-origin redirect disclosure, malformed-plan state escape, and weak
    topic identifier/duplicate validation.
11. The next correction pass added monitor set differences, recursive
    pre-persistence credential rejection, response-header screening, independent
    URL/hash and endpoint checks, redirect refusal, validated planner contracts,
    terminal exception handling, initial-ledger and raw-metadata binding, and
    complete topic hierarchy duplicate fingerprints.
12. Third-cycle focused suite: 59 passed. Full repository suite: 145 passed,
    one skipped.
13. Final monitor review added fresh full verification of every verified run and
    fail-closed malformed-JSON handling. A final provenance review then found
    that credential rejection was not universal across database write methods.
14. The store boundary now rejects credential markers, configured exact secret
    values, non-finite JSON and payloads over 2 MiB on every write surface.
    HTTP error bodies are bounded. Permanent tests inspect the database, WAL and
    shared-memory files for rejected sentinels.
15. Final focused suite: 64 passed. Final full repository suite: 150 passed,
    one skipped. All three independent reviewers returned **PASS for this
    explicitly review-only, non-authorizing tranche**.
16. A tracked Semantic Scholar credential discovered by the panel was removed
    from the working tree and replaced by environment indirection. External
    rotation and any authorized history remediation remain required operational
    actions.

## Independent external confirmation

A separate bounded HTTP query, outside the collector implementation, returned:

- Work: `W2010861052`
- DOI: `10.1021/ja02261a002`
- Title: `THE ATOM AND THE MOLECULE.`
- Year: 1916
- Field: Chemistry
- Primary topic: History and advancements in chemistry

## Current limitations

- OpenAlex v1 is DOI-only and required when selected.
- Attempts are not yet append-only and resumable.
- Process isolation currently uses `fork` on this Unix prototype; the production
  worker service must avoid fork-from-multithreaded-process hazards.
- The v1-to-v2 migration is additive but is not yet the full transactional,
  fingerprinted migration registry required by the production plan.
- Current hashes detect corruption; they do not authenticate data against an
  actor able to rewrite both records and hashes.
- Scientific contradiction/corpus-role verification remains a later independent
  policy-verifier tranche.
- The shared Atlas gate still requires its separately identified contract fixes.
