# Article Finder v2 — Contract

**Author:** Dhruv Sood
**Date:** 2026-05-19
**Repo:** `Article_Finder/article_finder_v2/`

This contract is binding on the v2 module. The previously-submitted Task 3
code in `Article_Finder/task3/` is unchanged; v2 is an additive upgrade
that supersedes it for any new search/triage/PDF work.

---

## 0. Substitutions & Limitations (read first)

| Topic | Decision | Reason |
|---|---|---|
| Sci-Hub libraries (`scidownl`, `scihub.py`, `scihub-downloader`) | **NEVER imported. NEVER called. NEVER referenced as a live code path.** | Sci-Hub hosts copyrighted PDFs without publisher consent; UCSD library policy unresolved; course rubric flags Sci-Hub-by-default as a fatal failure condition. Compliance test enforces this. |
| Google Scholar HTML scraping | Not implemented | Violates Scholar ToS. Programmatic Scholar access requires a compliant provider (e.g., SerpAPI) wired via API key. v2 does not include this by default. |
| "Google Scholar AI" model | No official API exists | Scholar Labs (https://scholar.google.com/scholar_labs/search) is the public AI interface and has no developer API as of 2026-05. The AI contribution in v2 is a query planner + abstract triage layer driven by an LLM (Anthropic Claude / OpenAI GPT). It is NOT a Scholar wrapper. |
| Publisher-OA PDFs | Downloaded only when `is_oa = true` per Unpaywall or OpenAlex `open_access.is_oa` | The OA verification is the only legal signal we trust. |
| Authenticated institutional links | Out of scope | We do not bypass auth, cookies, or paywalls. |

---

## 1. Inputs

CLI: `python3 -m article_finder.cli search [options]`

| Flag | Default | Description |
|---|---|---|
| `--topic` | required (or `--research-gap` / `--seed-dois`) | free-text research topic |
| `--research-gap` | optional | gap statement (passed to AI query planner) |
| `--seed-titles` | optional | comma-separated list of seed paper titles |
| `--seed-dois` | optional | comma-separated DOIs for citation-chasing |
| `--max-results` | 50 | per-source max |
| `--download-pdfs` | false | actually fetch PDF bytes |
| `--enabled-sources` | `openalex,crossref,arxiv` | subset of {openalex, crossref, semantic_scholar, pubmed, europe_pmc, arxiv} |
| `--output-dir` | `data/handoff` | where handoff JSON/CSV land |
| `--ai-backend` | `none` | `none` / `anthropic` / `openai` |

Environment variables (read by code, never logged):

- `ANTHROPIC_API_KEY` — for AI query planner / triage if `--ai-backend anthropic`
- `OPENAI_API_KEY` — for `--ai-backend openai`
- `UNPAYWALL_EMAIL` — Unpaywall requires a polite-pool email (free, no key)
- `CROSSREF_MAILTO` — CrossRef polite-pool address
- `S2_API_KEY` — optional Semantic Scholar key (raises rate limit)
- `CORE_API_KEY` — optional CORE key

`.gitignore` blocks `.env*` and any `*.key` / `*.token` files.

---

## 2. Outputs

### Article record schema (JSON Schema-style)

```json
{
  "canonical_id": "openalex:W2741809807",
  "doi": "10.1038/s41562-020-0942-6",
  "title": "...",
  "title_normalized": "...",
  "authors": ["Surname, F.", ...],
  "first_author_surname": "Surname",
  "year": 2020,
  "venue": "Nature Human Behaviour",
  "abstract": "...",
  "abstract_source": "openalex | crossref | europe_pmc | arxiv | none",
  "openalex_id": "W2741809807",
  "semantic_scholar_id": null,
  "crossref_url": "https://api.crossref.org/works/...",
  "pubmed_id": null,
  "pmcid": null,
  "arxiv_id": null,
  "oa_status": "gold | green | hybrid | bronze | closed | unknown",
  "is_oa": true,
  "pdf_url": "https://...",
  "local_pdf_path": "data/pdfs/2020_surname_short-title_<hash>.pdf | null",
  "pdf_sha256": "abc... | null",
  "pdf_status": "downloaded | already_exists | no_oa_pdf | failed_network | failed_validation | skipped_non_oa | skipped_no_download",
  "relevance_score": 0.82,
  "score_breakdown": {
    "topic_match": 0.30,
    "doi_present": 0.10,
    "abstract_present": 0.10,
    "pdf_available": 0.15,
    "citation_signal": 0.05,
    "recency": 0.07,
    "source_agreement": 0.05,
    "ai_triage": 0.00
  },
  "why_selected": "Matches gap on construct X; appears in 2 sources; OA PDF; cited 84x; abstract on-topic.",
  "risks_or_limitations": [],
  "duplicate_group_id": "grp-001",
  "provenance": {
    "openalex": {"id": "W2741809807", "url": "..."},
    "crossref": {"doi": "10.1038/...", "url": "..."}
  }
}
```

### Required output files (under `--output-dir`)

| File | Contents |
|---|---|
| `articles.json` | JSON array of canonical records, sorted by `rank` |
| `articles.csv` | flat CSV with core columns for spreadsheet review |
| `download_report.json` | per-record PDF status with reasons |
| `query_log.json` | every query issued (source, query string, timestamp, n_results) |
| `dedup_report.json` | duplicate groups + chosen canonical |
| `triage_report.md` | human-readable AI triage notes |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success; handoff files written |
| 1 | invalid CLI args / missing required input |
| 2 | all sources failed (no results from any API) |
| 3 | partial: some sources failed but pipeline produced results (warning logged) |

---

## 3. Invariants

1. **No duplicate canonical DOI records** — after dedup, every normalized DOI appears at most once in `articles.json`.
2. **No illegal PDF downloads** — every entry in `download_report.json` with `status=downloaded` has a `legal_oa_proof` field (Unpaywall `is_oa=true` OR OpenAlex `open_access.is_oa=true`).
3. **No Sci-Hub usage** — compliance test scans the whole `article_finder_v2/` tree for `scihub|sci-hub|scidownl` and fails the build if any non-doc match is found.
4. **No Google Scholar scraping** — compliance test scans for `scholar.google.com` HTTP calls and fails if found outside docs.
5. **Every downloaded PDF has a `pdf_url` AND a `pdf_sha256`.**
6. **Every result has a `provenance` map** with at least one source.
7. **Every skipped PDF has a `pdf_status` and a reason** in `download_report.json`.
8. **Sorting is deterministic** — same inputs + same data produce identical `articles.json` ordering.
9. **Pipeline is rerunnable** — second run with same inputs creates 0 new PDF files and 0 net new article records.

---

## 4. Failure modes (must handle, must not crash)

| Condition | Behavior |
|---|---|
| API unavailable / network error | log to `query_log.json` with `error=true`; continue to next source |
| Rate limited (HTTP 429) | back off ≥ 5 s; retry once; log if still failing |
| Missing DOI | use OpenAlex/S2 ID as `canonical_id`; mark `doi=null` |
| Duplicate title with no DOI | merged via title + first author + year heuristic |
| No OA PDF found | `pdf_status='no_oa_pdf'`; record reason; do NOT attempt sci-hub |
| Invalid PDF URL (404, non-PDF content-type) | `pdf_status='failed_validation'`; do not write file |
| Download timeout (>30 s) | `pdf_status='failed_network'`; cleanup partial file |
| Partial metadata | record what's present; missing fields = null |
| Malformed API response (non-JSON, schema mismatch) | log; skip that record; continue |
| AI backend unavailable / no key | fall back to deterministic query planner; no crash |

---

## 5. Acceptance criteria

The system passes only if:

- `pytest article_finder_v2/tests/` is green (every test PASS).
- Compliance test (`test_compliance.py`) confirms no Sci-Hub references in the v2 source tree.
- CLI smoke test (`python3 -m article_finder.cli search --topic "circadian lighting attention" --max-results 5 --output-dir /tmp/af-smoke`) runs without exceptions and produces 6 handoff files.
- DOI normalization tests pass on the 4 sample URLs in `tests/test_doi.py`.
- Dedup tests pass on the 4 cases in `tests/test_dedup.py`.
- Re-running the CLI a second time produces zero new PDF files and zero net new article records.
- README documents how to run the pipeline.

---

## 6. AI contribution — what's actually new

v2's contribution beyond v1 (`task3/`) is the **AI-assisted scholarly discovery and triage layer** (`src/article_finder/ai/`):

1. **`query_planner.py`** — converts a research gap into multiple search dimensions (constructs, population, methods, domain, outcomes, synonyms, exclusion terms) and generates source-specific queries for OpenAlex/Crossref/arXiv/etc. Uses an LLM when `--ai-backend` is set; falls back to a deterministic decomposition otherwise.

2. **`abstract_triage.py`** — scores each candidate abstract against the gap with an explanation. Flags off-topic and weak-metadata papers. Produces the `why_selected` and `risks_or_limitations` strings on every record.

The AI calls are bounded (≤ 1 per gap for planning, ≤ 1 per abstract for triage) and the full prompt + response are logged to `query_log.json` for reproducibility.

This is the contribution the assignment asks for. It is NOT a Scholar wrapper — it is a deterministic + LLM-augmented planner that takes the gap, makes a plan, drives the legal APIs, and explains every selection.

---

## 7. Reproducibility

Every run writes to `query_log.json`:

- timestamp (ISO 8601 UTC)
- source
- query string (exact)
- result count
- any error
- AI prompt + response (when AI backend is used)

Same inputs + same data → same outputs. The pipeline is deterministic given (a) a fixed `--ai-backend` choice and (b) network responses (which we cache for tests via fixture JSON).
