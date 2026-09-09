#!/usr/bin/env python3
"""make_field_batch.py — build a field-only (in vs out of CNfA) HITL batch for David.

Contents: every paper the corpus run put in out_of_field_candidate, borderline, or
pure_neuroscience — EXCEPT the KA-ART junk-metadata block (unjudgeable until T1
repair) — with duplicate clusters collapsed to one representative each (the ruling
propagates to all members via the cluster field). Ordered most-confidently-out
first so the easy rejections come as a fast run at the start.

Output: data/topic_comparison/field_batch_2026-09-09/{tasks.json, papers/*.txt}
plus a copy of ui/hitl_field_viewer.html. Serve the folder, open the viewer,
rule with I/B/O/N keys.
"""
import json, re, glob, shutil
from pathlib import Path

AE = Path("/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery")
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
SRC = AF / "data/topic_comparison/full1760_2026-09-09"
OUT = AF / "data/topic_comparison/field_batch_2026-09-09"
(OUT / "papers").mkdir(parents=True, exist_ok=True)

rows = [json.loads(l) for l in open(SRC / "typer_v1_results.jsonl")]
clusters = json.load(open(SRC / "duplicate_clusters.json"))["clusters"]
rep = {}
for c in clusters:
    head = sorted(c)[0]
    for pid in c: rep[pid] = head
members = {}
for c in clusters: members[sorted(c)[0]] = sorted(c)

def abstract_of(pid):
    p = AE / f"data/papers/{pid}/sc_summary/gold.json"
    try:
        a = json.load(open(p)).get("abstract") or ""
        if a: return a[:900]
    except Exception: pass
    for sub in ("docling", "ocr_canonical"):
        for f in glob.glob(str(AE / f"data/papers/{pid}/{sub}/*")):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try:
                    t = open(f, errors="replace").read()[:6000]
                    m = re.search(r"abstract[:.\s]*(.{80,900})", t, re.I | re.S)
                    if m: return re.sub(r"\s+", " ", m.group(1)).strip()
                except OSError: pass
    return ""

def load_text(pid):
    txt = ""
    for sub in ("docling", "ocr_canonical", "mathpix"):
        for f in glob.glob(str(AE / f"data/papers/{pid}/{sub}/*")):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: txt += open(f, errors="replace").read() + "\n"
                except OSError: pass
        if len(txt) > 3000: break
    return txt or "(no text layer found)"

cand = [r for r in rows if r.get("field_bucket") in
        ("out_of_field_candidate", "borderline", "pure_neuroscience")]
cand = [r for r in cand if not re.search(r"KA-ART-\d+", r.get("title") or "")]
seen, picked = set(), []
order = {"out_of_field_candidate": 0, "pure_neuroscience": 1, "borderline": 2}
cand.sort(key=lambda r: (order[r["field_bucket"]], r.get("env_density", 0)))
for r in cand:
    head = rep.get(r["paper_id"], r["paper_id"])
    if head in seen: continue
    seen.add(head)
    picked.append((head, r))

tasks = []
for head, r in picked:
    (OUT / "papers" / f"{head}.txt").write_text(load_text(head))
    tasks.append({"paper_id": head,
                  "title": re.sub(r"^\[from text\]\s*", "", r.get("title") or ""),
                  "abstract": abstract_of(head),
                  "machine_bucket": r["field_bucket"],
                  "cluster": members.get(head, [head]),
                  "text_file": f"papers/{head}.txt"})
(OUT / "tasks.json").write_text(json.dumps(
    {"schema": "hitl_tasks.v1", "mode": "field_only", "created": "2026-09-09",
     "note": "In-vs-out-of-CNfA only. Duplicate clusters collapsed; a ruling covers its whole cluster. KA-ART block excluded pending metadata repair (T1).",
     "tasks": tasks}, indent=1))
shutil.copy(AF / "ui/hitl_field_viewer.html", OUT / "hitl_field_viewer.html")
covered = sum(len(t["cluster"]) for t in tasks)
print(f"field batch: {len(tasks)} rulings covering {covered} paper ids "
      f"(clusters collapsed); buckets: "
      f"{ {b: sum(1 for t in tasks if t['machine_bucket']==b) for b in order} }")
print(f"serve: cd {OUT} && python3 -m http.server 8766  ->  http://localhost:8766/hitl_field_viewer.html")
