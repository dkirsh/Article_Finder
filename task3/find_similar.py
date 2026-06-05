#!/usr/bin/env python3
"""find_similar.py — "more like this": find articles related to a SEED paper and
retrieve their open-access PDFs through the Track 3 pipeline.

Workflow (all real, no API key):
  0. resolve the seed paper on OpenAlex (by DOI or by title)
  1. candidates = papers that CITE the seed (forward citations = follow-on work on
     the same topic) + OpenAlex related_works (filtered for the topic), deduped,
     seed removed
  2. insert into article_references (ACCEPT)
  3. pdf_acquirer — LIVE Unpaywall/OpenAlex OA download (%PDF + sha256 gated)
  4. HTML report + open the PDFs. Paywalled papers are metadata-only.

    python3 find_similar.py "The Influence of Ceiling Height: ..."
    python3 find_similar.py 10.1086/519146
"""
from __future__ import annotations
import html as _html
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

MAILTO = "dhruv@sood.me"
WORK = HERE / "data" / "find_similar"
SELECT = ("doi,title,publication_year,authorships,open_access,best_oa_location,"
          "abstract_inverted_index,cited_by_count")
# related_works homonym filter (drop statistical "ceiling effect", grade ceilings…)
SPATIAL = ("ceiling", "room height", "spatial", "physical space", "architectur",
           "environment", "atmospher", "spaciousness", "interior", "built ")
COGNITION = ("creativ", "cognit", "attention", "priming", "processing", "construal",
             "perception", "aesthetic", "sensory", "mood", "affect", "behavi")


def _abstract(inv):
    if not inv:
        return None
    pos = {}
    for term, idxs in inv.items():
        for i in idxs:
            pos[i] = term
    return " ".join(pos[i] for i in sorted(pos))[:1600] or None


def _get(url, params):
    try:
        r = requests.get(url, params={**params, "mailto": MAILTO}, timeout=30)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def _rec(w, relation):
    auth = w.get("authorships") or []
    who = (auth[0]["author"]["display_name"] + (" et al." if len(auth) > 1 else "")) if auth else "—"
    return {
        "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
        "title": w.get("title") or "(untitled)", "year": w.get("publication_year"),
        "author": who, "relation": relation,
        "is_oa": bool((w.get("open_access") or {}).get("is_oa")),
        "pdf_url": (w.get("best_oa_location") or {}).get("pdf_url"),
        "cited_by": w.get("cited_by_count") or 0,
        "abstract": _abstract(w.get("abstract_inverted_index")),
    }


def resolve_seed(arg: str) -> dict:
    is_doi = bool(re.match(r"^10\.\d{4,9}/\S+$", arg.strip()))
    if is_doi:
        w = _get(f"https://api.openalex.org/works/doi:{arg.strip()}",
                 {"select": "id,title,doi,related_works"})
    else:
        res = _get("https://api.openalex.org/works",
                   {"search": arg, "per_page": 1, "select": "id,title,doi,related_works"})
        w = (res.get("results") or [{}])[0]
    return w


