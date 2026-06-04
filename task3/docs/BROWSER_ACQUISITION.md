# Browser-assisted acquisition (publisher-blocked OA PDFs)

## Why this exists
The automated acquirer (`pdf_acquirer.py`, Unpaywall → OpenAlex) downloads open-access
PDFs by DOI with a `%PDF` + SHA-256 gate. Some OA publishers — **MDPI, Frontiers,
PeerJ** — serve their PDFs behind **Cloudflare bot protection** that returns `HTTP 403`
to datacenter/script requests. The paper *is* open access (a real browser reads it
freely), but the automated path can't fetch it. `try_unpaywall` / `try_openalex_oa`
report `miss`.

This is an **assisted** path for exactly those papers: a real browser clears the
Cloudflare challenge, downloads the PDF, and `browser_acquire.py` records it in the
lifecycle DB exactly like the automated acquirer would.

> **Honest boundary.** This step is **assisted, not headless.** It needs an interactive
> **Claude-in-Chrome** session, and the download itself requires a **genuine user
> gesture** — a programmatic `a.click()` injected via JavaScript is silently blocked by
> Chrome's user-activation rule; a *synthesized* click through the browser's input tool
> (or a human click) works. So this is not part of the automated pipeline run; it is a
> manual/assisted fallback invoked for the handful of blocked-OA DOIs.

## Step 1 — detect (deterministic, no browser)
```bash
python3 task3/browser_acquire.py --check 10.3390/s24237838
#  → [oa_blocked]  OPEN ACCESS but the automated fetch is blocked (publisher bot wall).
#     Browser-assisted retrieval — open in Claude-in-Chrome: https://doi.org/...
```
`--check` runs the real Unpaywall/OpenAlex path and classifies the DOI:
`pipeline_ok` (no browser needed) · `oa_blocked` (use this runbook) · `paywalled`
(metadata only — the pipeline never bypasses a paywall).

## Step 2 — retrieve in a real browser (Claude in Chrome)
1. `list_connected_browsers` → `select_browser` → `tabs_context_mcp` (create a tab).
2. `navigate` the tab to the article page (e.g. `https://www.mdpi.com/1424-8220/24/23/7838`
   or `https://doi.org/<doi>`). A real browser passes the Cloudflare JS challenge.
3. Find the publisher's **"Download PDF"** control and click it with the **computer
   tool** (`left_click` on the button — a real gesture). On MDPI it's a "Download ▾"
   dropdown → "Download PDF".
4. The browser saves the PDF to `~/Downloads` (give it a few seconds — large PDFs take
   real wall-clock time; the file may carry the publisher's own name, e.g.
   `sensors-24-07838.pdf`).

## Step 3 — register into the lifecycle DB (deterministic)
```bash
python3 task3/browser_acquire.py --doi 10.3390/s24237838 --pdf ~/Downloads/sensors-24-07838.pdf
```
This verifies `%PDF`, copies the file into `task3/data/pdfs/<reference_id>.pdf`, fetches
metadata from OpenAlex, and inserts an `article_references` row with
`triage_decision='ACCEPT'`, `triage_stage='acquired'`, `acquired_paper_id`, `pdf_path`,
`pdf_sha256`, and a lifecycle transition — `discovered_via='claude_in_chrome'` so the
provenance is honest (retrieved via browser, not the automated OA resolver).

## Proven (this checkout)
| DOI | Paper | Size | Result |
|---|---|---|---|
| `10.3390/s24237838` | Brain & Subjective Responses to Indoor Environments… | 12.6 MB | ✓ retrieved + registered |
| `10.3390/s21062193` | Cognitive-Emotional Design of Architectural Space… | 1.4 MB | ✓ retrieved + registered |

Both were `403`-blocked for the automated acquirer; both downloaded cleanly in a real
browser and now persist in `pipeline_lifecycle_full.db`.
