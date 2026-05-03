# Gap Extractor Contract — Task 2 Phase 2
**Author:** Dhruv Sood  
**Date:** 2026-04-28  
**Repo:** Article_Finder  
**Task:** Track 2 · Task 2 — Gap Targeting & Query Generation

---

## Data Source Note

The spec references `Article_Eater/data/templates/` (166 PNU templates with `mechanism_chain`
and per-step `confidence` scores). The Article_Eater repo did not have a working checkout at
time of submission. As the approved substitute, this contract uses
`Knowledge_Atlas/data/ka_payloads/mechanisms.json` — the canonical mechanism profile manifest
(71 mechanisms across 15 frameworks) that Article_Eater generates. Every field used below is
present in that manifest. If Article_Eater templates become available, `--templates-path`
accepts an alternative JSON source.

---

## 1. Inputs

| Field | Value |
|---|---|
| `--mechanisms-path` | Path to `mechanisms.json` (default: `../Knowledge_Atlas/data/ka_payloads/mechanisms.json`) |
| `--confidence-threshold` | Float 0–1; mechanisms with confidence < threshold are extracted as gaps (default: 0.6) |
| `--min-gaps` | Minimum gaps required for success (default: 10) |
| `--output` | Path for `gap_results.json` (default: `gap_results.json`) |

Confidence mapping from `maturity` field:
- `How-Plausibly` → confidence = 0.42 (clearly below threshold → gap)
- `How-Actually` → confidence = 0.78 (above threshold → not a gap)
- missing/stub → confidence = 0.20 (lowest confidence → highest priority)

---

## 2. Processing (step-by-step)

1. Load `mechanisms.json`; parse the `mechanisms` list.
2. For each mechanism, map `maturity` → `confidence` float.
3. Filter to mechanisms with `confidence < threshold`.
4. For each gap, compute `voi_score`:
   - `base = 1.0 - confidence` (lower confidence → higher base VOI)
   - `centrality_bonus`: +0.15 if `framework_id == "cross_framework"` (multi-framework hub)
   - `coverage_penalty`: `−min(word_count / 2000, 0.20)` (well-documented → less urgent)
   - `temporal_bonus`: +0.08 if `temporal` contains "Chronic" or "Long" (slow cascades are harder to study)
   - `voi_score = min(base + centrality_bonus + temporal_bonus − coverage_penalty, 1.0)`
5. Sort gaps by `voi_score` descending.
6. Write `gap_results.json`.

---

## 3. Outputs

File: `gap_results.json`

```json
[
  {
    "gap_id": "AL-CHRONIC-PE-001",
    "mechanism_name": "Chronic low-level PE → sustained cortisol",
    "framework_id": "AL",
    "framework_name": "Allostatic Load",
    "maturity": "How-Plausibly",
    "confidence": 0.42,
    "gap_type": "mechanism_underpowered",
    "voi_score": 0.74,
    "what_is_missing": "Direct longitudinal measurement linking prediction-error frequency to HPA-axis cortisol elevation in built-environment contexts.",
    "temporal": "Hormonal → chronic",
    "word_count": 297
  },
  ...
]
```

Required fields per entry: `gap_id`, `mechanism_name`, `framework_id`, `confidence`, `gap_type`, `voi_score`, `what_is_missing`.

---

## 4. Success Conditions

1. Script runs end-to-end without error: `python3 gap_extractor.py`
2. At least 10 gaps extracted across at least 3 different frameworks.
3. All `voi_score` values fall strictly in [0.0, 1.0].
4. All `confidence` values fall in [0.0, 1.0].
5. Gaps sorted by `voi_score` descending (first entry has highest score).
6. `gap_results.json` is valid, parseable JSON.
7. Each gap has a non-empty `what_is_missing` string.
8. No duplicate `gap_id` entries.

---

## 5. Test Checklist

- [ ] `--confidence-threshold 1.0` extracts ALL mechanisms (verifies parsing)
- [ ] `--confidence-threshold 0.0` extracts zero mechanisms (verifies filter)
- [ ] All `voi_score` in [0.0, 1.0]
- [ ] Gaps sorted descending by `voi_score`
- [ ] Output JSON valid: `python3 -c "import json; json.load(open('gap_results.json'))"`
- [ ] At least 10 gaps at default threshold 0.6
- [ ] At least 3 distinct `framework_id` values
- [ ] No duplicate `gap_id`
