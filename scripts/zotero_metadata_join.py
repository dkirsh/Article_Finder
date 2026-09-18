#!/usr/bin/env python3
"""zotero_metadata_join.py — definitive local bibliographic join (David 2026-09-09:
"i'm sure we have metadata for all the pdf's somewhere").

Join path: unified registry papers.zotero_folder (attachment storage key, 1,341/1,448)
-> zotero.sqlite items.key -> itemAttachments.parentItemID -> parent item's
title / publication / date / DOI / creators. Zotero DB opened READ-ONLY with
immutable=1 (safe while Zotero runs; zero writes).

Then ONE merged patch of the field batch tasks.json, precedence:
Zotero (authoritative, human-curated) > unified registry > OpenAlex checkpoint.
Also writes the full mapping to data/topic_comparison/full1760_2026-09-09/
metadata_local_zotero.jsonl for corpus-wide reuse (drive catalogue enrichment)."""
import sqlite3, json, re
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
BATCH = AF / "data/topic_comparison/field_batch_2026-09-09"
OUT = AF / "data/topic_comparison/full1760_2026-09-09"
Z = "/Users/davidusa/Zotero/zotero.sqlite"

# 1. paper_id -> zotero attachment key
uni = sqlite3.connect(f"file:{AE}/data/pipeline_registry_unified.db?mode=ro", uri=True)
zkey = {pid: k for pid, k in uni.execute(
    "SELECT paper_id, zotero_folder FROM papers "
    "WHERE zotero_folder IS NOT NULL AND zotero_folder!=''")}
umeta = {r[0]: {"title": r[1], "authors": r[2], "year": r[3], "venue": r[4]}
         for r in uni.execute("SELECT paper_id,title,authors,year,venue FROM papers")}
print(f"unified: {len(zkey)} zotero keys")

# 2. zotero: attachment key -> parent item metadata
z = sqlite3.connect(f"file:{Z}?mode=ro&immutable=1", uri=True)
fields = {name: fid for fid, name in z.execute("SELECT fieldID, fieldName FROM fields")}
def fval(item, fname):
    fid = fields.get(fname)
    if not fid: return None
    r = z.execute("SELECT v.value FROM itemData d JOIN itemDataValues v ON v.valueID=d.valueID "
                  "WHERE d.itemID=? AND d.fieldID=?", (item, fid)).fetchone()
    return r[0] if r else None
att = {k: (i, p) for i, k, p in z.execute(
    "SELECT ia.itemID, it.key, ia.parentItemID FROM itemAttachments ia "
    "JOIN items it ON it.itemID = ia.itemID WHERE ia.parentItemID IS NOT NULL")}
def creators(item):
    return [f"{f or ''} {l or ''}".strip() for f, l in z.execute(
        "SELECT c.firstName, c.lastName FROM itemCreators ic "
        "JOIN creators c ON c.creatorID=ic.creatorID WHERE ic.itemID=? "
        "ORDER BY ic.orderIndex LIMIT 6", (item,))]

zot = {}
for pid, key in zkey.items():
    hit = att.get(key)
    if not hit: continue
    parent = hit[1]
    date = fval(parent, "date") or ""
    ym = re.search(r"(19|20)\d\d", date)
    zot[pid] = {"title": fval(parent, "title"),
                "venue": fval(parent, "publicationTitle") or fval(parent, "bookTitle")
                         or fval(parent, "proceedingsTitle"),
                "year": int(ym.group(0)) if ym else None,
                "doi": fval(parent, "DOI"),
                "authors": creators(parent)}
print(f"zotero join resolved: {len(zot)} papers")

# 3. corpus-wide mapping file
with open(OUT / "metadata_local_zotero.jsonl", "w") as f:
    for pid, m in sorted(zot.items()):
        f.write(json.dumps({"paper_id": pid, "source": "zotero_via_unified_key", **m}) + "\n")

# 4. one merged patch of the live batch
ck = BATCH / "enrich_checkpoint.json"
oa = json.loads(ck.read_text()) if ck.exists() else {}
doc = json.loads((BATCH / "tasks.json").read_text())
counts = {"zotero": 0, "unified": 0, "openalex": 0}
for t in doc["tasks"]:
    pid = t["paper_id"]
    for src, m in (("zotero", zot.get(pid)), ("unified", umeta.get(pid)), ("openalex", oa.get(pid))):
        if not m: continue
        used = False
        for k in ("title", "venue", "year", "authors", "doi"):
            v = m.get(k)
            if v in (None, "", []): continue
            if k == "title" and t.get("title") and len(t["title"]) >= 20 and src != "zotero":
                continue
            if not t.get(k) or (k == "title" and src == "zotero"):
                if k == "authors" and isinstance(v, str):
                    v = [s.strip() for s in re.split(r";|,(?=\s*[A-Z][a-z])", v)][:4]
                t[k] = v; used = True
        if used: counts[src] += 1
(BATCH / "tasks.json").write_text(json.dumps(doc, indent=1))
have_y = sum(1 for t in doc["tasks"] if t.get("year"))
have_v = sum(1 for t in doc["tasks"] if t.get("venue"))
print(f"batch patched from: {counts}; tasks with year: {have_y}/{len(doc['tasks'])}, "
      f"with journal: {have_v}/{len(doc['tasks'])}")
