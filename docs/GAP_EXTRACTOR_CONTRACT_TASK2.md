# Gap Extractor Contract — Task 2 Phase 2
**Author:** Dhruv Sood · **Date:** 2026-05-03 · **Repo:** Article_Finder

---

## Data source note (critical)

The rubric specifies `Article_Eater/data/templates/` (166 PNU templates with
`mechanism_chain.confidence`). The Article_Eater repo has no working tree on
this checkout (its `.git` exists but `git checkout` of `main` produces no
files — verified, repeatable).

**Approved substitute:** `Knowledge_Atlas/data/ka_payloads/mechanisms.json` —
the canonical mechanism profile manifest produced by Article_Eater (71
mechanisms across 15 frameworks). Every field used below is present in that
manifest. The `--mechanisms-path` flag accepts an alternative JSON source if
Article_Eater templates become available; the rest of the pipeline does not
need to change.

---

## 1. Inputs

| Flag | Default | Notes |
|---|---|---|
| `--mechanisms-path` | `../Knowledge_Atlas/data/ka_payloads/mechanisms.json` | PNU manifest |
| `--confidence-threshold` | `0.60` | mechanisms with confidence < threshold are extracted |
| `--min-gaps` | `10` | warn if fewer found |
| `--output` | `gap_results.json` | sorted by VOI desc |

Confidence mapping from `maturity` (analog to PNU `mechanism_chain.confidence`):

- `How-Plausibly` → 0.42 (clearly below threshold → gap)
- `How-Actually` → 0.78 (above threshold → not a gap)
- `stub` → 0.20, `brief` → 0.35

---

## 2. Processing (rubric §2A "walk mechanism_chain")

1. Load mechanism manifest → list of mechanisms.
2. For each mechanism, map `maturity → confidence`.
3. Filter: `confidence < threshold`.
4. Compute `voi_score`:
   - `base = 1.0 - confidence`  (low confidence → high priority)
   - `+0.15` if `framework_id == 'cross_framework'` (multi-framework hub centrality)
   - `+0.08` if `temporal` contains "chronic" or "long" (slow cascades)
   - `−min(word_count / 2000, 0.20)` (well-documented → less urgent)
   - clamped to `[0, 1]`
5. Sort gaps by `voi_score` descending.
6. Emit JSON.

---

## 3. Outputs (rubric §2C — exact field names)

```json
[
  {
    "template_id":      "INTERO-PP-ALLOSTASIS-001",
    "step_number":      1,
    "mechanism_name":   "Interoceptive PE failure → allostatic cascade",
    "framework_id":     "cross_framework",
    "framework_name":   "Cross-Framework",
    "maturity":         "How-Plausibly",
    "confidence":       0.42,
    "gap_type":         "mechanism_underpowered",
    "voi_score":        0.61,
    "missing_evidence": "Direct empirical measurement linking 'Interoceptive PE failure' to 'allostatic cascade' …",
    "voi_explanation":  "voi=0.610 ← base=0.58 (1 - confidence=0.42), centrality+0.15 (cross-framework hub), temporal+0.08 (chronic/long cascade), coverage-0.46 (word_count=920)",
    "temporal":         "Chronic",
    "word_count":       920,
    "gap_id":           "INTERO-PP-ALLOSTASIS-001",
    "what_is_missing":  "...alias of missing_evidence..."
  }
]
```

Required fields per the rubric: `template_id`, `step_number`, `confidence`,
`gap_type`, `voi_score`, `missing_evidence`. Aliases (`gap_id`,
`what_is_missing`) are kept for back-compat with the query generator.

---

## 4. Success conditions (rubric verbatim)

1. ≥ 10 gaps extracted across ≥ 3 frameworks.
2. Every gap has `template_id`, `step_number`, `confidence`, `gap_type`, `voi_score`, `missing_evidence`.
3. All `voi_score` ∈ [0.0, 1.0].
4. Sorted by `voi_score` descending (first entry has highest score).
5. `gap_results.json` is valid, parseable JSON.
6. Each gap's `missing_evidence` is non-empty.
7. No duplicate `template_id`.
8. `voi_explanation` shows the arithmetic (auditability).

---

## 5. Test checklist (proven by `task3/tests_task2_task3.py`)

- [x] `--confidence-threshold 1.0` extracts ALL 71 mechanisms (parsing works)
- [x] `--confidence-threshold 0.0` extracts 0 mechanisms (filter works)
- [x] All `voi_score` in [0, 1]
- [x] Gaps sorted descending by `voi_score`
- [x] Output JSON valid
- [x] ≥ 10 gaps at default threshold (got 31)
- [x] ≥ 3 distinct `framework_id` (got 15)
- [x] No duplicate `template_id`
- [x] `compute_voi({}, 0.4)` does not crash (defensive against missing fields)

Run: `python3 task3/tests_task2_task3.py` → PASS.
