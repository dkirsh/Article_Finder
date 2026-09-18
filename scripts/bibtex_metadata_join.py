#!/usr/bin/env python3
"""bibtex_metadata_join.py — the join that actually fits the data:
unified.zotero_folder is the numeric folder of the BibTeX export
(__Zotero whole bibliography/files/<n>/...), and each .bib entry's `file`
field names that folder. entry -> title/journal/year/authors/doi.
Patches the live field batch (Zotero-export > unified > OpenAlex checkpoint)
and writes the corpus-wide mapping for reuse."""
import sqlite3, json, re
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
BATCH = AF / "data/topic_comparison/field_batch_2026-09-09"
OUT = AF / "data/topic_comparison/full1760_2026-09-09"
BIB = Path("/Users/davidusa/REPOS/__Zotero whole bibliography/__Zotero whole bibliography.bib")

txt = BIB.read_text(errors="replace")
entries = re.split(r"\n@", txt)
print(f"bib entries: {len(entries)}")

def field(e, name):
    m = re.search(name + r"\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", e, re.I | re.S)
    return re.sub(r"[{}]", "", m.group(1)).replace("\n", " ").strip() if m else None

bynum = {}
for e in entries:
    f = field(e, "file")
    if not f: continue
    nums = set(re.findall(r"files[/\\](\d+)[/\\]", f))
    if not nums: continue
    date = field(e, "year") or field(e, "date") or ""
    ym = re.search(r"(19|20)\d\d", date)
    auth = field(e, "author")
    rec = {"title": field(e, "title"),
           "venue": field(e, "journal") or field(e, "journaltitle")
                    or field(e, "booktitle") or field(e, "publisher"),
           "year": int(ym.group(0)) if ym else None,
           "doi": field(e, "doi"),
           "authors": [a.strip() for a in auth.split(" and ")][:5] if auth else []}
    for n in nums: bynum[n] = rec
print(f"file-number -> metadata entries: {len(bynum)}")

uni = sqlite3.connect(f"file:{AE}/data/pipeline_registry_unified.db?mode=ro", uri=True)
zmap = {pid: zf for pid, zf in uni.execute(
    "SELECT paper_id, zotero_folder FROM papers WHERE zotero_folder!=''")}
joined = {pid: bynum[zf] for pid, zf in zmap.items() if zf in bynum}
print(f"papers joined: {len(joined)}/{len(zmap)}")

with open(OUT / "metadata_local_zotero.jsonl", "w") as f:
    for pid, m in sorted(joined.items()):
        f.write(json.dumps({"paper_id": pid, "source": "zotero_bib_export_via_folder_number", **m}) + "\n")

ck = BATCH / "enrich_checkpoint.json"
oa = json.loads(ck.read_text()) if ck.exists() else {}
doc = json.loads((BATCH / "tasks.json").read_text())
counts = {"bib": 0, "openalex": 0}
for t in doc["tasks"]:
    pid = t["paper_id"]
    for src, m in (("bib", joined.get(pid)), ("openalex", oa.get(pid))):
        if not m: continue
        used = False
        for k in ("title", "venue", "year", "authors", "doi"):
            v = m.get(k)
            if v in (None, "", []): continue
            if k == "title":
                if src == "bib" and v: t["title"] = v; used = True
                continue
            if not t.get(k): t[k] = v; used = True
        if used: counts[src] += 1
(BATCH / "tasks.json").write_text(json.dumps(doc, indent=1))
y = sum(1 for t in doc["tasks"] if t.get("year"))
v = sum(1 for t in doc["tasks"] if t.get("venue"))
print(f"batch patched: {counts}; year {y}/{len(doc['tasks'])}, journal {v}/{len(doc['tasks'])}")
