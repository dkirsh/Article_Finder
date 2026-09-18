#!/usr/bin/env python3
"""quarantine_bad_bib_join.py — repair the 2026-09-09 BibTeX-join corruption
(David caught it via wrong batch titles; probe: bib agrees with the trusted gold
registry only 57%). Trust hierarchy for titles: gold registry > David's explicit
corrections > validated bib (agrees with gold or text) > text heading (junk-
filtered) > none. Unvalidated bib rows are QUARANTINED (fields stripped, source
flagged) in BOTH canonical DBs; batch headers rebuilt; APA rows whose DOI came
from a quarantined bib row are flagged suspect. Nothing deleted; all reversible."""
import json, re, sqlite3, sys, glob, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
B = AF / "data/topic_comparison/field_batch_2026-09-09"
OUT = AF / "data/topic_comparison/full1760_2026-09-09"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
DAVID = {
 "PDF-0084": "The Effect of Crowding on Human Task Performance",
 "PDF-0009": "Speech Privacy in Buildings",
 "PDF-0088": "The Psychology, Geography, and Architecture of Horror: How Places Creep Us Out",
 "PDF-0232": "Function as the Basis of Psychiatric Ward Design",
 "PDF-0115": "Human Factors in Lighting",
 "PDF-0178": "Spatial Navigation and Negative Emotions: The Effect of Emotion Processing on Wayfinding and Visuospatial Working Memory",
 "PDF-0116": "Visual perception of materials and their properties",
 "PDF-1341": "Perceiving layout and knowing distances: The integration, relative potency, and contextual use of different information about depth",
}
JUNK = re.compile(r"^(building and environment|the design journal|physiology|routledge|frontiers in|journal of|cities|elsevier|proceedings)\b", re.I)

def norm(t): return set(re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()) - {"the","a","of","and","in","on","for","to"}
def jac(a, b):
    A, B_ = norm(a), norm(b)
    return len(A & B_) / max(1, len(A | B_))

g = sqlite3.connect(f"file:{AE}/data/verification_runs/v7_gold_extraction_registry.db?mode=ro", uri=True)
gold = dict(g.execute("SELECT paper_id, title FROM gold_papers"))
ti = {}
con = sqlite3.connect(f"file:{AE}/data/article_eater_lifecycle.db?mode=ro", uri=True)
for pid, tt in con.execute("SELECT paper_id, text_title FROM title_integrity"):
    if tt and not JUNK.match(tt): ti[pid] = tt

sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
stats = {"validated_bib": 0, "quarantined": 0, "gold_restored": 0, "david": 0, "apa_flagged": 0}
for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000")
    cols = [r[1] for r in cx.execute("PRAGMA table_info('paper_bibliographic')")]
    if "title_trust" not in cols:
        cx.execute("ALTER TABLE paper_bibliographic ADD COLUMN title_trust TEXT")
    rows = cx.execute("SELECT paper_id, title, doi, source, apa_citation FROM paper_bibliographic").fetchall()
    first = True
    for pid, btitle, bdoi, src, apa in rows:
        gt, dt, tt = gold.get(pid), DAVID.get(pid), ti.get(pid)
        ref = dt or gt or tt
        if dt:
            cx.execute("UPDATE paper_bibliographic SET title=?, title_trust='human_david' WHERE paper_id=?", (dt, pid))
            if label == "AE": stats["david"] += 1
        elif src == "zotero_bib_export" and ref and btitle and jac(btitle, ref) >= 0.45:
            cx.execute("UPDATE paper_bibliographic SET source='zotero_bib_export_validated', title_trust='validated' WHERE paper_id=?", (pid,))
            if label == "AE": stats["validated_bib"] += 1
        elif src == "zotero_bib_export":
            newt = gt or tt
            cx.execute("""UPDATE paper_bibliographic SET title=?, venue=NULL, year=NULL,
                          doi=NULL, authors_json='[]', abstract=NULL,
                          source='QUARANTINED_bad_bib_join_2026-09-10',
                          title_trust=? WHERE paper_id=?""",
                       (newt, "gold_registry" if gt else ("text_heading" if tt else None), pid))
            if apa and bdoi:
                cx.execute("UPDATE paper_bibliographic SET apa_citation='SUSPECT: '||apa_citation "
                           "WHERE paper_id=? AND apa_citation NOT LIKE 'SUSPECT:%'", (pid,))
                if label == "AE": stats["apa_flagged"] += 1
            if label == "AE": stats["quarantined"] += 1
        elif gt and (not btitle or jac(btitle, gt) < 0.45):
            cx.execute("UPDATE paper_bibliographic SET title=?, title_trust='gold_registry' WHERE paper_id=?", (gt, pid))
            if label == "AE": stats["gold_restored"] += 1
        if first: cx.commit(); first = False   # one-example commit
    cx.commit(); cx.close()
print("DB repair:", stats)

# batch headers: rebuild titles by trust; strip unvalidated bib venue/year/authors
cx = get_lifecycle_db_connection()
fixed = dict(cx.execute("SELECT paper_id, title FROM paper_bibliographic WHERE title IS NOT NULL"))
qset = {p for (p,) in cx.execute("SELECT paper_id FROM paper_bibliographic WHERE source='QUARANTINED_bad_bib_join_2026-09-10'")}
cx.close()
doc = json.loads((B / "tasks.json").read_text())
nt = ns = 0
for t in doc["tasks"]:
    pid = t["paper_id"]
    best = DAVID.get(pid) or gold.get(pid) or None
    if best and jac(t.get("title"), best) < 0.9:
        t["title"] = best; nt += 1
    elif pid in qset:
        t["title"] = fixed.get(pid) or ti.get(pid) or t.get("title")
        for k in ("venue", "year", "authors", "apa"): t.pop(k, None)
        ns += 1
(B / "tasks.json").write_text(json.dumps(doc, indent=1))
print(f"batch headers: {nt} titles corrected, {ns} quarantined-stripped")
bad = OUT / "metadata_local_zotero.jsonl"
if bad.exists(): bad.rename(OUT / "metadata_local_zotero.jsonl.QUARANTINED_bad_join")
print("metadata_local_zotero.jsonl -> .QUARANTINED_bad_join")
