#!/usr/bin/env python3
"""title_integrity_audit.py — corpus-wide detector for the wrong-title defect
David caught during HITL (2026-09-10): the paper_id<->text axis is sound, but
metadata titles are misaligned for a subset, so typing/topicking may have run on
the wrong title+abstract.

Method: extract the paper's OWN title from its text (first markdown heading /
first plausible title line), compare to the metadata title (paper_bibliographic,
falling back to the corpus-run title) by token Jaccard. Low overlap = MISMATCH.
David's explicit corrections are loaded as human anchors (provenance: chat
2026-09-10) and always win. Writes an additive title_integrity table to both
canonical DBs plus a JSON report. Read-only against text; additive DB writes."""
import json, re, glob, sqlite3, sys, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
OUT = AF / "data/topic_comparison/full1760_2026-09-09"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

# David's corrections, verbatim from chat 2026-09-10 (human, final)
DAVID = {
 "PDF-0084": "The Effect of Crowding on Human Task Performance",
 "PDF-0009": "Speech Privacy in Buildings",
 "PDF-0088": "The Psychology, Geography, and Architecture of Horror: How Places Creep Us Out",
 "PDF-0232": "Function as the Basis of Psychiatric Ward Design",  # or: Notes on the Perceptual World of Schizophrenic Patients (David flagged both)
 "PDF-0115": "Human Factors in Lighting",
 "PDF-0178": "Spatial Navigation and Negative Emotions: The Effect of Emotion Processing on Wayfinding and Visuospatial Working Memory",
 "PDF-0116": "Visual perception of materials and their properties",
 "PDF-1341": "Perceiving layout and knowing distances: The integration, relative potency, and contextual use of different information about depth",
}

def text_title(pid):
    for sub in ("docling", "ocr_canonical", "mathpix"):
        for f in sorted(glob.glob(f"{AE}/data/papers/{pid}/{sub}/*")):
            if not f.lower().endswith((".md", ".mmd", ".txt")): continue
            try: t = open(f, errors="replace").read()[:8000]
            except OSError: continue
            m = re.search(r"^##?\s+(.{12,180})$", t, re.M)
            if m: return m.group(1).strip(" #")
            for line in t.splitlines():
                s = line.strip(" #*\t")
                if 15 < len(s) < 180 and s.count(" ") > 2 and not re.match(
                        r"(abstract|keywords|doi|www|http|\d|received|accepted|copyright|journal of)", s, re.I):
                    return s
    return None

def norm(t): return set(re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()) - {"the","a","of","and","in","on","for","to"}
def jac(a, b):
    A, B = norm(a), norm(b)
    return len(A & B) / max(1, len(A | B))

con = sqlite3.connect(f"file:{AE}/data/article_eater_lifecycle.db?mode=ro", uri=True)
meta = dict(con.execute("SELECT paper_id, title FROM paper_bibliographic WHERE title IS NOT NULL"))
run_titles = {}
for l in open(OUT / "typer_v1_results.jsonl"):
    r = json.loads(l)
    run_titles[r["paper_id"]] = re.sub(r"^\[from text\]\s*", "", r.get("title") or "")
pids = sorted(run_titles)

rows, mism, nocheck = [], 0, 0
for i, pid in enumerate(pids):
    mt = meta.get(pid) or run_titles.get(pid) or ""
    tt = text_title(pid)
    dv = DAVID.get(pid)
    if dv:
        status = "HUMAN_CORRECTED"
    elif not tt or not mt:
        status = "UNCHECKABLE"; nocheck += 1
    else:
        j = jac(mt, tt)
        status = "OK" if j >= 0.45 else "MISMATCH"
        if status == "MISMATCH": mism += 1
    rows.append((pid, mt[:250] or None, (tt or "")[:250] or None,
                 round(jac(mt, tt), 2) if (mt and tt) else None,
                 status, dv, NOW))
    if (i + 1) % 400 == 0: print(f"...{i+1}/{len(pids)}")

DDL = """CREATE TABLE IF NOT EXISTS title_integrity (
  paper_id TEXT PRIMARY KEY, meta_title TEXT, text_title TEXT, jaccard REAL,
  status TEXT NOT NULL, human_correct_title TEXT, checked_at TEXT NOT NULL)"""
sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000"); cx.execute(DDL)
    cx.executemany("INSERT OR REPLACE INTO title_integrity VALUES (?,?,?,?,?,?,?)", rows)
    cx.commit(); cx.close()

report = {"checked_at": NOW, "papers": len(rows), "mismatch": mism,
          "human_corrected": len(DAVID), "uncheckable": nocheck,
          "ok": len(rows) - mism - len(DAVID) - nocheck,
          "mismatches": [{"paper_id": p, "meta": m, "text": t, "j": j}
                         for p, m, t, j, s, d, _ in rows if s == "MISMATCH"][:400]}
(OUT / "title_integrity_report.json").write_text(json.dumps(report, indent=1))
print(f"papers={len(rows)} OK={report['ok']} MISMATCH={mism} "
      f"human_corrected={len(DAVID)} uncheckable={nocheck}")
for m in report["mismatches"][:10]:
    print(f"  {m['paper_id']} j={m['j']}\n    meta: {str(m['meta'])[:80]}\n    text: {str(m['text'])[:80]}")
