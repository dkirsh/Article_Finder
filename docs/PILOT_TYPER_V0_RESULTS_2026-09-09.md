# Pilot typer v0 — results on the gold-20

*2026-09-09. Fable, at David's direction ("build the pilot and run it on the 20").
Script: `scripts/pilot_typer_v0.py`; full evidence and verdicts:
`data/topic_comparison/pilot_typer_v0_2026-09-09/{results.json, judge_verdicts.json}`
(data/ is git-excluded — the files live on David's Mac and in the next DB-snapshot sync).
Provenance: written under atlas_shared SCIENCE_COMMUNICATION_NORMS.*

## What was built

The two-axis, layered design from the 2026-09-09 discussion. Mechanical layers run in
script: structural detectors over the full text AE already holds (methods headers,
inferential statistics, participant counts, PRISMA/search-strategy, qualitative-methods
and review language — each hit recorded WITH its text span as a receipt), AE's own
extraction artifacts, Semantic Scholar publicationTypes by DOI, and the OpenAlex block
the Aug-29 harness had already stored. A precedence combiner labels what it can and
says OPEN where it can't. The LLM layer was applied by Fable reading each paper's
evidence packet, bound by the receipt rule: no verdict without quoted in-text spans,
citation-context matches discounted, abstention allowed.

## Headline result

*(Updated after David's second-round rulings, later on 2026-09-09.)* Both of the
pilot's receipted challenges were upheld: David ruled PDF-0154 quantitative and
PDF-0461 narrative_review — the labels the pilot had assigned. Against his final
gold, the pilot agrees on **14 of 14 kept papers, zero unknowns**.

As first scored, against the pre-ruling corrected gold:

- **12 of 14 agree** at the family level; **zero unknowns**.
- The two disagreements are not typer failures on their face — both are **receipted
  challenges to the gold label**, queued for David:
  - **PDF-0154** (Color-Emotion Associations): gold `qualitative`, but "Fifty people
    ... participated" and "between age (P=0.029), gender (P=0.031)" read
    empirical-quantitative.
  - **PDF-0461** (Environmental Stressors): gold `qualitative`, but the text says
    "The present literature review discussed the harmful impacts..." and Semantic
    Scholar types it Review; its participants span is a cited study's class sizes.
- Baseline on the same 20: the production typer returned `unknown` for 11 of 20 and
  scored 2/20 in keyword mode.

On the six papers David removed, run as a hard probe: five got sensible labels —
including PDF-0267 typed `theoretical` with form `commentary` ("Response to Wixted
and Squire"), which the old flat vocabulary could not express — and one (PDF-1431,
Spanish, documentary grounded theory) drew an honest low-confidence abstention
routed to HITL.

## What the judge layer earned

The mechanical layers alone left 7 of 20 OPEN and misfired three times on precedence:
PRISMA-ish spans from an *embedded literature-review section* outranked a 142-participant
ANOVA study (PDF-0108), and meta-analysis language *in the references* mislabeled two
papers (PDF-0404, PDF-0176). The judge corrected every one of these using two rules
worth building into v1: own-data evidence dominates embedded-section evidence, and a
span describing a cited study's data is not evidence about this paper.

## The third axis (David, after the run)

David: "sometimes the pdfs are not even in the right field. many of my rejections were
topic based — ie what field." So the removals were largely **domain-admission**
rejections, and the design needs a third axis alongside method and form: field
relevance. Judge's reading of the removed six at title/abstract level: PDF-0061
(education/HCI), PDF-0267 (rat memory research), and PDF-1431 (architecture pedagogy)
are out of field; PDF-0176, PDF-0396, and PDF-1303 sit nearer the boundary. Two
consequences: the v1 typer emits method + form + field; and the certified corpus
itself contains out-of-field papers, so a **corpus-admission sweep of the 1,760** is a
companion task to the re-typing.

## Boundaries

The judge was Fable in-context, not yet a scripted API call — v1 scripts the same
rubric and receipts so the layer runs unattended. n = 20, with gold still under
adjudication on two labels. Semantic Scholar was unavailable for 2 papers (HTTP
errors); the pilot proceeded without it, as designed. Field-axis readings above are
title/abstract-level judgments, not full-text adjudications.

## Next steps

1. David adjudicates PDF-0154 and PDF-0461 (the two receipted gold challenges).
2. v1: encode the two judge rules mechanically where possible, script the LLM layer
   (same rubric, receipts required), add the field axis.
3. Fresh stratified ~50-paper sample, blind spot-check by David, κ against his labels.
4. On RATIFY: corpus-wide run over the 1,760 (and AF's 16k), version-stamped, plus
   the field-admission sweep.
