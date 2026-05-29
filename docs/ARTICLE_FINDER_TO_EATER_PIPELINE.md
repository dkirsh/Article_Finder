# Article Finder to Article Eater Pipeline

This diagram traces the current Article Finder flow from the first user request to PDF acquisition and Article Eater job readiness.

```mermaid
flowchart TD
    A["User request"] --> B{"Entry point"}

    B --> B1["CLI: cli/main.py"]
    B --> B2["Streamlit UI: ui/app.py + ui/pages/*"]
    B --> B3["Discovery automation: search/discovery_orchestrator.py"]
    B --> B4["HITL review: hitl_review/app.py"]

    B1 --> C{"Requested operation"}
    B2 --> C
    B3 --> C

    C --> C1["Import references or CSV/XLSX"]
    C --> C2["Import local PDFs"]
    C --> C3["Discover / expand corpus"]
    C --> C4["Download available OA PDFs"]
    C --> C5["Build Article Eater jobs"]

    C1 --> D["SmartImporter + CitationParser"]
    D --> E["DOIResolver"]
    E --> E1["OpenAlex metadata"]
    E --> E2["Crossref metadata"]
    E1 --> F["Normalize paper record"]
    E2 --> F

    C3 --> G["BoundedExpander / Bibliographer"]
    G --> G1["OpenAlex citations + references"]
    G1 --> H["ExpansionScorer"]
    H --> I{"Taxonomy relevance >= threshold?"}
    I -- "no" --> I1["Reject / keep out of corpus"]
    I -- "yes" --> J["expansion_queue pending"]
    J --> F

    C2 --> K["PDFCataloger / PDFWatcher / ZoteroImporter"]
    K --> K1["Extract DOI from filename or first pages"]
    K --> K2["Match by DOI, title, authors/year"]
    K2 --> L["Store pdf_path, sha256, bytes"]

    F --> M["SQLite papers table"]
    M --> N["Classification / triage"]
    N --> N1["TaxonomyScorer / HierarchicalScorer"]
    N1 --> O{"triage_decision"}
    O -- "reject" --> O1["Not sent to Article Eater"]
    O -- "review" --> O2["HITL queue / needs review"]
    O -- "send_to_eater" --> P["Candidate for PDF acquisition"]

    P --> Q{"Does paper already have pdf_path?"}
    Q -- "yes" --> Z["Ready gate"]
    Q -- "no" --> R["PDFDownloader"]

    R --> R1["Unpaywall API"]
    R1 --> R2{"OA PDF URL found?"}
    R2 -- "yes" --> R3["Download PDF"]
    R3 --> L
    R2 -- "no" --> S["Mark missing PDF / needs acquisition"]

    S --> T["ZoteroExporter"]
    T --> T1["Export RIS/CSV of papers needing PDFs"]
    T1 --> U["User imports to Zotero"]
    U --> U1["Zotero Find Available PDF"]
    U1 --> U2["UCSD proxy / VPN / OpenAthens in normal browser context"]
    U2 --> V{"PDF attached in Zotero?"}
    V -- "yes" --> W["ZoteroImporter copies PDF into Article Finder"]
    V -- "no" --> X["Manual download / drop PDF into inbox"]
    X --> K
    W --> L

    L --> M
    Z --> Y{"Readiness checks"}
    M --> Z
    Y --> Y1["triage_decision == send_to_eater or status filter matches"]
    Y --> Y2["pdf_path exists"]
    Y --> Y3["PDF hash + byte count computable"]
    Y --> Y4["paper metadata satisfies ae.paper.v1"]

    Y1 --> AA["JobBundleBuilder v2"]
    Y2 --> AA
    Y3 --> AA
    Y4 --> AA

    AA --> AB["Job bundle directory"]
    AB --> AB1["paper.pdf"]
    AB --> AB2["paper.json"]
    AB --> AB3["abstract.txt optional"]
    AB --> AB4["citations.json optional"]
    AB --> AC["Article Eater ready"]
```

## Operational Sequence

1. User starts from CLI, UI, or `discover`.
2. Article Finder imports or discovers candidate papers.
3. DOI metadata is resolved through OpenAlex and Crossref, then stored in `papers`.
4. Papers are classified against the taxonomy and assigned a triage decision.
5. Papers with `triage_decision = send_to_eater` need a valid local `pdf_path`.
6. Open-access PDFs are downloaded through Unpaywall.
7. Paywalled PDFs are routed through Zotero/UCSD or local inbox/manual import.
8. Once `pdf_path`, hash, byte count, and metadata are present, `JobBundleBuilder` creates the Article Eater bundle.

## Current PDF Acquisition Design

Article Finder intentionally uses legal and stable acquisition layers:

- `PDFDownloader`: Unpaywall open-access PDF lookup and download.
- `ZoteroExporter`: exports missing PDFs to RIS/CSV for Zotero.
- `ZoteroImporter`: imports Zotero-attached PDFs back into Article Finder.
- `PDFCataloger` / `PDFWatcher`: imports manually collected PDFs from folders.

This is the right design for UCSD access because Zotero and the user's normal browser session handle institutional authentication better than automated browser scraping.

## Ready For Article Eater

A paper is effectively ready when:

- It is selected by status/triage, usually `send_to_eater`.
- It has `pdf_path`.
- The PDF exists on disk.
- `pdf_sha256` and `pdf_bytes` can be computed.
- Required `ae.paper.v1` metadata is present: `paper_id`, `title`, `authors`, `year`, `source`, and `files`.

The bundle output is:

```text
job_<paper_id>_<timestamp>/
  paper.pdf
  paper.json
  abstract.txt       optional
  citations.json     optional
```

## Gaps To Watch

- `eater_interface/pipeline.py::acquire_pdfs` is still a stub, while the actual acquisition implementation lives in `ingest/pdf_downloader.py`.
- `search/discovery_orchestrator.py::_run_acquisition_phase` expects `attempted` and `not_available`, but `PDFDownloader.download_all()` currently returns `total` and `failed`.
- Paywalled PDFs should flow through Zotero/manual inbox rather than automated publisher-browser login.
