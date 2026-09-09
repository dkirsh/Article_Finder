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
| 3 | **Field admission (in vs out of CNfA)** | the panel-reviewed env-vs-neuro density identifier plus, eventually, the LLM judge; four outcomes: in_field / borderline / pure_neuroscience / out_of_field | `field_bucket`, `field_version`, receipts |
| 4 | **CNfA topic assignment** | which specific topic(s) within the field (acoustic, lighting, biophilia, wayfinding, ...) — the topic-bank machinery | `atlas_primary_topic` etc., version-stamped |
| 5 | **Typing, both axes** | method (empirical_quant/qual/mixed/reviews/meta/theoretical — theory REQUIRED for `theoretical`, per DK) and form (article/commentary/chapter/collection/thesis) | `method`, `form`, `typer_version`, tier, receipts |
| 6 | **Hand-off** | only papers passing 1–5 with tier CLEAN/GREY (or HARD after HITL) are packaged for AE | `ae_handoff_at`, bundle ref |

Every stage writes a version stamp and receipts, because the 2026-09 audit showed
that unstamped classification is unqueryable a season later.

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

## Boundaries

This spec records the target architecture and repairs; it does not claim the
migration is done. Current reality: the intake gate exists as validated scripts
(typer_v1, field identifier, dedup map, enrichment) run OUT of band; the
authoritative columns above do not all exist in article_finder.db yet. The
blind-50 κ gate remains the validation checkpoint before any corpus-wide label
write-back anywhere.
