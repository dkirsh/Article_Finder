#!/usr/bin/env python3
"""
Download PDFs for a named subset of papers, selected by tag or by import source.

Why this exists: `cli/main.py download` takes no selector. It calls
PDFDownloader.download_all() with no status filter, which pulls
db.search_papers(limit=10000) -- the whole corpus in arbitrary order -- and
then downloads the first N of those that lack a PDF. Running it after an
import does NOT download the papers you just imported. This script does.

    # see what would be attempted, touch nothing, no network
    python3 scripts/download_by_tag.py --tag acoustics --dry-run

    # the real run (needs network and an Unpaywall email)
    python3 scripts/download_by_tag.py --tag acoustics --email you@example.com

    # or select by the import that created them
    python3 scripts/download_by_tag.py --source acoustics_room_perception_2026-09-11 --dry-run

Only open-access PDFs are retrieved, through Unpaywall, which is what
ingest/pdf_downloader.py already does. Closed papers are reported as
not_available and are the ones to route through the Zotero/UCSD path
(`cli/main.py zotero export`), not through this script.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import Database          # noqa: E402
from config.loader import get               # noqa: E402


def select(db, tag, source, include_done):
    where, params = [], []
    if tag:
        where.append("tags LIKE ?")
        params.append(f"%{tag}%")
    if source:
        where.append("source = ?")
        params.append(source)
    if not where:
        raise SystemExit("give --tag or --source")
    if not include_done:
        where.append("(pdf_path IS NULL OR pdf_path = '')")
    sql = ("SELECT paper_id, doi, title, year, tags, pdf_path FROM papers WHERE "
           + " AND ".join(where) + " ORDER BY year DESC, title")
    with db.connection() as conn:
        cur = conn.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _install_polite_fetch(dl, email):
    """
    Replace the PDF fetch with one that identifies itself properly.

    ingest/pdf_downloader.py sends `User-Agent: ArticleFinder/3.0` for both the
    Unpaywall lookup and the PDF fetch. The lookup is fine. The fetch is not:
    PNAS, MDPI, AIP and Taylor & Francis answer that string with HTTP 403 even
    for articles they publish as gold open access, so papers that DO have a free
    copy come back looking closed. A descriptive agent with a contact address is
    what Crossref, OpenAlex and Unpaywall all ask callers to send.

    Everything else is left alone: Unpaywall still decides whether a free copy
    exists, the file lands in the same directory under the same name, the same
    %PDF check runs, and the record is written through the same db.add_paper.
    """
    import hashlib
    import urllib.request
    from datetime import datetime
    from pathlib import Path as _Path

    ua = f"ArticleFinder/3.2.3 (+https://github.com/dkirsh/Article_Finder; mailto:{email})"
    original = dl.download_pdf

    def download_pdf(paper_id):
        paper = dl.db.get_paper(paper_id)
        if not paper or not paper.get("doi"):
            return original(paper_id)
        if paper.get("pdf_path") and _Path(paper["pdf_path"]).exists():
            return {"success": True, "path": paper["pdf_path"], "cached": True}

        url = dl.unpaywall.get_pdf_url(paper["doi"])
        if not url:
            return {"success": False, "error": "No open access PDF found"}
        try:
            safe = paper["doi"].replace("/", "_").replace(":", "_")
            out = dl.pdf_dir / f"{safe}.pdf"
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Accept": "application/pdf,*/*",
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if not data.startswith(b"%PDF"):
                return {"success": False, "error": "Downloaded file is not a PDF"}
            out.write_bytes(data)
            paper["pdf_path"] = str(out)
            paper["pdf_sha256"] = hashlib.sha256(data).hexdigest()
            paper["pdf_bytes"] = len(data)
            paper["updated_at"] = datetime.utcnow().isoformat()
            dl.db.add_paper(paper)
            return {"success": True, "path": str(out), "size": len(data)}
        except urllib.error.HTTPError as e:
            return {"success": False, "error": f"HTTP {e.code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    dl.download_pdf = download_pdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="substring match against the papers.tags column")
    ap.add_argument("--source", help="exact match against the papers.source column")
    ap.add_argument("--email", help="Unpaywall contact email; falls back to config")
    ap.add_argument("--limit", type=int, help="stop after this many papers")
    ap.add_argument("--include-done", action="store_true",
                    help="also attempt papers that already record a pdf_path")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be attempted and exit; no network, no writes")
    ap.add_argument("--polite-agent", action="store_true",
                    help=("fetch the PDF with a descriptive User-Agent carrying a contact address, "
                          "instead of ingest/pdf_downloader.py's bare 'ArticleFinder/3.0'. Several "
                          "publishers -- PNAS, MDPI, AIP, Taylor & Francis -- return HTTP 403 to the "
                          "bare string even for gold open-access articles. Unpaywall is still what "
                          "decides whether a free copy exists; this only changes how it is fetched."))
    args = ap.parse_args()

    db = Database(get("paths.database", "data/article_finder.db"))
    papers = select(db, args.tag, args.source, args.include_done)

    no_doi = [p for p in papers if not p.get("doi")]
    with_doi = [p for p in papers if p.get("doi")]
    if args.limit:
        with_doi = with_doi[:args.limit]

    print(f"selected: {len(papers)}   with DOI: {len(with_doi)}   without DOI: {len(no_doi)}")
    if no_doi:
        print("\nno DOI, so Unpaywall cannot be asked -- these need Zotero or manual retrieval:")
        for p in no_doi:
            print(f"   {p['year']}  {(p['title'] or '')[:78]}")

    if args.dry_run:
        print("\nwould attempt, in order:")
        for p in with_doi:
            print(f"   {p['doi']:<42} {(p['title'] or '')[:60]}")
        print("\nDRY RUN. Nothing fetched, nothing written.")
        return 0

    email = args.email or get("apis.unpaywall.email", get("apis.openalex.email"))
    if not email or "@" not in email:
        print("Error: a valid --email is required for Unpaywall", file=sys.stderr)
        return 2

    from ingest.pdf_downloader import PDFDownloader
    dl = PDFDownloader(db, email=email)

    if args.polite_agent:
        _install_polite_fetch(dl, email)

    # Classify on the exact strings ingest/pdf_downloader.py returns, not on a
    # substring guess. The first version of this matched "not" in the error text,
    # which put 'No open access PDF found' (the ordinary closed-paper result) into
    # FAILED and 'Downloaded file is not a PDF' (a served paywall page, which IS a
    # problem) into "no OA copy" -- exactly backwards, and it made a correct run of
    # 34 closed papers read as 34 failures.
    def classify(r):
        if r.get("success"):
            return "cached" if r.get("cached") else "downloaded"
        e = str(r.get("error", ""))
        if e == "No open access PDF found":
            return "closed"          # Unpaywall knows it; there is no free copy
        if e == "Downloaded file is not a PDF":
            return "not_a_pdf"       # an OA URL existed and served HTML
        if e == "No DOI":
            return "no_doi"
        if e.startswith("HTTP "):
            return "http_error"
        if e == "Paper not found":
            return "no_record"
        return "other"

    LABEL = {"downloaded": "downloaded", "cached": "already had it",
             "closed": "closed, no OA copy", "not_a_pdf": "OA URL served a non-PDF",
             "no_doi": "no DOI", "http_error": "HTTP error",
             "no_record": "no DB record", "other": "unclassified"}

    buckets = {k: [] for k in LABEL}
    for i, p in enumerate(with_doi, 1):
        r = dl.download_pdf(p["paper_id"])
        k = classify(r)
        buckets[k].append((p, r))
        detail = "" if k in ("downloaded", "cached", "closed") else f"  <- {r.get('error')}"
        print(f"[{i}/{len(with_doi)}] {LABEL[k]:<26} {p['doi']}{detail}")

    print(f"\n=== {args.tag or args.source} ===")
    for k in ("downloaded", "cached", "closed", "not_a_pdf", "http_error", "no_doi", "no_record", "other"):
        if buckets[k]:
            print(f"{LABEL[k]:<26} {len(buckets[k])}")

    if buckets["closed"]:
        print("\nCLOSED -- no open-access copy exists. These are the Zotero / UCSD library set")
        print("(`python3 cli/main.py zotero export --format ris`). This is an expected outcome,")
        print("not an error:")
        for p, _ in buckets["closed"]:
            print(f"   {p['doi']:<42} {(p['title'] or '')[:55]}")

    problems = buckets["not_a_pdf"] + buckets["http_error"] + buckets["other"] + buckets["no_record"]
    if problems:
        print("\nWORTH READING rather than retrying -- Unpaywall offered a copy and fetching it")
        print("did not produce an article:")
        for p, r in problems:
            print(f"   {p['doi']:<42} {r.get('error')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
