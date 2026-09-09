# Typer v1 + field identifier — full corpus run (1,760 papers)

*2026-09-09, Fable, on David's charge ("run it on 1760... pure neuroscience in a
different bucket... build a topic identifier, panel help, run both"). Script:
`scripts/typer_v1.py`; panel: `docs/PANEL_REVIEW_TOPIC_IDENTIFIER_2026-09-09.md`;
full outputs: `data/topic_comparison/full1760_2026-09-09/` (results JSONL + CSV +
summary.json; data/ is git-excluded — rides the next DB-snapshot sync).*

## Calibration receipt, then the run

v1 mechanizes the pilot's judge rules and, after five generic fixes, scores
**14/14 family agreement against David's final gold-20 rulings** (from 8/14 before
the fixes — every earlier miss was an abstention, none a wrong label). Only then
was it run on every paper with a production PDF.

## Corpus results (1,760 papers)

| Method family | n | | Field bucket | n | | Tier | n |
|---|---|---|---|---|---|---|---|
| empirical | 995 | | in_field | 1,186 | | CLEAN | 347 |
| review | 338 | | out_of_field_candidate | 382 | | GREY | 1,106 |
| theoretical | 162 | | borderline | 142 | | HARD | 307 |
| OPEN (abstained) | 265 | | **pure_neuroscience** | **50** | | | |

David's suspicion that "many are not in this topic" is confirmed and quantified:
roughly one paper in five (382) shows essentially no environmental-design language
anywhere in its text, and another 142 sit near the boundary. The out-of-field
sample reads as expected — a maritime-psychology text, a physics paper on
space-time curvature and spin-1/2 particles, education/HCI experiments, pure
visual-perception psychophysics.

## The pure-neuroscience bucket (50 papers, for hand review)

The full id list is in `summary.json` (`pure_neuroscience`). Spot-checked titles
behave: macaque opioid-receptor mapping, the brain basis of misophonia, neural
mechanisms of material perception — neuro-dense and environment-silent, exactly
the definition the panel set.

## Boundary caveats, stated before anyone acts on the lists

- **These buckets are candidates for David's eyes, never deletions.** RULE 0
  applies; nothing has been removed or relabeled in any registry.
- The neuro/out-of-field boundary is porous by design: PDF-0267 (rat ROC memory)
  landed out_of_field rather than pure_neuroscience because its vocabulary is
  memory-psychology, not imaging. Both buckets reach the same hand review.
- Two bucket calls that touch David's own earlier rulings deserve his attention:
  PDF-0003 ("Urban Architecture: A Cognitive Neuroscience Perspective") and
  PDF-0723 ("Neuroscience and architecture...") sit in the neuroscience bucket at
  env-density just under threshold — arguably neuroarchitecture, i.e., ours. And
  PDF-0040 (science-museum exhibit design), which David KEPT in the gold-20, is
  flagged out_of_field — a live disagreement that should calibrate the threshold.
- 265 abstentions (15%) are honest OPENs, not errors — thin OCR, collection
  volumes, silent texts; they sit in HARD for the LLM/human layers.
- 1,000 papers currently lack a resolved title in the output (the classification
  is text-based and unaffected, but hand review wants titles — the join to
  `pdf_corpus_inventory` is the known fix).
- The blind-50 protocol is untouched: sealed verdicts stayed sealed; this run
  wrote only to its own directory.

## What consumes this next

1. David hand-reviews the 50-paper neuroscience list and (as bandwidth allows)
   the out-of-field list; the two near-boundary neuroarchitecture papers first.
2. The tier column feeds `hitl_scheduler.py` for production HITL (CLEAN
   auto-accept + spot-check; GREY assisted; HARD to Stephan/David).
3. κ from the blind-50 human round remains the formal validation gate before any
   registry write-back of these labels.
