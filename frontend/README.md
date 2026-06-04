# Article Finder — front-end mockup

A self-contained React UI over the Track 2 pipeline. It is a **faithful mockup of the
real outputs** (API-ready), not yet wired to the Python backend: all data flows through
`src/api.js`, whose async functions return mock data shaped exactly like the real
pipeline (triage decisions `ACCEPT/EDGE_CASE/REJECT/NEEDS_MORE_INFO`, retrieval statuses
`oa_retrieved/browser_retrieved/paywalled/oa_blocked`, and a `voiBreakdown` whose
structural/epistemic fields are `null` — the same honest shape `gap_extractor` emits).

## Run it

Because the page loads `src/*.jsx` over XHR (Babel-in-browser), `file://` is blocked by
Chrome — serve it over a tiny static server:

```bash
cd frontend
python3 -m http.server 8000
# then open:  http://localhost:8000/Article%20Finder.html
```

No build step, no npm install — React + Babel load from a CDN.

## Screens (the workflow)

1. **Ingest** — single file / multiple files / .zip / pasted text; each item may be a
   citation, question, abstract, DOI, or title → resolved to APA + abstract + DOI.
2. **Identify & Triage** — every article's **topic, article type, and triage decision**
   shown *before* you choose what to retrieve; select rows (or "all ACCEPT").
3. **Retrieve** — per-item status with the honest outcomes: OA-retrieved /
   browser-assisted / paywalled (metadata only) / publisher-blocked.
4. **Library** — a viewer over the collected-articles DB (filter by topic, type, triage,
   retrieval status; detail drawer with abstract, APA, DOI, sha256).
5. **VOI** — recommended areas to search next, ranked by value-of-information.
6. **Scholar compare** — side-by-side vs Google Scholar AI (external comparison).

## Wiring to the real backend later

Replace the mock bodies in `src/api.js` (`enrich`, `triage`, `retrieve`, `library`,
`recommendations`, `compareScholar`) with `fetch('/api/...')` calls to a thin API over
`task3/` (`abstract_collector`, `abstract_triage`, `pdf_acquirer`, `browser_acquire`,
`gap_extractor`). The component layer does not change.
