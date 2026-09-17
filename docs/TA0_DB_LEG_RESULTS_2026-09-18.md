# TA-0 database leg — results (run where the databases live, 2026-09-18)

**Run against:** `Article_Finder_v3_2_3/data/article_finder.db` and
`Article_Eater_PostQuinean_v1_recovery/data/article_eater_lifecycle.db`, both opened
read-only (`file:...?mode=ro`). Checks taken verbatim from Tanishq's
`docs/audits/TA0_RECONCILIATION_VERIFICATION_2026-09-15.md` (his branch
`tanishq/ae-scientific-extraction-2026-09-11`), plus the PDF-0164 question his file
leg posed. Runner: Fable lane, on David's machine.

## The PDF-0164 answer: only the latest

`field_rulings_human` holds ONE ruling for PDF-0164 in both databases:
`pure_psychology`, ruled_at `2026-09-10T09:31:00.836Z`. The earlier `borderline`
ruling of `2026-09-09T18:21:52.468Z` is not in either database, and the schema
(`paper_id, field, cluster_head, ruled_by, ruled_at, provenance, imported_at`) has no
history rows and no current-state marker. Tanishq's formulation is exactly right: the
ingestion was faithful to its source, and the source — a latest-state snapshot — had
already discarded the earlier state. The database inherits a gap it cannot see. The
sole surviving record of the borderline ruling is the checkpoint file
(a04a5803…), now committed on Tanishq's branch.

Context that explains, without excusing, the overwrite: the 09:31 timestamps on
PDF-0164/0261/0262 are consecutive — the morning of the 10th is when the two new
categories (pure_psychology, methodology) were added mid-session, and David swept
earlier borderline/out judgments against the enlarged vocabulary. A legitimate
re-judgment; a storage format that forgets.

## Check 7, the rest: PASS, with receipts

| Check | article_finder.db | article_eater_lifecycle.db |
|---|---|---|
| rows / distinct paper_id | 414 / 414 | 414 / 414 |
| provenance | all 414: "hitl_field_viewer exports through 2026-09-10 (human, outranks machine)" | same |
| ruled_by | David Kirsh only | same |
| imported_at | single batch, 2026-09-10T20:51:04+00:00 | same |
| table content sha256 (ordered dump of paper_id, field, cluster_head, ruled_by, ruled_at, provenance) | f66cb110d0765693… | f66cb110d0765693… (IDENTICAL) |

## The 414 expansion — now verified (was carried as stated)

The duplicate-cluster mapping is not a separate excluded file; it is embedded in the
table as `cluster_head`. Verified: 258 distinct cluster_head values; all 258 are
autosave paper_ids (258/258); zero rows whose `field` disagrees with their cluster
head's autosave ruling; zero rows whose cluster_head falls outside the 258. So
414 = the 258 rulings expanded over their clusters, faithfully.

## Boundary

Append-only behaviour of the ingestion STEP is consistent with a single-batch
imported_at and one row per paper, but with a one-shot import there is no second write
to test against; what is established is content fidelity (source → table) and
cross-database identity, not the ingester's behaviour under a future second import.
The history gap is upstream of the ingester, in the autosave format.
