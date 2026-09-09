# Gold-20 adjudication — David Kirsh, 2026-09-09

David reviewed the 20-paper gold evaluation set
(`data/topic_comparison/gold_sample_20_2026-08-29_r2/comparison.db`) by title, with
abstract checks on the two suspect labels. Rulings given in chat, 2026-09-09;
recorded here by Fable. The certified gold registry has NOT yet been amended —
see "What remains" below.

## Removed from the evaluation set (6)

David: "the following should be removed." List positions from the 2026-09-09 title
listing, alphabetical by paper id:

| # | ID | Title (short) |
|---|----|----|
| 2 | PDF-0061 | Embodied Learning Using a Tangible User Interface |
| 7 | PDF-0176 | Wayfinding: A Simple Concept, a Complex Process |
| 9 | PDF-0267 | ROCs in rats? Response to Wixted and Squire |
| 10 | PDF-0396 | Architectural Lessons From Environmental Psychology |
| 19 | PDF-1303 | Preferences for and attitudes towards street flowers and trees in Sapporo |
| 20 | PDF-1431 | Neurociencia del aprendizaje y la poiesis somática de la arquitectura |

## Retyped (2) — abstract-confirmed

Both were flagged from titles alone, David concurred, and the abstracts settle it.
The current classifier's own title_abstract prediction agreed in both cases.

- **PDF-0404**: gold said `theoretical` → **empirical_research**. Abstract: EEG as a
  physiological evaluation tool, three VR soundscape environments, measured
  psycho-physiological responses.
- **PDF-0446**: gold said `qualitative` → **empirical_research**. Abstract: n = 27,
  17 lighting conditions (7 illuminance × 7 CCT combinations), emotional valence,
  arousal, and adjustment-behavior measures.

## The surviving 14-paper set

PDF-0040, PDF-0062, PDF-0071, PDF-0108, PDF-0154, PDF-0196, PDF-0404*, PDF-0446*,
PDF-0461, PDF-0466, PDF-0674, PDF-0802, PDF-0839, PDF-1106 (* = with the retyped
gold label above).

## Vocabulary drift (must fix before any κ)

Gold labels use `qualitative`; the classifier taxonomy uses `qualitative_research`.
Raw comparison scores every such paper as a disagreement. Unify before scoring.

## Facts about the 2026-08-29 comparison run (verified 2026-09-09)

- The run classified all 20 LIVE via `atlas_shared.classifier_system
  .AdaptiveClassifierSubsystem` (three evidence modes) — not by copying stored rows.
- `atlas_shared/src` has not changed since commit b261b89 (2026-08-15), so the
  Aug-29 run used what is still the CURRENT classifier.
- That current classifier performed poorly: title_abstract mode returned `unknown`
  for 11 of 20; the run summary records keyword_enriched article-type accuracy of
  2/20 — and two of its scored "errors" (PDF-0404, PDF-0446) were cases where the
  classifier was right and the gold wrong.

## What remains

1. Amend the certified gold surfaces (the v7 gold registry's `article_type` for
   PDF-0404 and PDF-0446) as a receipted AE-lane change, and rebuild the comparison
   set as the 14-paper version.
2. Only after that: score the classifier against the corrected 14, report κ to
   David, and only on his RATIFY run any corpus-wide re-typing.
