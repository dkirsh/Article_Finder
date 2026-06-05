# Gap Extractor Contract — Task 2 Phase 2
**Author:** Dhruv Sood · **Date:** 2026-05-03 · **Repo:** Article_Finder

---

## 0. Substitutions & Limitations (read first)

| Topic | Canonical | Substitute used | Justification |
|---|---|---|---|
| Input source | `Article_Eater/data/templates/` (166 PNU templates) | `Knowledge_Atlas/data/ka_payloads/mechanisms.json` (71 mechanisms × 15 frameworks) | Article_Eater's working tree is unavailable on this checkout (.git is present but `git checkout` produces no files — verified, repeatable). The mechanism manifest is the canonical output Article_Eater produces; same fields are present. `--mechanisms-path` accepts a real templates directory the moment Article_Eater is back. |
| VOI scoring | `Article_Eater/src/services/voi_search.py::VOICalculator.calculate_voi()` | local `compute_voi()` in `gap_extractor.py` implementing the same formula | VOICalculator class is in the inaccessible repo. Local re-implementation uses the documented formula (`base + centrality + temporal − coverage`, all clamped to [0,1]). When Article_Eater is back, `--use-voicalculator` will swap to the upstream class. |
| Confidence threshold | configurable via `--confidence-threshold` (default `0.60`) | same | Picked because the maturity→confidence map places `How-Plausibly = 0.42` and `How-Actually = 0.78`; the threshold sits between them so How-Actually mechanisms are not flagged as gaps and every plausibly-supported step is. |

Manual artifacts required: **none** for this contract.

---

## 1. Inputs

| Flag | Default | Notes |
|---|---|---|
| `--mechanisms-path` | `../Knowledge_Atlas/data/ka_payloads/mechanisms.json` | PNU manifest (or Article_Eater templates dir) |
| `--confidence-threshold` | `0.60` | mechanisms with confidence < threshold are extracted |
| `--min-gaps` | `10` | warn (do not crash) if fewer found at the default threshold |
| `--output` | `gap_results.json` | sorted by VOI desc |

Confidence mapping from `maturity` (analog to PNU `mechanism_chain.confidence`):

- `How-Plausibly` → 0.42 (clearly below threshold → gap)
- `How-Actually` → 0.78 (above threshold → not a gap)
- `stub` → 0.20, `brief` → 0.35

---

## 2. Allowed `gap_type` values (enum, closed set)

| Value | When emitted |
|---|---|
| `mechanism_undocumented` | maturity ∈ {stub, brief} OR word_count < 200 |
| `mechanism_underpowered` | maturity == `How-Plausibly` |
| `mechanism_gap` | everything else below the confidence threshold |

Any other value is a contract violation.

---

## 3. Processing (rubric §2A "walk mechanism_chain")

1. Load mechanism manifest. If JSON is malformed → log warning, skip the file, continue (do not crash).
2. For each mechanism:
   - if `mechanism_chain` is missing/empty → skip with warning.
   - map `maturity → confidence`. If `maturity` is missing → default `0.30`.
3. Filter: `confidence < threshold`. Boundary: `0.59` is included, `0.60` is excluded.
4. Compute `voi_score`:
   - `base = 1.0 - confidence` (low confidence → high priority)
   - `+0.15` if `framework_id == 'cross_framework'` (multi-framework hub centrality bonus)
   - `+0.08` if `temporal` contains "chronic" or "long" (slow cascades)
   - `−min(word_count / 2000, 0.20)` (well-documented → less urgent; clamped at 0.20)
   - clamped to `[0, 1]`
5. Sort gaps by `voi_score` descending.
6. Emit JSON.

If `VOICalculator` (or local `compute_voi`) raises on a single gap → log warning, skip that gap, continue. Never let one bad mechanism crash the whole run.

---

## 4. Outputs (rubric §2C — exact field names)

```json
[
  {
    "gap_id":            "INTERO-PP-ALLOSTASIS-001",
    "template_id":       "INTERO-PP-ALLOSTASIS-001",
    "step_number":       1,
    "mechanism_name":    "Interoceptive PE failure → allostatic cascade",
    "framework_id":      "cross_framework",
    "framework_name":    "Cross-Framework",
    "maturity":          "How-Plausibly",
    "confidence":        0.42,
    "gap_type":          "mechanism_underpowered",
    "voi_score":         0.61,
    "missing_evidence":  "Direct empirical measurement linking 'Interoceptive PE failure' to 'allostatic cascade' …",
    "voi_explanation":   "voi=0.610 ← base=0.58 (1 - confidence=0.42), centrality+0.15 (cross-framework hub), temporal+0.08 (chronic/long cascade), coverage-0.20 (word_count=920, clamped at 0.20)",
    "temporal":          "Chronic",
    "word_count":        920,
    "what_is_missing":   "(alias of missing_evidence)"
  }
]
```

`voi_explanation` is built deterministically from the same arithmetic that produced `voi_score`; reading it tells the grader exactly which terms contributed.

Required fields per the rubric: `template_id`, `step_number`, `confidence`, `gap_type`, `voi_score`, `missing_evidence`. `gap_id` and `what_is_missing` are kept for back-compat with the query generator.

---

## 5. Success conditions (rubric verbatim)

1. ≥ 10 gaps extracted across ≥ 3 frameworks.
2. Every gap has `template_id`, `step_number`, `confidence`, `gap_type`, `voi_score`, `missing_evidence`.
3. All `voi_score` ∈ [0.0, 1.0].
4. Sorted by `voi_score` descending (first entry has highest score).
5. `gap_results.json` is valid, parseable JSON.
6. Each gap's `missing_evidence` is non-empty.
7. No duplicate `template_id`.
8. `voi_explanation` shows the arithmetic (auditability).
9. `gap_type` is from the closed enum in §2.
10. Script does not crash on malformed templates / missing fields / non-numeric confidence.

---

## 6. Failure handling

| Condition | Behavior |
|---|---|
| Template file is malformed JSON | log warning, skip file, continue |
| Mechanism missing `mechanism_chain` (or empty) | skip mechanism, do not count as gap |
| Step has no `confidence` field | skip step |
| `confidence` is non-numeric | skip step, log warning |
| VOI computation raises | skip gap, log warning |
| Fewer than `--min-gaps` extracted | print warning to stderr; do **not** raise; exit 0 |

---

## 7. Test checklist (proven by `task3/tests_task2_task3.py`)

- [x] `--confidence-threshold 1.0` extracts ALL 71 mechanisms (parsing works)
- [x] `--confidence-threshold 0.0` extracts 0 mechanisms (filter works)
- [x] All `voi_score` in [0, 1]
- [x] Gaps sorted descending by `voi_score`
- [x] Output JSON valid
- [x] ≥ 10 gaps at default threshold (got 31)
- [x] ≥ 3 distinct `framework_id` (got 15)
- [x] No duplicate `template_id`
- [x] `compute_voi({}, 0.4)` does not crash (defensive against missing fields)
- [x] Boundary: confidence 0.59 included; 0.60 excluded

Run: `python3 task3/tests_task2_task3.py` → 11/11 Task 2 checks PASS.
