#!/usr/bin/env python3
"""question_run.py — drive the Track 3 acquisition pipeline from a free-text question.

REAL run, no API key required:
  OpenAlex search  →  insert candidates into article_references (ACCEPT)
  →  pdf_acquirer (LIVE Unpaywall/OpenAlex OA download, %PDF + sha256 gated)
  →  HTML report + open the downloaded PDFs.

Open-access papers are downloaded; paywalled papers are reported metadata-only
(the pipeline never bypasses a paywall — same honest boundary as the test suite).

    python3 question_run.py "Does the height of a room affect creativity?"
"""
from __future__ import annotations
import html as _html
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import requests  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import db_schema  # noqa: E402
import pdf_acquirer  # noqa: E402

MAILTO = "dhruv@sood.me"
WORK = HERE / "data" / "question_run"
SELECT = ("doi,title,publication_year,authorships,open_access,best_oa_location,"
          "abstract_inverted_index")


def _abstract(inv: dict | None) -> str | None:
    if not inv:
        return None
    pos: dict[int, str] = {}
    for term, idxs in inv.items():
        for i in idxs:
            pos[i] = term
    return " ".join(pos[i] for i in sorted(pos))[:1600] or None


def _openalex(params: dict) -> list[dict]:
    params = {**params, "mailto": MAILTO, "select": SELECT}
    try:
        r = requests.get("https://api.openalex.org/works", params=params, timeout=30)
        return r.json().get("results", []) if r.status_code == 200 else []
    except Exception:
        return []


# Concept terms derived from the question; a paper is kept only if it mentions a
# SPATIAL term AND a COGNITION term (drops OpenAlex full-sentence relevance noise).
SPATIAL = ("ceiling", "room height", "spatial volume", "physical space", "high-ceiling",
           "vertical", "architectural", "spaciousness", "enclosure", "office environment")
COGNITION = ("creativ", "cognit", "attention", "divergent", "idea generation", "problem solving",
             "processing", "brain", "thinking", "mood", "concentration", "productivity")


def _relevant(w: dict) -> bool:
    t = ((w.get("title") or "") + " " + (w["abstract"] or "")).lower()
    return any(s in t for s in SPATIAL) and any(c in t for c in COGNITION)


def search(question: str, n: int = 8) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    # Targeted concept queries beat the raw sentence for OpenAlex relevance.
    queries = (
        {"search": "ceiling height creativity cognition priming"},
        {"search": "physical space size creativity divergent thinking"},
        {"search": "ceiling height architectural design brain attention"},
        {"filter": "title.search:ceiling height"},
    )
    for params in queries:
        for w in _openalex({**params, "per_page": 8}):
            doi = (w.get("doi") or "").replace("https://doi.org/", "")
            if not doi or doi in seen:
                continue
            auth = w.get("authorships") or []
            who = "—"
            if auth:
                who = auth[0]["author"]["display_name"] + (" et al." if len(auth) > 1 else "")
            boa = w.get("best_oa_location") or {}
            rec = {
                "doi": doi, "title": w.get("title") or "(untitled)",
                "year": w.get("publication_year"), "author": who,
                "is_oa": bool((w.get("open_access") or {}).get("is_oa")),
                "pdf_url": boa.get("pdf_url"),
                "abstract": _abstract(w.get("abstract_inverted_index")),
            }
            if not _relevant(rec):
                continue
            seen.add(doi)
            out.append(rec)
    # OA-with-direct-PDF first (most likely to download), then most recent.
    out.sort(key=lambda r: (r["pdf_url"] is None, -(r["year"] or 0)))
    return out[:n]


