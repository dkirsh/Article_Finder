# TASKS.md — Article_Finder

*Last updated: 2026-09-09. Created to register the AF-first pipeline repairs
(David's architectural ruling, chat 2026-09-09; spec:
`docs/AF_FIRST_PIPELINE_SPEC_2026-09-09.md`).*

## Pending

| ID | Task | Added | Context |
|----|------|-------|---------|
| T1 | **KA-ART import repair**: 190 `KA-ART-*` corpus entries have junk titles and no abstracts despite large text files; repair metadata, then re-run field admission. Never judge them out-of-field in this state. | 2026-09-09 | Surfaced during the corpus-wide field run |
| T2 | **Corpus dedup adjudication**: 349 sha256-identical clusters (886 papers, 537 redundant ids) in `data/topic_comparison/full1760_2026-09-09/duplicate_clusters.json`. One canonical id per cluster, others `duplicate_of`; mirror to AE `paper_supersessions`. No deletions (RULE 0). | 2026-09-09 | Content-addressed drive release proved 1,760 ids = 1,221 PDFs |
| T3 | **Field-identifier fix**: density dilution mislabels very large in-field documents (METU theses); normalize by body region or route theses to the LLM judge. | 2026-09-09 | David flagged; confirmed on PDF-0308/0343 |
| T4 | **Finish OpenAlex metadata enrichment**: add backoff/resume (rate-limited at 1,424 errors on first full attempt); output feeds the drive-catalogue enrichment codex-ae was asked for. | 2026-09-09 | `scripts/enrich_metadata_openalex.py`; matches spot-checked exact |
| T5 | **Intake-gate columns in article_finder.db**: dedup/metadata/field/topic/typing columns with version stamps + receipts + provenance (system, version, at, receipt) per the spec; AF becomes the authoritative record BEFORE AE hand-off. | 2026-09-09 | Spec §intake gate + §provenance |
| T6 | **AE→AF back-fill with provenance**: import rows for the ~1,000 AE papers AF lacks, provenance class `legacy_ae`. | 2026-09-09 | Reservoir completeness |
| T7 | **KA leg audit**: record what Knowledge_Atlas consumes and from where in the canonical registries. | 2026-09-09 | Third pipeline leg currently undocumented here |
| T8 | **Gold-registry write-back** of the four corrected gold-20 labels (receipted, AE lane), and typer-v1 labels only after the blind-50 κ gate. | 2026-09-09 | Validation before write-back |

## In Progress

| ID | Task | Started | Notes |
|----|------|---------|-------|
| T9 | Blind-50 human round (Stephan/David) → κ vs sealed machine verdicts | 2026-09-09 | Batch ready at `data/topic_comparison/blind50_2026-09-09/` |
| T10 | David's hand review: 50-title out-of-field list (delivered in chat), pure-neuroscience bucket | 2026-09-09 | Duplicate clusters overlap this list |

## Completed

| ID | Task | Completed | Outcome |
|----|------|-----------|---------|
| C1 | Pilot typer + gold-20 adjudication (4 labels corrected, 6 field removals) | 2026-09-09 | 14/14 after David's rulings |
| C2 | Typer v1 + panel-reviewed field identifier, corpus run on 1,760 | 2026-09-09 | docs/TYPER_V1_CORPUS_RUN_2026-09-09.md |
| C3 | HITL apparatus: viewer, Stephan onboarding, VOI scheduler | 2026-09-09 | commit c9b765a |
