#!/usr/bin/env python3
"""make_title_review_batch.py — David 2026-09-10: "i worry that i classified many
papers on the basis of their top title and top abstract... create a new hitl page
with the pdf with wrong title and then immediately the right title and then the
correct abstract + apa."

Selection: papers DAVID RULED whose displayed header was suspect — bib-join
quarantined, or title_integrity MISMATCH, or among his corrected batch headers.
Each task carries: the WRONG title he likely saw (from the quarantined mapping),
the TRUSTED title (his corrections > gold registry > validated bib > text), the
trusted abstract, clean APA (non-SUSPECT only), and his current ruling.
Output: data/topic_comparison/title_review_2026-09-10/ (tasks.json, papers/,
hitl_review_viewer.html, served with the same hitl_serve.py)."""
import json, sqlite3, shutil, re
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
SRC = AF / "data/topic_comparison/field_batch_2026-09-09"
OUT = AF / "data/topic_comparison/title_review_2026-09-10"
(OUT / "papers").mkdir(parents=True, exist_ok=True)

rulings = {}
for l in open(SRC / "judgments_autosave.jsonl"):
    r = json.loads(l); rulings[r["paper_id"]] = r

wrong = {}
bad = AF / "data/topic_comparison/full1760_2026-09-09/metadata_local_zotero.jsonl.QUARANTINED_bad_join"
if bad.exists():
    for l in bad.read_text().splitlines():
        try:
            m = json.loads(l)
            if m.get("title"): wrong[m["paper_id"]] = m["title"]
        except Exception: pass

con = sqlite3.connect(f"file:{AE}/data/article_eater_lifecycle.db?mode=ro", uri=True)
bib = {r[0]: {"title": r[1], "abstract": r[2], "apa": r[3], "src": r[4], "trust": r[5]}
       for r in con.execute("SELECT paper_id,title,abstract,apa_citation,source,title_trust FROM paper_bibliographic")}
mism = {r[0] for r in con.execute("SELECT paper_id FROM title_integrity WHERE status='MISMATCH'")}
qset = {p for p, b in bib.items() if b["src"] == "QUARANTINED_bad_bib_join_2026-09-10"}

def norm(t): return set(re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()) - {"the","a","of","and","in","on"}
def jac(a, b):
    A, B = norm(a), norm(b)
    return len(A & B) / max(1, len(A | B))

tasks = []
for pid, r in sorted(rulings.items()):
    suspect = pid in qset or pid in mism or pid in wrong
    if not suspect: continue
    b = bib.get(pid, {})
    right = b.get("title")
    wt = wrong.get(pid)
    if wt and right and jac(wt, right) >= 0.7: continue   # header was fine after all
    src = SRC / "papers" / f"{pid}.txt"
    if not src.exists(): continue
    shutil.copy(src, OUT / "papers" / f"{pid}.txt")
    apa = b.get("apa")
    if apa and apa.startswith("SUSPECT"): apa = None
    tasks.append({"paper_id": pid,
                  "wrong_title": wt,
                  "title": right or "(no trusted title — read the text)",
                  "title_trust": b.get("trust"),
                  "abstract": (b.get("abstract") or "")[:1100] or None,
                  "apa": apa,
                  "prior_field": r["field"],
                  "prior_secondary": r.get("field_secondary"),
                  "cluster": r.get("cluster") or [pid],
                  "text_file": f"papers/{pid}.txt"})
(OUT / "tasks.json").write_text(json.dumps(
    {"schema": "hitl_tasks.v1", "mode": "title_review", "created": "2026-09-10-review",
     "note": "Re-confirmation of rulings possibly made under a wrong header title. Wrong-seen title shown struck through; trusted title, abstract, APA beneath; prior ruling preselected.",
     "tasks": tasks}, indent=1))
shutil.copy(AF / "ui/hitl_review_viewer.html", OUT / "hitl_review_viewer.html")
shutil.copy(AF / "scripts/hitl_serve.py", OUT / "hitl_serve.py")
print(f"title-review batch: {len(tasks)} of your {len(rulings)} rulings had suspect headers")
print(f"serve: cd {OUT} && python3 hitl_serve.py 8767 -> http://localhost:8767/hitl_review_viewer.html")
