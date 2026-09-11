#!/usr/bin/env python3
"""apa_from_printed_dois.py — highest-trust rung of the APA ladder (David's
insight): DOIs printed in the paper's OWN front matter need no matching at all.
Fetch APA via doi.org for each harvested printed DOI, write into the shared
checkpoint (so the Crossref matcher skips them) and into both canonical DBs
with source 'printed_doi'. One-example-first; verify a 5-row sample per the
bulk-verification rule (CASE 2026-09-10): the APA's title tokens must appear
in the paper's own text."""
import json, re, glob, sqlite3, sys, time, urllib.request, urllib.parse, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
CKPT = AF / "data/topic_comparison/full1760_2026-09-09/doi_apa_checkpoint.json"
PRINTED = Path("/private/tmp/claude-501/-Users-davidusa-REPOS-New-VR-Platform/b07ed661-0ea6-4535-8b9d-cd0200658a81/scratchpad/printed_dois.json")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def fetch_apa(doi, tries=3):
    delay = 8
    for a in range(tries):
        try:
            req = urllib.request.Request("https://doi.org/" + urllib.parse.quote(doi),
                headers={"Accept": "text/x-bibliography; style=apa",
                         "User-Agent": "AE-corpus (mailto:dkirsh@gmail.com)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                s = re.sub(r"\s+", " ", r.read().decode("utf-8", "replace")).strip()
                return s if 20 < len(s) < 1200 else None
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if a < tries - 1: time.sleep(delay); delay *= 2
            else: return None
        except Exception:
            if a < tries - 1: time.sleep(3)
            else: return None

printed = json.load(open(PRINTED))
done = json.loads(CKPT.read_text()) if CKPT.exists() else {}
got = miss = 0
for i, (pid, doi) in enumerate(sorted(printed.items())):
    if done.get(pid, {}).get("apa"): continue
    apa = fetch_apa(doi)
    done[pid] = {"doi": doi, "apa": apa, "score": 1.0, "basis": "printed_doi"}
    got += bool(apa); miss += (not apa)
    CKPT.write_text(json.dumps(done))
    time.sleep(0.8)
    if (i + 1) % 40 == 0: print(f"  {i+1}/{len(printed)} apa={got} miss={miss}")
print(f"printed-DOI APAs fetched: {got}; unresolvable DOIs: {miss}")

# MANDATORY sample verification: APA title tokens must appear in the paper's own text
def text_of(pid):
    t = ""
    for sub in ("docling", "ocr_canonical"):
        for f in glob.glob(f"{AE}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: t += open(f, errors="replace").read()[:20000]
                except OSError: pass
        if len(t) > 3000: break
    return t.lower()
import random
oks = [(p, r) for p, r in done.items() if r.get("basis") == "printed_doi" and r.get("apa")]
sample = random.sample(oks, min(6, len(oks)))
passed = 0
for pid, r in sample:
    body = text_of(pid)
    words = [w for w in re.findall(r"[a-z]{5,}", r["apa"].lower())][:12]
    hit = sum(1 for w in words if w in body)
    ok = hit >= max(3, len(words) // 3)
    passed += ok
    print(f"  sample {pid}: {hit}/{len(words)} APA tokens found in paper text -> {'OK' if ok else 'FAIL'}")
print(f"SAMPLE VERIFICATION: {passed}/{len(sample)} passed")
if passed < max(1, len(sample) - 1):
    sys.exit("SAMPLE FAILED — not writing to DBs; investigate before shipping.")

sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
rows = [(r["doi"], r["apa"], NOW, p) for p, r in oks]
for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000")
    cx.executemany("UPDATE paper_bibliographic SET doi=?, apa_citation=?, source=source||'+printed_doi', imported_at=? WHERE paper_id=?", rows)
    cx.commit()
    n = cx.execute("SELECT COUNT(*) FROM paper_bibliographic WHERE apa_citation IS NOT NULL AND apa_citation NOT LIKE 'SUSPECT:%'").fetchone()[0]
    print(f"{label}: clean APA total now {n}")
    cx.close()
