# T16 completion — the efficient κ-pilot pack (R3)

**Date**: 2026-09-11 · **Built by**: Fable, under David Kirsh's same-day ruling ("do the
efficient version") · **AF commit**: fbc969c · **Board**: DONE + REVIEW_REQUEST rows
2026-09-11T15:48:36Z, _control 69a5915

## Summary

The frozen kappa-20 review pack now runs David's sequential-stopping economics inside the
pilot itself. A second, blind extraction route (five Sonnet subagents reading only docling
text) was diffed against the pack's candidate projections; questions arrive
disagreement-first, papers ordered by disagreement mass, and each field switches off once
the reviewer's judgments bound its error rate — in either direction. Frozen scientific
content is untouched: scientific_content_sha256 equals the ratified
acd779c44ad594ca6fba24b350a0cb0711eb0e79805dc8c4009c5935de95081b, scientific_inputs_changed
false, per the R2 precedent.

## Artifacts (all verified this session)

| Artifact | Location |
|---|---|
| R3 pack (1,424 files) | `/Users/davidusa/REPOS/_shared_artifacts/AE_HITL/AE_KAPPA_PILOT_FROZEN_20_PLUS_DEMO_HITL_R3_EFFICIENT_2026-09-11` — manifest sha256 0f95a748198fef2051651efd29f380f76f62b8a1748a13273e800c64cb102bf1 |
| Transport ZIP | same dir, `.zip`, sha256 f7dc5a74ba5576c6e9adae255eef74c283d143d8536123a0569ccb2bca3d181d |
| R3 queue logic + overlay + diff receipt | `/Users/davidusa/REPOS/Article_Finder_v3_2_3/apps/kappa_review_r3/` |
| Builder scripts + test suite | `/Users/davidusa/REPOS/Article_Finder_v3_2_3/scripts/kappa_r3_diff_and_rank.py`, `revise_kappa_r3_efficient.py`, `test_kappa_r3_queue_logic.js` |

## Design decisions

1. **One-sided 80% Wilson bound**, not 95%: David's budget intuition (3–5 mechanical,
   10–15 semantic) calibrates exactly to it; the pilot is triage, and certification-grade
   95%/n≈50 stays at registry write-back (three-regimes distinction in the AF-first spec).
   Zero-error release lands at n=5 (mechanical, ≤0.15) and n=7 (semantic, ≤0.10).
2. **Fail-fast condemnation** (lower bound ≥ 0.35): a field proven broken stops consuming
   the reviewer as fast as a field proven clean; its remedy is re-extraction. Added after
   the route diff showed agreement of only 10–41% per stratum.
3. **Blindness preserved**: the pack carries ranks and config only; route-B values live
   solely in the repo-side receipt. The reviser refuses a payload containing route
   values (leak guard, attacked in review).
4. **Seeded 15% audit retention** with automatic re-open: a settled stratum keeps
   deterministic spot-audit items; one error there re-raises the bound and restores the
   full queue. Verified live (release at 5 clean → 11 skipped; one poisoned audit item →
   287 restored).
5. **Ordering-bias honesty**: disagreement-first prefixes overstate stratum error rates,
   so "condemned" certifies the *flagged* items (the re-extraction queue); population
   estimates are computed post-hoc with the audit items.

## Testing

Node suite 20/20, negative controls included (2-errors-in-10 must stay open; audit error
must re-open; no-overlay fallback must reproduce R2's order; demo items never feed the
bound). Live-browser entry test on the built pack: start flow, 13 strata chips, dynamic
release/re-open, export carries `strata_stop_state`. Simulated load under the pessimistic
assumption: ~116 of 287 items.

## Findings worth acting on

Route-A candidate quality on this pack is poor in places that will decide the pilot fast:
`effect_size "d=57462037"`, `apa_citation "WMG et al."`, template-looking DV lists on a
qualitative paper, empty measurement inventories where route B found six instruments.
Full evidence: `apps/kappa_review_r3/receipts/route_b_diff_receipt.json`.

## Gate

The ZIP does not go to Stephan until codex-ae's different-lineage REVIEW_VERDICT accepts
the R3 receipt (REVIEW_REQUEST posted 2026-09-11T15:48:36Z). Drive upload happens after
that verdict.