def find(arg: str, n: int = 12) -> tuple[dict, list[dict]]:
    seed = resolve_seed(arg)
    wid = (seed.get("id") or "").split("/")[-1]
    seed_doi = (seed.get("doi") or "").replace("https://doi.org/", "")
    out, seen = [], {seed_doi}

    # (1) forward citations — papers that cite the seed, most-cited first
    cit = _get("https://api.openalex.org/works",
               {"filter": f"cites:{wid}", "sort": "cited_by_count:desc",
                "per_page": 14, "select": SELECT})
    for w in cit.get("results", []):
        r = _rec(w, "cites→seed")
        if r["doi"] and r["doi"] not in seen:
            seen.add(r["doi"]); out.append(r)

    # (2) OpenAlex related_works — filtered for the topic (drops 'ceiling effect' noise)
    rel_ids = [x.split("/")[-1] for x in (seed.get("related_works") or [])[:12]]
    if rel_ids:
        rel = _get("https://api.openalex.org/works",
                   {"filter": f"openalex_id:{'|'.join(rel_ids)}", "per_page": 12, "select": SELECT})
        for w in rel.get("results", []):
            r = _rec(w, "related")
            t = (r["title"] + " " + (r["abstract"] or "")).lower()
            if r["doi"] and r["doi"] not in seen and any(s in t for s in SPATIAL) and any(c in t for c in COGNITION):
                seen.add(r["doi"]); out.append(r)

    out.sort(key=lambda r: (r["pdf_url"] is None, -(r["cited_by"])))
    return seed, out[:n]


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "10.1086/519146"
    seed = resolve_seed(arg)
    print(f"\n━━ SEED PAPER ━━\n  {seed.get('title')}\n  DOI {(seed.get('doi') or '').replace('https://doi.org/','')}\n")

    print("━━ STEP 1 · find related articles (forward citations + related_works) ━━")
    seed, works = find(arg)
    print(f"  {len(works)} related papers:")
    for w in works:
        print(f"    [{'OA' if w['is_oa'] else 'paywall':7}|{w['relation']:10}] {w['year']}  "
              f"cited×{w['cited_by']:<4} {w['title'][:46]}")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    db, pdf_dir = WORK / "q.db", WORK / "pdfs"
    conn = db_schema.open_db(db)
    for i, w in enumerate(works, 1):
        conn.execute(
            "INSERT INTO article_references (reference_id, doi, title_raw, discovered_via, "
            "triage_stage, triage_decision, abstract, abstract_source, gap_template_id, "
            "voi_score, raw_citation) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"REF-S-{i:03d}", w["doi"], w["title"], f"openalex:{w['relation']}",
             "abstract_collected", "ACCEPT", w["abstract"] or "", "openalex",
             "GAP-SIMILAR", 0.8, f"{w['author']} ({w['year']}). {w['title']}."))
    conn.commit(); conn.close()

    print("\n━━ STEP 2 · pipeline acquisition — LIVE OA PDF download (Unpaywall→OpenAlex) ━━")
    pdf_acquirer.run(db, enable_scidownl=False, pdf_dir=pdf_dir, enable_network=True)

    conn = db_schema.open_db(db)
    rows = conn.execute("SELECT reference_id, doi, title_raw, raw_citation, abstract, "
                        "discovered_via, pdf_path, pdf_sha256 FROM article_references "
                        "ORDER BY reference_id").fetchall()
    conn.close()

    print("\n━━ STEP 3 · results ━━")
    got = 0
    for r in rows:
        p = r["pdf_path"]
        if p and Path(p).exists():
            got += 1
            print(f"  ✓ PDF  {r['doi'][:30]:30} {Path(p).stat().st_size:>9,} B  "
                  f"sha={(r['pdf_sha256'] or '')[:12]}  {Path(p).name}")
        else:
            print(f"  ·      {r['doi'][:30]:30} (no OA PDF — metadata only)")

    def esc(x):
        return _html.escape(str(x or ""))
    cards = []
    for r in rows:
        p = r["pdf_path"]; has = bool(p and Path(p).exists())
        rel = (r["discovered_via"] or "").replace("openalex:", "")
        badge = ('<span class="b ok">PDF retrieved</span>' if has
                 else '<span class="b no">metadata only</span>')
        link = (f'<a href="file://{esc(p)}">open PDF ▸</a>' if has
                else '<span class="muted">paywalled / no OA copy</span>')
        cards.append(f"""<div class="card"><div class="row"><b>{esc(r['title_raw'])}</b> {badge}</div>
          <div class="muted">{esc(r['raw_citation'])} &nbsp;·&nbsp; <span class="rel">{esc(rel)}</span></div>
          <div class="meta">DOI <a href="https://doi.org/{esc(r['doi'])}">{esc(r['doi'])}</a> &nbsp;·&nbsp; {link}</div>
          <div class="abs">{esc((r['abstract'] or '')[:560])}{'…' if r['abstract'] and len(r['abstract'])>560 else ''}</div></div>""")
    report = WORK / "report.html"
    report.write_text(f"""<!doctype html><meta charset=utf-8><title>Find similar</title>
<style>body{{font:15px/1.5 -apple-system,Segoe UI,sans-serif;max-width:880px;margin:30px auto;padding:0 18px}}
.seed{{background:#234; color:#fff;padding:14px 18px;border-radius:10px}} .seed small{{opacity:.8}}
.sum{{margin:16px 0;color:#444}} .card{{border:1px solid #e3e3e3;border-radius:10px;padding:13px 16px;margin:11px 0}}
.row{{display:flex;justify-content:space-between;gap:10px;align-items:baseline}}
.b{{font-size:11px;padding:2px 8px;border-radius:20px;white-space:nowrap}} .ok{{background:#0b5;color:#fff}} .no{{background:#eee;color:#777}}
.meta{{font-size:13px;margin:6px 0}} .muted{{color:#888;font-size:13px}} .rel{{color:#247;font-weight:600}} .abs{{font-size:13px;color:#444;margin-top:6px}} a{{color:#0a6;text-decoration:none}}</style>
<h2>Track 2 — "find articles like this"</h2>
<div class="seed">🔎 Seed: <b>{esc(seed.get('title'))}</b><br><small>DOI {esc((seed.get('doi') or '').replace('https://doi.org/',''))}</small></div>
<div class="sum"><b>{len(works)}</b> related papers (forward citations + related_works) · <b>{got}</b> open-access
PDFs retrieved &amp; verified (%PDF + sha256) · paywalled shown metadata-only (no paywall bypass).</div>
{''.join(cards)}
<p class="muted">task3/find_similar.py — OpenAlex citation graph + the pipeline's OA acquirer. PDFs in {esc(pdf_dir)}.</p>""")
    print(f"\n  report:  {report}\n  pdfs in: {pdf_dir}")
    print(f"  SUMMARY: {len(works)} related · {got} OA PDFs retrieved · {len(works)-got} metadata-only")


if __name__ == "__main__":
    main()
