# AF-first pipeline — gate order, database homes, provenance, and the repair list

*2026-09-09, Fable, recording David's architectural ruling given in chat: "the
initial pruning, typing (both types) and topic'ing — both in vs out of CNfA, and
the specific topic in CNfA — has to happen in AF before AE ever gets a pdf to put
through the pipeline... the complete AF-AE-KA pipeline is imperfect and has legacy
elements... sync'ing it up, so that the right process happens at the right place
and it is recorded in the right dbase. Since we have AE pipeline stuff being put
back into AF the dbase should include provenance."*

## The governing principle

Article_Finder is the reservoir AND the gate. A PDF reaches Article Eater only
after AF has (in order) deduplicated it, verified its metadata, admitted it to the
field, assigned its CNfA topic, and typed it on both axes. AE extracts; KA
presents. Each process happens in exactly one place and is recorded in exactly one
database, and everything that flows backward (AE-derived labels re-entering AF)
carries provenance saying which system produced it, with what version, when.

## The intake gate, stage by stage (all in AF, all recorded in article_finder.db)

| # | Stage | What it does | Recorded as (articles/papers table) |
|---|---|---|---|
| 1 | **Dedup** | content-hash (sha256) + DOI + normalized-title match against everything already held | `dedup_status`, `duplicate_of`, `dedup_basis` |
| 2 | **Metadata completeness** | title/authors/year/DOI resolved (local sources first, then OpenAlex/S2 by DOI or gated title-match); a paper failing this goes to repair, not forward | `metadata_status`, per-field `*_source` |
| 3 | **Field admission (in vs out of CNfA)** | the panel-reviewed density identifier plus, eventually, the LLM judge; FIVE outcomes: in_field / borderline / pure_neuroscience / **pure_psychology** / out_of_field | `field_bucket`, `field_version`, receipts |
| 4 | **CNfA topic assignment** | which specific topic(s) within the field (acoustic, lighting, biophilia, wayfinding, ...) — the topic-bank machinery | `atlas_primary_topic` etc., version-stamped |
| 5 | **Typing, both axes** | method (empirical_quant/qual/mixed/reviews/meta/theoretical — theory REQUIRED for `theoretical`, per DK) and form (article/commentary/chapter/collection/thesis) | `method`, `form`, `typer_version`, tier, receipts |
| 6 | **Hand-off** | only papers passing 1–5 with tier CLEAN/GREY (or HARD after HITL) are packaged for AE | `ae_handoff_at`, bundle ref |

Every stage writes a version stamp and receipts, because the 2026-09 audit showed
that unstamped classification is unqueryable a season later.

**The pure_psychology bucket (David Kirsh, 2026-09-10, verbatim and binding):**
"pure_psychology is neither out_of_field nor borderline. It is an adjacent-evidence
bucket for studies of human cognition, emotion, behaviour, or clinical outcomes that
lack a substantive built, spatial, environmental, or ambient exposure. This
distinction prevents useful psychological theory and measurement papers from being
discarded while stopping them from masquerading as direct CNfA evidence."
Note: David's 2026-09-09 borderline rulings predate this bucket — some were forced
choices and are being re-keyed via the viewer's revision rail (key P).

**The methodology bucket (David Kirsh, 2026-09-10):** a second adjacent-evidence
bucket for papers not directly in CNfA but related, whose METHODS are of interest to
the platform — instruments, designs, analyses we may want to borrow. Neither
discarded nor counted as direct evidence. Field-admission outcomes are therefore
SIX: in_field / borderline / pure_neuroscience / pure_psychology / methodology /
out_of_field. Viewer key: M.

## Provenance for back-flow

AE outputs that re-enter AF (extraction-derived types, statistics-presence
signals, gold labels, KA-facing payload state) are stored with:
`provenance_system` (AE/AF/KA/human), `provenance_version` (script or model
version), `provenance_at`, and `provenance_receipt` (the evidence span or run
id). A value with no provenance is treated as legacy and scheduled for
re-derivation. Human rulings (David, Stephan) are provenance class `human` and
outrank machine values.

## The repair list (registered in TASKS.md; owners to be assigned)

1. **KA-ART import repair.** 190 of the corpus's out-of-field candidates are
   `KA-ART-*` imports with junk titles and no abstracts despite large text files —
   a degraded legacy import batch. Repair their metadata (stage-2 machinery) and
   re-run field admission before treating any as out of field.
2. **Corpus dedup.** The content-addressed drive release proves 1,760 paper ids
   resolve to 1,221 unique PDFs. Adjudicate the duplicate clusters
   (`data/topic_comparison/full1760_2026-09-09/duplicate_clusters.json`): one
   canonical id per cluster, others marked `duplicate_of` — in AF AND mirrored to
   AE supersessions. No deletions; RULE 0 applies.
3. **Field-identifier false positives.** Density dilution in very large documents
   (the METU city-planning theses) mislabels in-field work; normalize density by
   body-not-front-matter, or gate theses through the LLM judge.
