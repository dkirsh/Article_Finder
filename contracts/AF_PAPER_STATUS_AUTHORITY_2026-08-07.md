# Article Finder Paper-Status Authority

Status: DRAFT; requires non-author certification
Tier: P1

## Authority

`papers.status` is a lifecycle field distinct from `triage_decision`. The latter
records a scoring decision (`send_to_eater`, `review`, or `reject`); it is not a
paper-status state and must not be inserted into the status machine.

The executable declaration is `contracts/fsm/paper_status.fsm.json`.
`Database.update_paper_status` and every status-bearing `Database.add_paper`
insert or upsert must reject an edge not declared there. Direct-SQL maintenance
writers must run the same transition check before their update.

## Invariant

`rejected` OUTRANKS later admission: once a paper reaches `status='rejected'`, no
automatic writer may return it to `candidate`, `queued_for_eater`, or any later
state. A human repair is a separate audited operation, not a lifecycle edge.

## Failure Signature

- A caller supplies a triage value such as `send_to_eater` as a paper status.
- A rejected row is silently reintroduced to the AE queue.
- A retry skips `queued_for_eater` and asserts an execution state directly.

## Witnesses

- Positive: `unregistered -> candidate -> pending_scorer -> candidate -> downloaded ->
  queued_for_eater` is accepted.
- Negative: `rejected -> queued_for_eater` is rejected at the attempted edge.

Tests: `tests/test_contract_fsm_runtime.py` and
`tests/test_database_lifecycle_fsm.py`.

## Rationale

The 2026-08-07 proposal combined `papers.status` and `triage_decision`. The schema
and callers show they are separate variables. Encoding the combined sequence would
give a formal appearance to an invalid model and would reject legitimate drivers.
