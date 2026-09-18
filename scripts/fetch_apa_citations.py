#!/usr/bin/env python3
"""fetch_apa_citations.py — resolve APA citations from DOIs via doi.org content
negotiation (David 2026-09-09: "if you have the doi can't you get the apa
citation quickly"). Adds apa_citation to paper_bibliographic in BOTH canonical
DBs and patches the live field batch. Checkpointed, gentle (0.7s spacing,
backoff on 429/5xx), batch papers prioritized. Usage:
    python3 scripts/fetch_apa_citations.py [--limit N]
"""
import sqlite3, json, sys, time, urllib.request, re, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
BATCH = AF / "data/topic_comparison/field_batch_2026-09-09"
CKPT = AF / "data/topic_comparison/full1760_2026-09-09/apa_checkpoint.json"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def fetch_apa(doi, tries=3):
    url = "https://doi.org/" + urllib.parse.quote(doi)
    delay = 8
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "text/x-bibliography; style=apa",
                "User-Agent": "AE-corpus (mailto:dkirsh@gmail.com)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                s = r.read().decode("utf-8", "replace").strip()
                return re.sub(r"\s+", " ", s) if 20 < len(s) < 1200 else None
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if a < tries - 1: time.sleep(delay); delay *= 2
            else: return None
        except Exception:
            if a < tries - 1: time.sleep(3)
            else: return None

import urllib.parse
limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None

# gather DOIs: bibliographic table first, drive catalogue as supplement
con = sqlite3.connect(f"file:{AE}/data/article_eater_lifecycle.db?mode=ro", uri=True)
dois = {p: d for p, d in con.execute(
    "SELECT paper_id, doi FROM paper_bibliographic WHERE doi IS NOT NULL AND doi!=''")}
CATP = Path("/private/tmp/claude-501/-Users-davidusa-REPOS-New-VR-Platform/b07ed661-0ea6-4535-8b9d-cd0200658a81/scratchpad/drive_catalogue/pdf_holdings.jsonl")
if CATP.exists():
    for line in CATP.read_text().splitlines():
        try:
            h = json.loads(line)
            if h.get("doi"): dois.setdefault(h["paper_id"], h["doi"])
        except Exception: pass
print(f"papers with a DOI: {len(dois)}")

batch_ids = [t["paper_id"] for t in json.loads((BATCH / "tasks.json").read_text())["tasks"]]
order = [p for p in batch_ids if p in dois] + sorted(p for p in dois if p not in set(batch_ids))
if limit: order = order[:limit]
done = json.loads(CKPT.read_text()) if CKPT.exists() else {}

got = miss = 0
for i, pid in enumerate(order):
    if pid in done: continue
    apa = fetch_apa(dois[pid].strip())
    done[pid] = apa or ""
    got += bool(apa); miss += (not apa)
    CKPT.write_text(json.dumps(done))
    time.sleep(0.7)
    if (i + 1) % 50 == 0: print(f"  {i+1}/{len(order)} fetched={got} miss={miss}")

apa_map = {p: a for p, a in done.items() if a}
print(f"APA citations resolved: {len(apa_map)} (this run: +{got}, miss {miss})")

# write into both DBs (additive column)
sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000")
    cols = [r[1] for r in cx.execute("PRAGMA table_info('paper_bibliographic')")]
    if "apa_citation" not in cols:
        cx.execute("ALTER TABLE paper_bibliographic ADD COLUMN apa_citation TEXT")
    cx.executemany("UPDATE paper_bibliographic SET apa_citation=? WHERE paper_id=?",
                   [(a, p) for p, a in apa_map.items()])
    # papers with a citation but no bibliographic row yet
    have = {r[0] for r in cx.execute("SELECT paper_id FROM paper_bibliographic")}
    cx.executemany("INSERT INTO paper_bibliographic (paper_id, doi, apa_citation, source, imported_at) VALUES (?,?,?,?,?)",
                   [(p, dois[p], a, "doi_org_apa", NOW) for p, a in apa_map.items() if p not in have])
    cx.commit()
    n = cx.execute("SELECT COUNT(*) FROM paper_bibliographic WHERE apa_citation IS NOT NULL").fetchone()[0]
    print(f"{label}: rows with apa_citation = {n}")
    cx.close()

# patch batch
doc = json.loads((BATCH / "tasks.json").read_text())
np = 0
for t in doc["tasks"]:
    a = apa_map.get(t["paper_id"])
    if a: t["apa"] = a; np += 1
(BATCH / "tasks.json").write_text(json.dumps(doc, indent=1))
print(f"batch tasks with APA: {np}/{len(doc['tasks'])}")
