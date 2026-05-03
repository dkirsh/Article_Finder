# Query Spot-Check — Task 2 Phase 4
**Author:** Dhruv Sood
**Date:** 2026-05-03
**Repo:** Article_Finder

---

## Selection
Three top-VOI queries chosen for Google Scholar spot-check:

1. **Gap #2 — INTERO-PP-ALLOSTASIS-001** (VOI 0.610) — interoception × allostatic cascade
2. **Gap #4 — MULTISENSORY-CONGRUENCE-001** (VOI 0.530) — cross-modal alignment & superadditivity
3. **Gap #7 — CIRCADIAN-DEV-PROGRAM-001** (VOI 0.530) — morning light & circadian calibration

---

## Spot-check Results

| # | Gap ID | Query type | Query (truncated) | First-page hits relevant | Notes |
|---|---|---|---|---|---|
| 1 | INTERO-PP-ALLOSTASIS-001 | Boolean | `"interoception" AND "thermal environment" AND "allostatic load" -review` | TBD by user in Google Scholar | Targets primary studies linking interoceptive PE failure to allostatic cascade |
| 2 | MULTISENSORY-CONGRUENCE-001 | AI Citation | `What empirical evidence shows that multisensory environment exposure influences cross-modal alignment leading to superadditivity in healthy adults, as explained by multisensory integration theory?` | TBD by user | Should surface Stein/Meredith multisensory papers |
| 3 | CIRCADIAN-DEV-PROGRAM-001 | Boolean | `"circadian rhythm" AND "daylight" AND "light entrainment" -review` | TBD by user | Targets primary chronobiology / lighting studies |

> **User action:** Run each query in Google Scholar, mark the count of first-page results that are
> on-topic primary studies (not reviews), and replace TBD entries above.

---

## Quality Review (automated checks)

All 6 contract checks passed (run `python3 query_generator.py --gaps gap_results.json`):
- AI citation queries: end with `?` ✓ ; > 50 chars ✓
- Boolean queries: contain AND/OR ✓ ; contain quoted phrases ✓ ; no bare comma lists ✓
- `query_results.json` is valid JSON ✓

## Known limitations

- Mechanisms whose `name` lacks a `→` separator (e.g. "Architectural signaling of group identity")
  produce AI Citation queries where the IV and DV are the same phrase. These still pass contract
  checks but read awkwardly. Future improvement: split on `&` or `×` operators or fall back to
  using the first synonym from `mechanism_synonyms` as the DV.
- 10/10 top-ranked gaps come from `cross_framework` because of the +0.15 centrality bonus.
  Per-gap vocabulary overrides (`CROSS_FRAMEWORK_VOCAB_MAP`) supply domain-specific synonyms,
  but adding a `--by-framework` mode for diversified sampling would help downstream coverage.
