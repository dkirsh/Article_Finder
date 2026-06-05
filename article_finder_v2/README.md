# article_finder v2

An upgrade pass on the Track 2 Article Finder pipeline. Adds:

- multi-source legal search (OpenAlex, Crossref, arXiv) with retries
- DOI normalization + cross-source deduplication that preserves provenance
- strict open-access PDF resolver (Unpaywall → OpenAlex OA → Europe PMC → arXiv → PMC)
- transparent ranking with an explainable score breakdown
- **AI-assisted query planner + per-abstract triage** — the contribution
- six handoff files written atomically
- 38-test suite including a compliance scan that proves there is no Sci-Hub code in the module

The previously-submitted Task 3 (`Article_Finder/task3/`) is unchanged. v2 lives in its own module so the existing PR is not disturbed.

## What v2 is NOT

- It is **not** a Sci-Hub client. No `scidownl`, `scihub.py`, or `scihub-downloader` is imported or called. The compliance test (`tests/test_compliance.py`) enforces this.
- It is **not** a Google Scholar scraper. `scholar.google.com` is never fetched. The compliance test enforces this.
- It is **not** a wrapper around any unofficial "Google Scholar AI" model. The AI layer is our own planner + triage, driven by an LLM (Anthropic / OpenAI) when keys are configured, with a deterministic fallback when they are not.

## Install

```bash
cd article_finder_v2
pip install -e .          # or: pip install -e ".[ai,dev]"
```

## Run

```bash
# Offline smoke run (no network; produces all 6 handoff files)
python3 -m article_finder.cli search \
    --topic "circadian lighting attention adults" \
    --max-results 10 \
    --enabled-sources openalex,crossref,arxiv \
    --ai-backend none \
    --no-network \
    --output-dir data/handoff

# Online run with PDF downloads (legal OA only)
export UNPAYWALL_EMAIL=you@your-domain
export CROSSREF_MAILTO=you@your-domain
python3 -m article_finder.cli search \
    --topic "circadian lighting attention adults" \
    --max-results 25 \
    --download-pdfs --download-top-n 10 \
    --output-dir data/handoff

# Online run with AI planner + triage (requires API key)
export ANTHROPIC_API_KEY=sk-ant-...
python3 -m article_finder.cli search \
    --research-gap "what behavioral evidence links morning-light intensity to attention scores in office workers, and which neural mechanisms have been measured?" \
    --ai-backend anthropic \
    --download-pdfs \
    --output-dir data/handoff
```

## Outputs (handoff files)

| File | What |
|---|---|
| `articles.json` | sorted canonical records with `rank`, `score`, `score_breakdown`, `why_selected`, `provenance` |
| `articles.csv` | spreadsheet-friendly subset |
| `download_report.json` | per-record PDF status with the `legal_oa_proof` from Unpaywall/OpenAlex/etc. |
| `query_log.json` | every query issued (source, query string, n_results, error, AI prompt + response if used) |
| `dedup_report.json` | duplicate groups + chosen canonical + match reasons |
| `triage_report.md` | human-readable AI triage notes per paper |

## Tests

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
# 38 passed
```

Tests cover:
- DOI normalization on the 4 required URL variants + invalid-input rejection
- Dedup: same DOI from 3 sources, capitalization, title+author+year, different-papers-don't-merge, merge-preserves-longer-abstract
- PDF: magic bytes, safe filename, path-traversal rejection, sha256 stability, no-OA → `no_oa_pdf`, network-off → `skipped_no_download`, already-exists no-redownload
- Ranking: weights sum to 1, PDF availability raises score, breakdown sums to score, deterministic order, on-topic > off-topic
- Compliance: no Sci-Hub imports, no Sci-Hub URLs, downloader only consumes resolver output, no Scholar HTML scraping
- CLI: smoke run produces all 6 handoff files; empty-topic exits 1

## Contract

Full contract at [`docs/contracts/article_finder_contract.md`](docs/contracts/article_finder_contract.md). Includes inputs, JSON schema for outputs, invariants, failure modes, and acceptance criteria.

## Compliance statement

This module:

1. Does not import any Sci-Hub library or call any Sci-Hub URL. Enforced by automated scan (`tests/test_compliance.py`).
2. Does not bypass paywalls or authentication. The downloader only fetches URLs that an OA resolver (Unpaywall, OpenAlex, Europe PMC, arXiv, PMC) has marked as open access; every downloaded file carries a `legal_oa_proof` field in the download report.
3. Does not scrape `scholar.google.com`. Enforced by automated scan.
4. Never logs API keys; reads them only from environment variables.
5. Respects rate limits (per-source backoff on HTTP 429; max-byte cap on PDF streams).

## Known limitations

- arXiv is treated as universally OA (it is, under the arXiv license), but the resolver does not yet verify the specific paper's license terms.
- Semantic Scholar, PubMed, and Europe PMC search backends are referenced in the resolver but not wired as full search clients (`search/` only has openalex / crossref / arxiv). Adding them is a 1-file change each; the dedup + ranking already accept their IDs.
- The AI backends (`anthropic`, `openai`) gracefully fall back to the deterministic planner when keys are absent or calls fail. The fallback is fully tested; the live LLM path is not unit-tested (requires mocking the SDK).
- The deterministic planner is a token-extractor, not a librarian. The Anthropic / OpenAI path is materially better when a key is configured.
