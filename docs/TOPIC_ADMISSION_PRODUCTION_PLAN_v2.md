# Topic Admission Production Plan v2

Status: tested prototype; prohibited from Article Eater production authorization
until every release gate below passes.

## Objective and authority

Article Finder owns identity resolution, evidence collection, orchestration,
monitoring, and authorization. `atlas_shared` owns topic constitutions and the
conservative pre-extraction decision vocabulary. Article Eater verifies an AF
authorization before extraction and never reimplements admission logic.

Stephan is the sole human gold authority for classification correctness. Model
performance is measured model-versus-Stephan; there is no human-human kappa.

## Versioned contracts to deliver

1. `IdentityResolutionResult`: DOI/title/author/year assertions, component
   similarities, ambiguity, work/version/retraction relations, and source IDs.
2. `CollectorPlan`: required, optional, or inapplicable sources; collector and
   parser versions; request hash; reason; timeout; retry policy.
3. `SourceObservation`: query, endpoint, retrieval time, status, cache state,
   licence/access class, raw content hash and durable private/public locator.
4. `TaxonomyAssertion`: stable term ID, label, hierarchy, score, assignment
   authority, taxonomy version and source record.
5. `CitationNeighborhoodSummary`: identity-bound edges, depth, direction,
   subject distribution, bridge candidates and coverage limits.
6. `EvidencePacket`: immutable selected-attempt manifest and packet hash.
7. `AdmissionDecision`: full shared intake output plus corpus role, explicit
   question/mechanism bridge, contradictions, temporal role and evidence refs.
8. `AdmissionAuthorization`: accepted decision only, bound to paper and PDF
   hashes, purpose, issuer, schema versions, issue time and revocation state.
   Production must choose and specify either authenticated online introspection
   or signed portable authorization, including key rotation, revocation and
   fail-closed AE verification. The prototype implements neither and therefore
   cannot authorize AE.
9. `DocumentTextArtifact`: PDF hash; converter and version; conversion time;
   page coverage; text hash; page/span map; OCR confidence and anomaly metrics;
   language; and usability decision. Unusable or falsely labelled text holds.
10. `CandidateNomination`: discovery query, source, result rank/page, search
    time, search agent/model/version, rationale, deduplication chain, and seed or
    citation-expansion parent.
11. `HumanGoldVerdict`: Stephan's identity, timestamp, paper/PDF identity,
    displayed evidence spans, blinded status, verdict and reason, schema version,
    and correction/supersession/revocation links. An override cannot bypass
    identity, private-data or PDF-integrity gates.

## Workflow

1. Resolve identity. Conflicts or ambiguity go to hold.
2. Persist a collector plan appropriate to the paper. PubMed absence may be
   `not_applicable` or `not_found`; it is not a collector failure.
3. Run planned collectors concurrently with deadlines. Preserve every attempt
   and raw artifact append-only.
4. Normalize assertions without treating correlated aggregators as votes.
5. Run the shared Atlas intake gate through a typed adapter.
6. Run an independently implemented policy verifier for identity, evidence
   sufficiency, subject contradictions, corpus role, temporal utility and topic
   bridge.
7. Persist an integrity-verification result.
8. Authorize AE only for `accept_candidate` + `article_eater`; all other verified
   decisions remain non-authorizing outcomes.

The evidence policy must enumerate `ok`, `not_found`, `not_applicable`, `partial`,
transient error and permanent error. It defines per-role sufficiency,
authority/correlation classes, conflict precedence and abstention. Citation
neighbourhoods and model-derived taxonomies may never be the sole topic bridge.

## Corpus roles and temporal rule

Allowed roles include direct built-environment evidence, core neuroscience
mechanism, core psychology mechanism, methods/measurement, historical
foundation, adjacent context, and off-topic. Core mechanism papers require a
named question and mechanism bridge. Old papers require a declared historical
or foundational role plus evidence of a modern bridge; age and citation count
alone never establish utility.

The topic bank must gain governed hierarchical core-neuroscience and
core-psychology mechanism constitutions: inclusion, exclusion, false-friend and
bridge rules; hard examples; Stephan approval; versions; deprecation and
supersession. Release requires benchmark coverage for every authorized role.

## Persistence and recovery

The production schema is append-only for plans, attempts, evidence, decisions,
verifications and authorizations. Materialized run state must be reconstructable
from a hash-chained event stream. Runs use compare-and-swap transitions, worker
leases, deadlines, bounded retries, idempotency keys, explicit supersession and
operator retry/abandon commands. Ordered transactional migrations reject unknown
future schema versions.

Private or copyrighted responses and full text remain in an approved encrypted
private storage realm with declared principals, access auditing, retention and
deletion rules. Public-repository and public-log export is forbidden and tested.

## Monitoring controls

Persist monitor observations and alert lifecycles. Report current and historical
values separately: queue depth, throughput, state age, expired leases, retry
exhaustion, source availability and latency, metadata coverage, identity
conflicts, taxonomy drift, decision distribution, contradiction rate,
authorization issuance/revocation and verification failures.

## Test–replan–retest programme

Use three disjoint sets: development, locked validation and sealed final safety.
They must include PDF-0180; DOI collisions; OCR corruption;
chemistry/materials false positives; core neuroscience and psychology hard
positives lacking architecture vocabulary; valid interdisciplinary sensor work;
methods papers; retractions and versions; and paired old papers that are genuinely
foundational or merely obsolete.

Revise only against development. Select thresholds on locked validation. Run the
sealed set once after Stephan's blinded verdicts are fixed. Stephan adjudicates
every gold row. Report exact denominators and binomial confidence bounds, and by
corpus role: precision, recall,
false-admission rate, false-rejection rate, abstention/manual-review rate and
calibration. Overall accuracy is not a sufficient measure.

After release, randomly sample nominations and decisions for continuing Stephan
audit so selection bias and drift remain measurable.

## Production release gates

- The false-admission confidence-bound target and minimum sample size approved
  by Stephan are met; an observed zero alone is not proof of safety.
- Zero authorization-integrity, cross-paper or cross-PDF replay failures.
- Every required/optional/inapplicable source is accounted for.
- Crash/restart succeeds at every state boundary without lost history.
- Concurrent same-run execution is idempotent and lease-safe.
- Every authoritative mutation invalidates or revokes authorization.
- Full shared decision schema and cross-field invariants pass.
- The policy verifier catches PDF-0180 and the interdisciplinary positive control.
- Role-stratified thresholds satisfy limits approved by Stephan.
- Article Eater independently verifies issuer, decision, paper/PDF identity,
  schema, current authorization and revocation status.

The policy verifier is a separately versioned package or process governed by its
own specification. It does not reuse adjudicator predicates; error or timeout
fails closed.

Authorization has an executable default-deny interlock. It requires a signed,
version-specific release attestation naming the code commit, schema,
release-report hash, Stephan-approved threshold version, issuer, environment and
validity period. Without it AF cannot issue authorization. Production uses
authenticated online introspection or canonical signed authorization (for
example Ed25519), with key ID/custody, environment separation, rotation,
revocation, expiry, replay protection and an AE fail-closed trust-store policy.

Deployment proceeds through shadow operation and a bounded canary. A tested kill
switch, rollback and incident-response procedure precede corpus-wide authority.

Until all gates pass, the subsystem may collect evidence and produce review
reports, but it must not authorize Article Eater processing.
