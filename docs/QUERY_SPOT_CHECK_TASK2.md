# Query Spot-Check — Task 2 Phase 4
**Author:** Dhruv Sood
**Date:** 2026-05-04
**Repo:** Article_Finder

---

## Honesty rule

The rubric requires **at least three queries manually tested in Google
Scholar with first-page result titles recorded**. This page records the
status of that test honestly:

| Run state | Mark |
|---|---|
| Test was actually run, results pasted | filled rows below |
| Test was not run | rows say `NOT RUN` |

The first run of this submission has **NOT RUN** rows because Google
Scholar testing is a manual artifact and the queries are paste-ready
below. When the user runs them, replace the relevant cells.

---

## Three queries to paste into Google Scholar

Open `https://scholar.google.com/` and paste each query verbatim.

### Query 1 — INTERO-PP-ALLOSTASIS-001 (Boolean, VOI 0.61)

```
("Interoceptive PE failure" OR "interoception") AND ("thermal environment" OR "indoor climate") AND ("allostatic cascade" OR "allostatic load") -review
```

Targets: primary studies linking interoceptive prediction-error failure to
allostatic-load accumulation in thermally-variable indoor environments.

### Query 2 — MULTISENSORY-CONGRUENCE-001 (AI Citation, VOI 0.53)

```
What empirical evidence shows that multisensory environment exposure influences cross-modal alignment leading to superadditivity in healthy adults, as explained by multisensory integration theory?
```

Targets: empirical multisensory integration / superadditivity papers in
built-environment contexts.

### Query 3 — CIRCADIAN-DEV-PROGRAM-001 (Boolean, VOI 0.53)

```
("Morning light" OR "circadian rhythm") AND ("daylight" OR "natural light") AND ("circadian calibration" OR "light entrainment") -review
```

Targets: primary chronobiology studies on morning-light entrainment of
circadian rhythms in real-world settings.

---

## Spot-check results table

| # | Gap ID | Query type | First-page hits relevant? | Top result title | Notes |
|---|---|---|---|---|---|
| 1 | INTERO-PP-ALLOSTASIS-001    | Boolean      | NOT RUN | NOT RUN | paste Query 1 above |
| 2 | MULTISENSORY-CONGRUENCE-001 | AI Citation  | NOT RUN | NOT RUN | paste Query 2 above |
| 3 | CIRCADIAN-DEV-PROGRAM-001   | Boolean      | NOT RUN | NOT RUN | paste Query 3 above |

**To complete:** for each row, run the query in Google Scholar, write
`Yes` / `Partial` / `No` in column 4, paste the top result's title in
column 5, and (optionally) note anything in column 6.

---

## Automated quality review (already passed)

`python3 query_generator.py --gaps gap_results.json` final block:

```
Contract validation:
  PASS  ai_citation ends with ?
  PASS  ai_citation > 50 chars
  PASS  boolean has AND/OR
  PASS  boolean has quoted phrase
  PASS  no bare comma list
  PASS  output JSON valid
ALL PASS
```

`query_quality_flags` per gap (post-fix for degenerate IV==DV):

| gap_id | flags |
|---|---|
| SOCIAL-AFFILIATION-002         | `degenerate_dv` (mechanism is a single noun phrase; mediator-fallback applied — query reads grammatically) |
| INTERO-PP-ALLOSTASIS-001       | clean |
| SOCIAL-ACOUSTIC-COUPLING-001   | clean |
| MULTISENSORY-CONGRUENCE-001    | clean |
| COMPLEXITY-LOAD-001            | `degenerate_dv` (single noun phrase; mediator-fallback) |
| WAYFINDING-002                 | `degenerate_dv` (single noun phrase; mediator-fallback) |
| CIRCADIAN-DEV-PROGRAM-001      | clean |
| THERMAL-SOCIAL-WARMTH-001      | clean |
| EMOTION-REGULATION-001         | `degenerate_dv` (single noun phrase; mediator-fallback) |
| OLFACTORY-SPATIAL-MEMORY-001   | `degenerate_dv` (single noun phrase; mediator-fallback) |

`degenerate_dv` is documented in the contract enum (Contract 2 §6). The
mediator-fallback in `generate_ai_citation` produces a grammatical
sentence even when source equals destination, so these flags are
informational, not blocking.

---

## Known limitations

- Mechanisms whose `name` lacks a `→` separator (e.g. "Architectural
  signaling of group identity") still trigger `degenerate_dv` — the
  mediator-fallback uses the first synonym from `mechanism_synonyms` so
  the sentence stays grammatical, but the underlying gap shape is still
  a single noun phrase rather than a source→destination chain.
- 10/10 top-ranked gaps come from `cross_framework` because of the +0.15
  centrality bonus. Per-gap vocabulary overrides (`CROSS_FRAMEWORK_VOCAB_MAP`)
  supply domain-specific synonyms, but adding a `--by-framework` mode
  for diversified sampling would help downstream coverage.
- Corpus-awareness pass: `pdf_corpus_inventory/latest.csv` is not present
  on this checkout (the lifecycle DB ships empty). The generator logs a
  stderr note and skips the corpus check. When the inventory file is
  available, queries that target an already-owned paper get the
  `targets_owned_paper` flag; the search runner can then skip them.
