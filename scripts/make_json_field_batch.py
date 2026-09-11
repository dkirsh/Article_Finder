#!/usr/bin/env python3
"""make_json_field_batch.py — offline metadata-record HITL for David's flight
(2026-09-11). One task per paper: all JSON fields (title/authors/year/venue/
doi/apa/abstract) with provenance chips, editable, full text beneath.
Ordered needs-human-first: suspect APA or missing APA, missing/dirty abstract,
weak title trust float to the front; fully-verified records go last.
Everything local — texts copied in, no network needed in flight.
Output: data/topic_comparison/json_field_batch_2026-09-11/"""
import json, sqlite3, shutil, glob, re
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Finder_v3_2_3"
AEREPO = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path(AE)
OUT = AF / "data/topic_comparison/json_field_batch_2026-09-11"
(OUT / "papers").mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(f"file:{AEREPO}/data/article_eater_lifecycle.db?mode=ro", uri=True)
cols = [r[1] for r in con.execute("PRAGMA table_info('paper_bibliographic')")]
rows = con.execute("SELECT paper_id,title,venue,year,doi,authors_json,abstract,apa_citation,"
                   "source,title_trust,abstract_quality FROM paper_bibliographic").fetchall()
rulings = {r[0]: r[1] for r in con.execute("SELECT paper_id, field FROM field_rulings_human")}

def load_text(pid):
    txt = ""
    for sub in ("docling", "ocr_canonical", "mathpix"):
        for f in glob.glob(f"{AEREPO}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: txt += open(f, errors="replace").read()
                except OSError: pass
        if len(txt) > 3000: break
    return txt or "(no text layer found)"

tasks = []
for pid, title, venue, year, doi, aj, ab, apa, src, trust, aq in rows:
    apa_status = ("suspect" if (apa or "").startswith("SUSPECT") else
                  "verified" if apa else "missing")
    need = 0
    if apa_status != "verified": need += 3
    if not ab or aq in (None, "dirty_flagged", "none"): need += 3
    elif aq == "repaired_mechanical": need += 1
    if trust not in ("human_david", "gold_registry", "validated"): need += 2
    if not year: need += 1
    try: authors = json.loads(aj or "[]")
    except Exception: authors = []
    tasks.append((need, {"paper_id": pid,
        "fields": {"title": title, "authors": authors, "year": year, "venue": venue,
                   "doi": doi, "apa": (apa or "").replace("SUSPECT: ", "") or None,
                   "abstract": ab},
        "prov": {"title_trust": trust, "source": src, "apa_status": apa_status,
                 "abstract_quality": aq, "david_field_ruling": rulings.get(pid)},
        "text_file": f"papers/{pid}.txt"}))
tasks.sort(key=lambda x: -x[0])
for _, t in tasks:
    (OUT / "papers" / f"{t['paper_id']}.txt").write_text(load_text(t["paper_id"]))
(OUT / "tasks.json").write_text(json.dumps(
    {"schema": "hitl_tasks.v1", "mode": "json_fields", "created": "2026-09-11-json",
     "note": "Metadata-record editor, needs-human-first ordering. Fully offline. Human edits carry provenance human_david_json_review and outrank machine values.",
     "tasks": [t for _, t in tasks]}, indent=1))
shutil.copy(AF / "ui/hitl_json_viewer.html", OUT / "hitl_json_viewer.html")
shutil.copy(AF / "scripts/hitl_serve.py", OUT / "hitl_serve.py")
hi = sum(1 for n, _ in tasks if n >= 5)
print(f"json-field batch: {len(tasks)} records ({hi} high-need at the front)")
print(f"serve OFFLINE: cd {OUT} && python3 hitl_serve.py 8768 -> http://localhost:8768/hitl_json_viewer.html")
