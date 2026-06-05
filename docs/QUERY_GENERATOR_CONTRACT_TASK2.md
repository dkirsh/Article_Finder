# Query Generator Contract — Task 2 Phase 3
**Author:** Dhruv Sood · **Date:** 2026-05-03 · **Repo:** Article_Finder

---

## 0. Substitutions & Limitations

| Topic | Canonical | Substitute used | Justification |
|---|---|---|---|
| Query patterns | `160sp/ka_google_search_guide.html` + `query_generator_skill.md` | followed verbatim where applicable | The 5-component pattern + Boolean phrase rules below match the guide. |
| Cross-framework vocabulary | per-framework synonym map in the guide | `CROSS_FRAMEWORK_VOCAB_MAP` in `query_generator.py` (per-gap overrides for the 11 cross-framework hubs) | The guide's per-framework synonyms only fire when the gap has a single framework. Cross-framework hubs would otherwise fall to a generic vocabulary. The override map injects domain-specific synonyms (interoception, circadian rhythm, oxytocin, etc.). |
| Manual spot-check | required by the rubric | recorded in `docs/QUERY_SPOT_CHECK_TASK2.md` with first-page result titles | Cannot be checked from code; the artifact is the proof. |

Manual artifacts required: **3 spot-checked queries** in `docs/QUERY_SPOT_CHECK_TASK2.md`.

---

## 1. Inputs

| Flag | Default | Notes |
|---|---|---|
| `--gaps` | `gap_results.json` | output of `gap_extractor.py` |
| `--top-n` | `10` | how many top-VOI gaps get queries |
| `--output` | `query_results.json` | per-gap query pair |

---

## 2. Processing

For each of the top-N gaps:

1. Read the gap. Identify environmental feature (from framework `env_terms`), mechanism (from `mechanism_name`), and synonyms (from `mechanism_synonyms`, with per-gap override if cross_framework).
2. Generate one **AI Citation query** following the 5-component pattern.
3. Generate one **Boolean query** following the structured-phrase pattern.
4. Validate both automatically (rules in §4 and §5). Set `query_quality_flags` for any sub-rule that fails.
5. Attach both queries + the term breakdown.

---

## 3. Output

```json
{
  "gap_id":            "GAP-...",
  "template_id":       "...",
  "voi_score":         0.61,
  "gap_summary":       "Interoceptive PE failure → allostatic cascade (Cross-Framework, How-Plausibly)",
  "ai_citation_query": "What longitudinal evidence shows that thermal environment exposure influences …?",
  "boolean_query":     "(\"interoception\" OR …) AND (\"thermal environment\" OR …) AND (\"allostatic load\") -review",
  "query_terms": {
    "environment_terms": ["thermal environment", "indoor climate"],
    "mechanism_terms":   ["interoception", "Interoceptive PE failure"],
    "outcome_terms":     ["allostatic cascade", "allostatic load"],
    "method_terms":      ["longitudinal", "neuroimaging"]
  },
  "query_quality_flags": []
}
```

---

## 4. AI Citation Query — closed rule set

Each AI Citation query MUST:

- [x] be a full research question (full sentence, ends with `?`)
- [x] be > 50 characters
- [x] include the environmental feature (from `env_terms`)
- [x] include the psychological / cognitive outcome (mechanism destination)
- [x] include the missing mechanism (mechanism source)
- [x] include study/evidence vocabulary: at least one of `evidence`, `study`, `studies`, `neuroimaging`, `behavioral`, `experimental`, `longitudinal`
- [x] read as a real research question (verb agrees with subject — see grammar bug we caught and fixed: `_evidence_type()` returns mass nouns like `"longitudinal evidence"` so the template `"What {ev_type} shows that …"` stays grammatical)

Pattern:
```
What {evidence_type} shows that {environmental_feature} exposure influences
'{mechanism_source}' leading to '{mechanism_destination}' in {population},
{theory_anchor}?
```

---

## 5. Boolean Query — closed rule set

Each Boolean query MUST:

- [x] use exact-phrase quotes (`"…"`) for at least one term
- [x] use `AND` between major concept groups
- [x] use `OR` for synonyms inside a group
- [x] include `-review` when the goal is primary studies (default ON; set OFF only for review-meta gaps)
- [x] NOT be a bare comma-separated list (a comma outside an `OR` group is a violation)
- [x] stay under 250 characters total (Google Scholar truncates after that)

Pattern:
```
("mechanism_term" OR "synonym1" OR "synonym2")
AND ("env_term" OR "env_alt")
AND ("outcome_term" OR "outcome_synonym")
-review
```

---

## 6. `query_quality_flags` enum (closed set)

Set on the output object when a query violates a sub-rule. Allowed values:

| Flag | Meaning |
|---|---|
| `no_synonyms` | Boolean has no `OR` group |
| `single_term_only` | Boolean has only one quoted phrase (too narrow) |
| `missing_outcome` | Outcome term is empty (mechanism without `→`) |
| `exceeds_length_limit` | Boolean > 250 chars |
| `no_review_filter` | `-review` is missing on a primary-studies gap |
| `no_question_mark` | AI Citation does not end with `?` |
| `too_short` | AI Citation < 50 chars |
| `degenerate_dv` | mechanism_source == mechanism_destination (single-step gap) — surfaces a known weak query |

An empty list `[]` means all rules passed.

---

## 7. Success conditions

1. `query_results.json` is valid JSON.
2. ≥ 10 gaps carry both `ai_citation_query` and `boolean_query`.
3. Every AI Citation query passes every rule in §4.
4. Every Boolean query passes every rule in §5.
5. No Boolean query is a bare comma-list.
6. ≥ 3 AI Citation queries spot-checked manually in Google with the first-page result titles recorded in `docs/QUERY_SPOT_CHECK_TASK2.md`.
7. The contract validator (`validate_queries()` in `query_generator.py`) prints all 6 PASS lines.

---

## 8. Required manual spot-check (template, do not fake)

Recorded in `docs/QUERY_SPOT_CHECK_TASK2.md`. Format:

| gap_id | Query (truncated) | First-page relevant? | Top result title | Notes |
|---|---|---|---|---|
| INTERO-PP-ALLOSTASIS-001 | `"interoception" AND "thermal environment" …` | TBD by user | TBD | |
| MULTISENSORY-CONGRUENCE-001 | What empirical evidence shows that … | TBD by user | TBD | |
| CIRCADIAN-DEV-PROGRAM-001 | `"circadian rhythm" AND "daylight" …` | TBD by user | TBD | |

If a query was not actually run, write `NOT RUN`. Do not fake.

---

## 9. Test checklist (proven by `task3/tests_task2_task3.py`)

- [x] `query_results.json` is valid JSON
- [x] ≥ 10 paired queries
- [x] every AI Citation > 50 chars and ends with `?`
- [x] every Boolean has AND/OR and a quoted phrase
- [x] no Boolean is a bare comma-list
- [x] generator does not crash when `--top-n` exceeds gap count

Run: `python3 task3/tests_task2_task3.py` → covers Task 2 query checks.
