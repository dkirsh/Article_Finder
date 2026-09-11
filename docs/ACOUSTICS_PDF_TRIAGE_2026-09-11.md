# Acoustics set, PDF acquisition triage

43 papers imported 2026-09-11 under source `acoustics_room_perception_2026-09-11`,
all tagged `acoustics`. This records what happened when PDFs were fetched, because
the first report of it was wrong in a way worth not repeating.

## The count that was reported, and what it actually was

The run reported **0 downloaded, 2 no-OA, 34 failed**. Reading the error strings
rather than the buckets gives a different picture:

| Outcome | n | What it means |
|---|---:|---|
| already on disk | 7 | fetched in an earlier run, verified as real PDFs |
| `No open access PDF found` | 25 | Unpaywall knows of no free copy. Genuinely closed. |
| `HTTP 403` | 8 | Unpaywall returned a PDF URL and the publisher refused the fetch |
| `Downloaded file is not a PDF` | 2 | an OA URL existed and served HTML |
| `IncompleteRead(4372600 bytes read)` | 1 | 4.37 MB transferred, then truncated |

So the set is **25 closed and 11 retrievable**, not 34 closed. The downloader only
attempts a fetch when `get_pdf_url()` has already returned a URL, so every 403,
every non-PDF and the truncated read is a paper Unpaywall says has a free copy.

## Why the 403s

`ingest/pdf_downloader.py` sends `User-Agent: ArticleFinder/3.0` on both the
Unpaywall lookup and the PDF fetch. The lookup is unaffected. The fetch is refused
by several publishers that answer a bare unknown agent with 403 regardless of the
article's licence. The eight are consistent with that and not with paywalling:

- `10.1073/pnas.1612524113` — PNAS, confirmed bronze OA
- `10.1051/aacus/2026024` — Acta Acustica, confirmed gold OA, CC-BY
- `10.3390/buildings15172995`, `10.3390/app12010348` — MDPI, gold OA by policy
- `10.1080/17508975.2025.2508233` — Taylor & Francis
- `10.1121/10.0022382`, `10.1121/1.3662055`, `10.1121/1.2936368` — AIP / JASA

Crossref, OpenAlex and Unpaywall all ask callers to send a descriptive agent with
a contact address. `scripts/download_by_tag.py --polite-agent` does that for the
fetch only, leaving the Unpaywall lookup and every other step untouched. The
durable fix is the same two strings in `ingest/pdf_downloader.py`, which affects
every acquisition the project makes, not only this set.

## Closed, and therefore the Zotero / UCSD batch

These 25 have no open-access copy and belong in `cli/main.py zotero export --format ris`:

    10.1145/3788851.3805009    10.1016/j.apacoust.2026.111334   10.1121/10.0042240
    10.1121/10.0036888         10.1109/TVCG.2025.3549855        10.1121/10.0027603
    10.1109/ismar62088.2024.00057   10.1109/i3da57090.2023.10289365
    10.1121/10.0023498         10.1016/j.jobe.2023.107063       10.1016/j.scs.2023.104394
    10.1121/10.0009167         10.1145/3561212.3561216          10.1177/03010066221125864
    10.1097/aud.0000000000001110    10.1177/03010066211020598
    10.1016/j.buildenv.2018.11.040  10.1016/j.apacoust.2018.06.019
    10.1121/1.4904515          10.1260/1351-010x.20.4.383       10.1068/p7555
    10.1121/1.4755592          10.1121/1.3455837                10.1109/iscit.2006.339980
    10.1121/1.425625

One caveat on that list. Scite reports `10.1016/j.apacoust.2026.111334` (Cerviño
et al., 2026) as open access, hybrid, CC-BY-NC-ND, while Unpaywall reports no free
copy. For a 2026 hybrid article that is most likely an indexing lag rather than a
contradiction; it is worth re-asking Unpaywall later before paying for it.

## Served a non-PDF

    10.1177/23312165241273399   Tsironis et al., Trends in Hearing — SAGE gold OA
    10.1121/1.5095862           Boucher et al., JASA

An OA location is recorded for both and fetching it returned something that is not
an article. Retry with `--polite-agent` first; if the result is still HTML, the
recorded OA URL is stale and the record needs correcting rather than the fetch
retrying.

## Truncated

    10.1109/i3da57090.2023.10289314   Burnett et al., I3DA 2023

4,372,600 bytes arrived before the connection closed. A plain retry is reasonable;
the 120-second timeout in `--polite-agent` is longer than the 60 seconds the
default path allows, which may be the whole story.
