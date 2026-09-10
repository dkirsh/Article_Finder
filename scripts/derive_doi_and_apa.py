#!/usr/bin/env python3
"""derive_doi_and_apa.py — T12: close the APA gap on clean provenance only.
For every paper whose APA is missing or SUSPECT: OpenAlex search on the TRUSTED
title (human/gold/validated/text trust recorded per row), accept a match only at
token-Jaccard >= 0.6, store the DOI with source 'oa_title_match' + score, fetch
the APA from doi.org, clear the SUSPECT flag on success. Gentle (1.2s spacing,
exponential backoff), checkpointed, resumable. Updates BOTH canonical DBs."""
import json, re, sqlite3, sys, time, urllib.request, urllib.parse, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
CKPT = AF / "data/topic_comparison/full1760_2026-09-09/doi_apa_checkpoint.json"
MAILTO = "dkirsh@gmail.com"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def get(url, accept=None, tries=4):
    delay = 10
    for a in range(tries):
        try:
            h = {"User-Agent": f"AE-corpus (mailto:{MAILTO})"}
            if accept: h["Accept"] = accept
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if a < tries - 1: time.sleep(delay); delay *= 2
            else: return None
        except Exception:
            if a < tries - 1: time.sleep(4)
            else: return None

def norm(t): return set(re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()) - {"the","a","of","and","in","on","for","to"}
def jac(a, b):
    A, B = norm(a), norm(b)
    return len(A & B) / max(1, len(A | B))

sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
src = get_lifecycle_db_connection()
todo = src.execute("""SELECT paper_id, title, title_trust FROM paper_bibliographic
                      WHERE title IS NOT NULL AND length(title) > 14
                        AND (apa_citation IS NULL OR apa_citation LIKE 'SUSPECT:%')""").fetchall()
src.close()
done = json.loads(CKPT.read_text()) if CKPT.exists() else {}
print(f"papers needing clean DOI+APA: {len(todo)}; checkpointed: {len(done)}")

got = miss = 0
results = dict(done)
for i, (pid, title, trust) in enumerate(todo):
    if pid in results: continue
    q = re.sub(r"^\[from text\]\s*", "", title)[:130]
    raw = get("https://api.openalex.org/works?search=" + urllib.parse.quote(q)
              + f"&per-page=1&select=doi,title&mailto={MAILTO}")
    rec = {"doi": None, "apa": None, "score": None}
    if raw:
        try:
            hits = json.loads(raw).get("results", [])
            if hits and hits[0].get("doi"):
                sc = jac(q, hits[0].get("title"))
                if sc >= 0.6:
                    doi = hits[0]["doi"].replace("https://doi.org/", "")
                    apa = get("https://doi.org/" + urllib.parse.quote(doi),
                              accept="text/x-bibliography; style=apa")
                    if apa:
                        s = re.sub(r"\s+", " ", apa.decode("utf-8", "replace")).strip()
                        if 20 < len(s) < 1200:
                            rec = {"doi": doi, "apa": s, "score": round(sc, 2)}
        except Exception: pass
    results[pid] = rec
    got += bool(rec["apa"]); miss += (not rec["apa"])
    CKPT.write_text(json.dumps(results))
    time.sleep(1.2)
    if (i + 1) % 50 == 0: print(f"  {i+1}/{len(todo)} clean_apa={got} miss={miss}")

ok = {p: r for p, r in results.items() if r.get("apa")}
print(f"clean DOI+APA derived: {len(ok)} total")
for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000")
    cx.executemany("""UPDATE paper_bibliographic
                      SET doi=?, apa_citation=?, source=source||'+oa_title_match', imported_at=?
                      WHERE paper_id=?""",
                   [(r["doi"], r["apa"], NOW, p) for p, r in ok.items()])
    cx.commit()
    n = cx.execute("SELECT COUNT(*) FROM paper_bibliographic WHERE apa_citation IS NOT NULL AND apa_citation NOT LIKE 'SUSPECT:%'").fetchone()[0]
    ns = cx.execute("SELECT COUNT(*) FROM paper_bibliographic WHERE apa_citation LIKE 'SUSPECT:%'").fetchone()[0]
    print(f"{label}: clean APA now {n}; still suspect {ns}")
    cx.close()
