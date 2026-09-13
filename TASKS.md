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

| T11 | **Bib rejoin, properly**: re-parse the Zotero BibTeX export with a real parser (bibtexparser), and accept a join ONLY where its title agrees with the gold-registry or text title (the 2026-09-09 naive join misattached 43% and is quarantined). | 2026-09-10 | David caught wrong titles in HITL |
| T12 | **APA + abstract completion on clean provenance**: refetch the 511 SUSPECT-flagged APAs from catalogue/validated DOIs; derive DOIs for the ~700 DOI-less papers via OpenAlex matched on TRUSTED titles (backoff/resume); same route for missing abstracts. | 2026-09-10 | David: "APA is essential" |
| T13 | **Dedup execution (extends T2)**: assign canonical id per sha-cluster, write supersessions in AE + duplicate_of in AF, then a referential-integrity sweep so no surface references an absent or superseded id. | 2026-09-10 | David: "prune the pdfs correctly... make sure no errors arise" |
| T14 | **Dyadic field labels downstream**: field_secondary now flows from the viewer; add the column to field_rulings_human in both DBs and propagate on next merge. | 2026-09-10 | David's (primary+secondary) vector design |
| T15 | **Conjecture-adjudication HITL mode**: extractor emits 2–3 candidate values + spans + reasons on ambiguity-routed items (`ambiguity_type` source vs model per dual-route pattern); viewer mode with 1/2/3/X keys, warrant-not-relevance prompt, context_expansion logging; 10–15% blind re-judge as acceptance-bias audit; never used for κ-gate batches. | 2026-09-11 | David's proposal, literature-checked; spec §ambiguity routing |
| T16 | **Efficient κ-pilot pack — BUILT, awaiting different-lineage review** (codex-ae) before the ZIP goes to Stephan. Pack: `_shared_artifacts/AE_HITL/AE_KAPPA_PILOT_FROZEN_20_PLUS_DEMO_HITL_R3_EFFICIENT_2026-09-11` (scientific hash acd779c4… UNCHANGED; manifest 0f95a748…). Route B = 5 blind sonnet extractors over docling; agreement 10–41% per stratum (route-A pathology documented in receipts/route_b_diff_receipt.json: d=57462037, "WMG et al.", template DV lists). Stop rule: one-sided-80% Wilson, release ≤0.15 mech/≤0.10 sem, fail-fast condemn LB≥0.35, 15% seeded audit, re-open on audit error. Node suite 20/20 incl. negative controls; live-browser entry + release + re-open verified. Sim load ~116/287. | 2026-09-11 | Built this session; REVIEW_REQUEST on AE taskboard |

| T17 | **URGENT — Title-vs-document sweep, corpus-wide, INCLUDING trusted rows**: 322 paper_bibliographic rows carry a trust label (gold_registry/validated) contradicted by their source lineage (oa_title_match / QUARANTINED). David caught PDF-0814 live: DOI right, title from a sibling paper via oa_title_match, trust said gold. Sweep all 1,760: extract document front-matter title (\title{} / first heading), jaccard vs DB title; disagreements get title_trust downgraded + document title recorded; NO trust label may survive that its source lineage contradicts. Blind-50 batches already swept (10/50 display titles corrected against documents, 2026-09-12). Batch-build scripts gain a mandatory document-title check before any batch is served to a human. | 2026-09-12 | David: "it was never tested for title accuracy" — correct; the audit tested registry agreement, never the document itself |

| T18 | **VLM route over page images for typing/topicing (route C)**: David's ruling — sometimes the best evidence for type/topic is visual (tables, figures, layout); add a vision-language pass over page images as a third extraction route feeding the dual-route disagreement machinery. Substrate exists: AE κ-pack exporter already produces page images + figure/table crops (527 pages, 180 fig / 113 table crops for 23 papers); generalize that exporter corpus-wide, then a VLM judge on the crops for papers where text routes disagree or text is degraded (KA-ART candidates first). | 2026-09-13 | David: "sometimes the best method would be through using VLM and page images" |

| T19 | **Human-factors gate for every HITL surface** (David's ruling 2026-09-13: integrity review alone is not enough). Before any batch/interface is served to a human, a reviewer walks it AS A FIRST-TIME USER against a written checklist: (1) system status always visible at any scroll (Nielsen 1 — the buried save note); (2) content in the reader's format, not the pipeline's (Nielsen 2 — raw LaTeX/OCR); (3) recognition over recall — APA/venue/metadata present at the point of judgment; (4) error prevention — every required ruling expressible without fighting validation (the off-topic case); (5) 1–2 keystrokes per judgment, auto-advance, no flow breaks; (6) display metadata document-verified (T17 check); (7) failure modes triggered, not assumed (kill the server mid-save, judge with nothing selected). Checklist doc + apply to R3 pack as rung two after the Opus integrity verdict. | 2026-09-13 | Every defect David caught 09-12/13 maps to a known heuristic; the gate makes the checklist run before the human does |

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
