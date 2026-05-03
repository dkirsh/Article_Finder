# Query Generator Contract — Task 2 Phase 3
**Author:** Dhruv Sood  
**Date:** 2026-04-28  
**Repo:** Article_Finder  
**Task:** Track 2 · Task 2 — Gap Targeting & Query Generation

---

## 1. Inputs

| Field | Value |
|---|---|
| `--gaps` | Path to `gap_results.json` produced by `gap_extractor.py` |
| `--top-n` | Generate queries for top N gaps by VOI score (default: 10) |
| `--output` | Path for `query_results.json` (default: `query_results.json`) |

---

## 2. Processing (step-by-step)

1. Load `gap_results.json`; take the top-N by `voi_score`.
2. For each gap, extract from the mechanism name: the **environmental condition** (IV) and the **outcome / mechanism step** (DV/pathway).
3. Look up framework vocabulary (SRT, ART, AL, PP, etc.) to inject the **theoretical anchor** (Component 5).
4. Generate **AI Citation query** (natural-language sentence, > 50 chars, ends with `?`):
   - Pattern: `What {evidence_type} shows that {environmental_condition} {mechanism_pathway} {outcome}, {theoretical_anchor}?`
   - Component 1 (evidence type): "empirical evidence" / "neuroimaging evidence" / "longitudinal studies"
   - Component 2 (mechanism): the mechanism step from the gap
   - Component 3 (environment): built environment or natural environment feature
   - Component 4 (population/context): "in healthy adults" / "in office workers"
   - Component 5 (theory): framework abbreviation expanded
5. Generate **Boolean query** (for Google Scholar / SerpAPI):
   - Rules: exact phrases in double quotes, `AND`/`OR` joins, at minimum one quoted phrase, `-review` to filter review noise when targeting primary studies.
   - Pattern: `("mechanism term" OR "synonym") AND ("environment term" OR "alt term") AND ("outcome") -review`
6. Write `query_results.json`.

---

## 3. Outputs

File: `query_results.json`

```json
[
  {
    "gap_id": "AL-CHRONIC-PE-001",
    "mechanism_name": "Chronic low-level PE → sustained cortisol",
    "framework_id": "AL",
    "voi_score": 0.74,
    "ai_citation_query": "What longitudinal evidence shows that chronic exposure to unpredictable built environments elevates cortisol through sustained prediction-error accumulation, consistent with Allostatic Load theory?",
    "boolean_query": "\"cortisol\" AND (\"prediction error\" OR \"allostatic load\") AND (\"built environment\" OR \"indoor environment\") AND \"chronic stress\" -review",
    "query_rationale": "Targets HPA-axis measurements in longitudinal studies; -review excludes narrative summaries to prioritise primary neurobiological data."
  },
  ...
]
```

Required fields per entry: `gap_id`, `mechanism_name`, `voi_score`, `ai_citation_query`, `boolean_query`, `query_rationale`.

---

## 4. Success Conditions

1. Script runs: `python3 query_generator.py --gaps gap_results.json`
2. Every gap in top-10 has both `ai_citation_query` and `boolean_query`.
3. All AI Citation queries: length > 50 chars AND end with `?`.
4. All Boolean queries: contain at least one quoted phrase (`"`) AND at least one `AND`.
5. No Boolean query is a bare comma-separated word list without operators.
6. At least 3 of 10 queries tested manually in Google return relevant first-page results (Phase 4 spot-check).
7. `query_results.json` is valid JSON.

---

## 5. Test Checklist (run before Phase 4)

- [ ] All `ai_citation_query` end with `?`
- [ ] All `ai_citation_query` length > 50 characters
- [ ] All `boolean_query` contain `AND` or `OR`
- [ ] All `boolean_query` contain at least one `"` (quoted phrase)
- [ ] No `boolean_query` is just comma-separated words
- [ ] `query_results.json` is valid: `python3 -c "import json; json.load(open('query_results.json'))"`
- [ ] Manual Google spot-check: 3 AI Citation queries → relevant first page
