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

    got, missing, failed = [], [], []
    for i, p in enumerate(with_doi, 1):
        r = dl.download_pdf(p["paper_id"])
        if r.get("success"):
            got.append((p, r))
            mark = "cached" if r.get("cached") else "downloaded"
        elif "not" in str(r.get("error", "")).lower() or r.get("no_oa"):
            missing.append((p, r)); mark = "no OA copy"
        else:
            failed.append((p, r)); mark = f"FAILED: {r.get('error')}"
        print(f"[{i}/{len(with_doi)}] {mark:<28} {p['doi']}")

    print(f"\n=== {args.tag or args.source} ===")
    print(f"have PDF now : {len(got)}")
    print(f"no OA copy   : {len(missing)}")
    print(f"failed       : {len(failed)}")
    if missing:
        print("\nroute these through Zotero / UCSD library "
              "(`python3 cli/main.py zotero export --format ris`):")
        for p, _ in missing:
            print(f"   {p['doi']:<42} {(p['title'] or '')[:55]}")
    if failed:
        print("\nfailures worth reading rather than retrying:")
        for p, r in failed:
            print(f"   {p['doi']:<42} {r.get('error')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
