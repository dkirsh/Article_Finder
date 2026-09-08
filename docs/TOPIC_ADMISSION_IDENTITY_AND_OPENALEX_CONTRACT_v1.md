# Topic Admission Identity and OpenAlex Contract v1

## Scope

This contract governs the first implemented external evidence source. It is a
review-only prototype and cannot authorize Article Eater.

## Collector planning

Before any request, Article Finder persists a `CollectorRequirement` containing
collector/version, requiredness, applicability, reason, credential-free request
hash, timeout and maximum attempts. A required but inapplicable source holds the
run. Collector names must be unique.

OpenAlex v1 is applicable only when the candidate has a syntactically valid DOI.
It uses the singleton DOI endpoint and the curated core corpus. API credentials
may appear only in an Authorization header and must never enter the recorded URL,
request hash, database, raw artifact or logs.

## Source observation and raw provenance

The source observation records request hash and credential-free URL, retrieval
time, HTTP status, collector/parser version, result status, response hash,
content-addressed locator and access class. Raw OpenAlex metadata is CC0 public
metadata and is retained byte-for-byte. A verifier recomputes its size and SHA-256.

Statuses are `ok`, `not_found`, `not_applicable`, `partial`, `transient_error`,
or `permanent_error`. This tranche treats OpenAlex as required: every outcome
other than `ok` holds. Retries remain a later release-gated implementation.

## Identity resolution

The resolver normalizes DOI and text and records independent DOI, title, author
and year comparisons. DOI disagreement, severe title disagreement, disjoint
authorship, malformed source year, or a year disagreement greater than one year
is a hard conflict. No weighted score can override a hard conflict. Resolution
requires a weighted score of at least 0.80 and combined token/ordered-text
similarity of at least 0.65. Ambiguous, conflicting or insufficient identity
holds before adjudication.

The computed component evidence, thresholds, conflicts, reasons and resolver
version are persisted and hashed. A collector-supplied scalar alone is not the
identity authority for this OpenAlex collector.

## Taxonomy assertions

Every OpenAlex topic retains its stable ID, label, domain/field/subfield
hierarchy, model score, source work ID, record update date, assignment method and
authority class `aggregator_model_derived`. Work type is retained separately as
`aggregator_metadata`. Neither is a corpus-admission vote or a sufficient topic
bridge.

## Success conditions

- Plan, attempt and observation collector sets agree exactly.
- Planned and observed versions and request hashes agree.
- Raw bytes exist and reproduce the stored size and SHA-256.
- The identity assertion is `resolved` for the same candidate paper ID.
- Exactly one registered raw artifact backs every network observation, and the
  complete state-transition ledger starts at creation, is contiguous and ends
  at the recorded run state.
- OpenAlex supplies at least one meaningful hierarchical topic, exactly one
  primary topic, and one declared correlation family for all model-derived
  topic assertions.
- Every normalized evidence item passes existing finite-range validation.
- No API credential appears in persisted provenance.
- All ordinary and adversarial tests pass.