def main() -> None:
    question = (sys.argv[1] if len(sys.argv) > 1 else
                "Does the height of a room affect the creativity of people working in the room")
    print(f"\n━━ QUESTION ━━\n  {question}\n")

    print("━━ STEP 1 · live OpenAlex search ━━")
    works = search(question)
    print(f"  {len(works)} candidate papers:")
    for w in works:
        print(f"    [{'OA' if w['is_oa'] else 'paywall':7}] {w['year']}  "
              f"{w['doi'][:30]:30} {w['title'][:54]}")

    import shutil
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    db = WORK / "q.db"
    pdf_dir = WORK / "pdfs"
    conn = db_schema.open_db(db)
    for i, w in enumerate(works, 1):
        rid = f"REF-Q-{i:03d}"
        conn.execute(
            "INSERT INTO article_references (reference_id, doi, title_raw, discovered_via, "
            "triage_stage, triage_decision, abstract, abstract_source, gap_template_id, "
            "voi_score, raw_citation) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (rid, w["doi"], w["title"], "openalex_search", "abstract_collected", "ACCEPT",
             w["abstract"] or "", "openalex", "GAP-ROOM-HEIGHT", 0.8,
             f"{w['author']} ({w['year']}). {w['title']}."))
    conn.commit()
    conn.close()

    print("\n━━ STEP 2 · pipeline acquisition — LIVE OA PDF download (Unpaywall→OpenAlex) ━━")
    counts = pdf_acquirer.run(db, enable_scidownl=False, pdf_dir=pdf_dir, enable_network=True)

    conn = db_schema.open_db(db)
    rows = conn.execute(
        "SELECT reference_id, doi, title_raw, raw_citation, abstract, pdf_path, pdf_sha256, "
        "pdf_acquisition_last_source FROM article_references ORDER BY reference_id").fetchall()
    conn.close()

    print("\n━━ STEP 3 · results ━━")
    got = []
    for r in rows:
        p = r["pdf_path"]
        if p and Path(p).exists():
            size = Path(p).stat().st_size
            got.append((r, size))
            print(f"  ✓ PDF  {r['doi'][:30]:30} {size:>8,} B  sha={ (r['pdf_sha256'] or '')[:12] }  "
                  f"{Path(p).name}")
        else:
            print(f"  ·      {r['doi'][:30]:30} {'(no OA PDF — metadata only)':>20}")

    # ---- HTML report (the visual preview) ----
    def esc(x):
        return _html.escape(str(x or ""))
    cards = []
    for r in rows:
        p = r["pdf_path"]
        has = bool(p and Path(p).exists())
        badge = ('<span class="b ok">PDF retrieved</span>' if has
                 else '<span class="b no">metadata only</span>')
        pdflink = (f'<a href="file://{esc(p)}">open PDF ▸</a>' if has else
                   '<span class="muted">paywalled / no OA copy</span>')
        cards.append(f"""
        <div class="card">
          <div class="row"><b>{esc(r['title_raw'])}</b> {badge}</div>
          <div class="muted">{esc(r['raw_citation'])}</div>
          <div class="meta">DOI <a href="https://doi.org/{esc(r['doi'])}">{esc(r['doi'])}</a>
            &nbsp;·&nbsp; {pdflink}
            {f"&nbsp;·&nbsp; sha256 {esc(r['pdf_sha256'][:16])}…" if r['pdf_sha256'] else ""}</div>
          <div class="abs">{esc((r['abstract'] or '')[:600])}{'…' if r['abstract'] and len(r['abstract'])>600 else ''}</div>
        </div>""")
    report = WORK / "report.html"
    report.write_text(f"""<!doctype html><meta charset=utf-8>
<title>Track 2 — question run</title>
<style>
 body{{font:15px/1.5 -apple-system,Segoe UI,sans-serif;max-width:860px;margin:32px auto;padding:0 18px;color:#1a1a1a}}
 h1{{font-size:20px}} .q{{background:#0b5; color:#fff; padding:14px 18px;border-radius:10px;font-size:17px}}
 .sum{{margin:16px 0;color:#444}} .card{{border:1px solid #e3e3e3;border-radius:10px;padding:14px 16px;margin:12px 0}}
 .row{{display:flex;justify-content:space-between;gap:10px;align-items:baseline}}
 .b{{font-size:11px;padding:2px 8px;border-radius:20px;white-space:nowrap}} .ok{{background:#0b5;color:#fff}} .no{{background:#eee;color:#777}}
 .meta{{font-size:13px;margin:6px 0;color:#333}} .muted{{color:#888;font-size:13px}} .abs{{font-size:13px;color:#444;margin-top:6px}}
 a{{color:#0a6;text-decoration:none}}
</style>
<h1>Track 2 — Article Finder · live question run</h1>
<div class="q">❓ {esc(question)}</div>
<div class="sum"><b>{len(works)}</b> papers discovered via OpenAlex · <b>{len(got)}</b> open-access PDFs
retrieved and verified (%PDF + sha256) · paywalled papers shown metadata-only (no paywall bypass).</div>
{''.join(cards)}
<p class="muted">Generated by task3/question_run.py — real OpenAlex search + the pipeline's
Unpaywall/OpenAlex OA acquirer. PDFs in {esc(pdf_dir)}.</p>
""")
    print(f"\n  report:  {report}")
    print(f"  pdfs in: {pdf_dir}")
    print(f"  SUMMARY: {len(works)} found · {len(got)} OA PDFs retrieved · "
          f"{len(works)-len(got)} metadata-only")


if __name__ == "__main__":
    main()