4. **Metadata enrichment run.** OpenAlex enrichment works (spot-checked exact
   matches) but needs backoff/resume after rate-limiting; finish the 1,760 and
   feed the drive catalogue enrichment already requested of codex-ae.
5. **AF↔AE sync.** Migrate the intake gate's authoritative record INTO
   article_finder.db (stages 1–5 columns above); AE's lifecycle DB keeps
   pipeline state only; back-fill AF rows for the ~1,000 AE papers AF has no
   match for (AE→AF import with provenance `legacy_ae`).
6. **KA leg.** Confirm what KA consumes and from where; record its read surface
   in the canonical registries so the third leg is as explicit as the first two.
7. **Registry write-back.** The four corrected gold-20 type labels, and
   eventually typer-v1 labels that clear the blind-50 κ gate, land in the gold
   registry as receipted amendments — after, never before, validation.

## HITL economics — sequential stopping per field (David's ruling, 2026-09-11)

Human review budgets are NOT fixed per task; they emerge from a stop rule applied
per field. For each extracted/classified field: verify items sequentially; after
each, compute a confidence bound (Wilson) on the field's error rate; STOP when
the bound clears the field's release threshold, releasing the field to
spot-audit. Low-variance fields (subject N, year) clear in ~3-5 checks;
high-variance semantic fields (IV/DV, effect direction, findings) take ~10-15 —
David's numbers, derived rather than assumed. A disagreement re-opens the budget
AND retargets selection toward similar cases (the VOI scheduler's surprise
term). Second lever: run two independent extraction routes; auto-accept
agreement, route ONLY disagreements to humans. Three distinct sample sizes must
never be conflated: teaching a rubric (per-field, small), certifying an error
rate before registry write-back (statistical, ~50 for ±10%), and the abstention
queue of a weak mechanical layer (an engineering debt the judge absorbs, not a
human budget).

## Ambiguity routing and conjecture adjudication (David's proposal, 2026-09-11; literature-checked)

Three additions to the HITL economics above, each grounded in an established
literature — we are not first, and the prior work adds guardrails.

**1. Ambiguity is a routing signal, not a failure.** When a field (e.g.
direction of effect) cannot be determined because the source language is odd,
badly written, or syntactically ambiguous, that item is a high-value human
touchpoint. The uncertainty literature distinguishes two causes that must be
routed differently: *source ambiguity* (aleatoric — the text itself
underdetermines the answer; irreducible by a better model) and *model
uncertainty* (epistemic — the model lacks skill or context; reducible).
Operationalization with our dual-route design: both routes uncertain but
proposing DIFFERENT readings → source ambiguity, route to human WITH the
competing readings shown; one route confident, other abstaining → model
uncertainty, first try context expansion / the stronger judge, humans only if
that fails. Each routed item carries `ambiguity_type` so the two queues are
separately measurable.

**2. Conjecture + evidence adjudication (the new viewer mode).** For routed
items the machine presents 2–3 candidate values, each with its quoted
span(s) and a one-line reason; the human picks one, or rejects all and
supplies the value. Judging presented evidence is faster than re-deriving
from the paper (verification asymmetry; the rationale literature further
shows span-marking is often a better use of annotator time than more
labels). Rules, from the literature's failure modes:
- *Warrant, not relevance:* the prompt to the human is "does this span
  WARRANT this reading," never "is this span related" — topical relevance
  without warrant is the known failure of citation-style verification.
- *Anchoring guardrail:* presented conjectures bias humans toward
  acceptance. Adjudication mode is for production throughput ONLY — never
  for blind validation batches (the κ gate stays blind), and ~10–15% of
  adjudicated items are re-judged blind as a standing acceptance-bias audit.
- *Reject-all is a disagreement:* it re-opens the field's sequential-stop
  budget and feeds the VOI surprise term, same as any human–machine
  disagreement.
- The full paper stays scrollable beneath the conjectures (the one rule
  about context); spans are anchors, not boundaries.

**3. Context expansion learned from humans.** Sometimes local text is
ambiguous but a larger window resolves it. Every adjudication logs whether
the human ruled from the offered spans or scrolled beyond them, and which
passage they finally marked (`context_expansion` event: field, offered
spans, used span, section, distance). Aggregated per field, these events
become expansion policies (e.g. direction-of-effect routinely needs the
stats sentence PLUS its results paragraph PLUS the matching discussion
paragraph). This mirrors the "sufficient context" lens from the RAG
literature: classify each failure as evidence-insufficient (expand the
window) vs evidence-unused (fix the model) before spending human time.

## Boundaries

This spec records the target architecture and repairs; it does not claim the
migration is done. Current reality: the intake gate exists as validated scripts
(typer_v1, field identifier, dedup map, enrichment) run OUT of band; the
authoritative columns above do not all exist in article_finder.db yet. The
blind-50 κ gate remains the validation checkpoint before any corpus-wide label
write-back anywhere.
