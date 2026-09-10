#!/usr/bin/env python3
"""enrich_field_batch.py — add year/journal/authors (and better titles) to the
field-only HITL batch, in place. Gentle on OpenAlex: 1 req/1.5s, exponential
backoff on 429/403, checkpoint file so reruns resume. David's rulings are
untouched (localStorage keys are paper-id based; tasks.json order preserved)."""
import json, re, time, urllib.request, urllib.parse
from pathlib import Path

BATCH = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3/data/topic_comparison/field_batch_2026-09-09")
CKPT = BATCH / "enrich_checkpoint.json"
MAILTO = "dkirsh@gmail.com"
FIELDS = "id,doi,title,publication_year,authorships,primary_location"

def get(url, tries=4):
    delay = 10
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"AE-corpus-enrich (mailto:{MAILTO})"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 403) and a < tries - 1:
                time.sleep(delay); delay *= 2
            else:
                raise
    return None

def norm(t): return set(re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split())
def jac(a, b):
    A, B = norm(a), norm(b)
    return len(A & B) / max(1, len(A | B))

doc = json.loads((BATCH / "tasks.json").read_text())
done = json.loads(CKPT.read_text()) if CKPT.exists() else {}
n_ok = n_skip = n_miss = n_err = 0
for t in doc["tasks"]:
    pid = t["paper_id"]
    if pid in done:
        t.update(done[pid]); n_skip += 1; continue
    if t.get("year"): n_skip += 1; continue
    q = t.get("title") or ""
    if len(norm(q)) < 4:
        q = (t.get("abstract") or "")[:100]
    if len(norm(q)) < 4:
        n_miss += 1; continue
    try:
        data = get("https://api.openalex.org/works?search=" + urllib.parse.quote(q[:120])
                   + f"&per-page=1&select={FIELDS}&mailto={MAILTO}")
        hits = (data or {}).get("results", [])
        if hits and jac(q, hits[0].get("title")) >= 0.55:
            w = hits[0]
            auths = [a.get("author", {}).get("display_name") for a in (w.get("authorships") or [])[:4]]
            enr = {"year": w.get("publication_year"),
                   "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
                   "authors": [a for a in auths if a],
                   "oa_doi": (w.get("doi") or "").replace("https://doi.org/", "")}
            if len(t.get("title") or "") < 20 and w.get("title"):
                enr["title"] = w["title"]
            t.update(enr); done[pid] = enr; n_ok += 1
        else:
            done[pid] = {}; n_miss += 1
    except Exception:
        n_err += 1
    CKPT.write_text(json.dumps(done))
    time.sleep(1.5)
    if (n_ok + n_miss + n_err) % 25 == 0:
        print(f"  progress: ok={n_ok} miss={n_miss} err={n_err}")

(BATCH / "tasks.json").write_text(json.dumps(doc, indent=1))
print(f"enriched={n_ok} already/skipped={n_skip} no-match={n_miss} errors={n_err} "
      f"of {len(doc['tasks'])} tasks")
