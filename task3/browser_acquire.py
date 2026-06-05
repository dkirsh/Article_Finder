#!/usr/bin/env python3
"""browser_acquire.py — assisted acquisition for publisher-blocked open-access PDFs.

Some OA publishers (MDPI, Frontiers, PeerJ…) serve their PDFs behind Cloudflare
bot protection that returns HTTP 403 to the automated Unpaywall/OpenAlex acquirer
(`pdf_acquirer.py`). The paper IS open access — a real browser reads it freely —
but datacenter/script requests are refused.

For those, a CONNECTED Claude-in-Chrome session loads the article in a real browser
(clearing the challenge) and downloads the PDF; this tool then VERIFIES (%PDF) and
RECORDS it in article_references exactly like pdf_acquirer would
(triage_stage='acquired', acquired_paper_id, pdf_path, pdf_sha256 + a lifecycle
transition), so the browser-retrieved paper is a first-class row in the lifecycle DB.

HONEST BOUNDARY: the browser step is ASSISTED, not headless — it needs an
interactive Claude-in-Chrome session. This module does the deterministic half
(detect-blocked + verify + register); the runbook for the browser half is
docs/BROWSER_ACQUISITION.md.

    python3 browser_acquire.py --check 10.3390/s24237838            # is it OA-but-blocked?
    python3 browser_acquire.py --doi 10.3390/s24237838 --pdf ~/Downloads/sensors-24-07838.pdf
"""
from __future__ import annotations
import argparse
import hashlib
import re
import shutil
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import requests  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import db_schema  # noqa: E402
import pdf_acquirer  # noqa: E402
from db_schema import DEFAULT_DB, log_transition, open_db  # noqa: E402

PDF_STORE = HERE / "data" / "pdfs"
MAILTO = "dhruv@sood.me"


def _meta(doi: str) -> dict:
    """Title / year / first author / abstract / landing+pdf URL from OpenAlex."""
    try:
        j = requests.get(f"https://api.openalex.org/works/doi:{doi}", timeout=25,
                         params={"mailto": MAILTO, "select": "title,publication_year,"
                                 "authorships,open_access,best_oa_location,primary_location,"
                                 "abstract_inverted_index"}).json()
    except Exception:
        j = {}
    inv = j.get("abstract_inverted_index") or {}
    pos: dict[int, str] = {}
    for t, idxs in inv.items():
        for i in idxs:
            pos[i] = t
    a = j.get("authorships") or []
    who = (a[0]["author"]["display_name"] + (" et al." if len(a) > 1 else "")) if a else "—"
    boa = j.get("best_oa_location") or {}
    prim = j.get("primary_location") or {}
    return {"title": j.get("title") or "", "year": j.get("publication_year"),
            "author": who, "abstract": " ".join(pos[i] for i in sorted(pos))[:1600],
            "is_oa": bool((j.get("open_access") or {}).get("is_oa")),
            "pdf_url": boa.get("pdf_url") or boa.get("landing_page_url"),
            "landing": prim.get("landing_page_url") or boa.get("landing_page_url")}


def _ref_id(doi: str) -> str:
    return "REF-" + re.sub(r"[^A-Za-z0-9]+", "-", doi).strip("-").upper()


def check(doi: str) -> dict:
    """Classify a DOI: pipeline-acquirable / OA-but-blocked (needs browser) / paywalled."""
    m = _meta(doi)
    blocked_dir = Path("/tmp")
    hit = False
    for fn in (pdf_acquirer.try_unpaywall, pdf_acquirer.try_openalex_oa):
        status, *_ = fn(doi, "PROBE", blocked_dir, enable_network=True)
        if status == "hit":
            hit = True
            break
    if hit:
        verdict = "pipeline_ok"
        msg = "the automated pipeline can fetch this (no browser needed)."
    elif m["is_oa"]:
        verdict = "oa_blocked"
        msg = ("OPEN ACCESS but the automated fetch is blocked (publisher bot wall).\n"
               f"  Browser-assisted retrieval — open in Claude-in-Chrome: {m['landing'] or m['pdf_url']}\n"
               "  then: python3 browser_acquire.py --doi %s --pdf <downloaded.pdf>" % doi)
    else:
        verdict = "paywalled"
        msg = "not open access — metadata only (the pipeline never bypasses a paywall)."
    print(f"  {doi}  [{verdict}]\n  {m['title'][:70]}\n  {msg}")
    return {"doi": doi, "verdict": verdict, **m}


def register(doi: str, pdf: Path, *, db_path: Path = DEFAULT_DB, via: str = "claude_in_chrome",
             gap: str = "GAP-ASSISTED", ref_id: str | None = None) -> dict:
    """Verify a browser-downloaded PDF and record it in the lifecycle DB."""
    pdf = Path(pdf).expanduser()
    if not pdf.exists() or pdf.read_bytes()[:5] != b"%PDF-":
        raise SystemExit(f"not a PDF (or missing): {pdf}")
    rid = ref_id or _ref_id(doi)
    PDF_STORE.mkdir(parents=True, exist_ok=True)
    dest = PDF_STORE / f"{rid}.pdf"
    shutil.copy2(str(pdf), str(dest))
    dest.chmod(0o644)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    m = _meta(doi)
    conn = open_db(db_path)
    conn.execute("DELETE FROM article_references WHERE reference_id=?", (rid,))
    conn.execute(
        "INSERT INTO article_references (reference_id,doi,title_raw,discovered_via,"
        "triage_stage,triage_decision,abstract,abstract_source,gap_template_id,voi_score,"
        "raw_citation,acquired_paper_id,pdf_path,pdf_sha256) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, doi, m["title"], via, "acquired", "ACCEPT", m["abstract"], "openalex", gap, 0.8,
         f"{m['author']} ({m['year']}). {m['title']}.", f"paper:{rid}", str(dest), sha))
    log_transition(conn, reference_id=rid, from_stage="abstract_collected", to_stage="acquired",
                   agent="browser_acquire", outcome="success",
                   notes=f"pdf={dest.name} sha256={sha[:12]} via={via}")
    conn.commit()
    conn.close()
    out = {"reference_id": rid, "doi": doi, "title": m["title"], "bytes": dest.stat().st_size,
           "sha256": sha, "pdf_path": str(dest), "via": via}
    print(f"  ✓ registered {rid}  {doi}  {out['bytes']:,} B  sha={sha[:12]}  via={via}")
    print(f"    title: {m['title'][:66]}\n    pdf:   {dest}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", metavar="DOI", help="classify a DOI (pipeline / oa_blocked / paywalled)")
    ap.add_argument("--doi", help="DOI of a browser-downloaded PDF to register")
    ap.add_argument("--pdf", type=Path, help="path to the downloaded PDF (with --doi)")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--via", default="claude_in_chrome")
    args = ap.parse_args()
    if args.check:
        check(args.check)
    elif args.doi and args.pdf:
        register(args.doi, args.pdf, db_path=args.db, via=args.via)
    else:
        ap.error("use --check DOI, or --doi DOI --pdf PATH")


if __name__ == "__main__":
    main()
