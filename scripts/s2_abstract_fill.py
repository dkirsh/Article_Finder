#!/usr/bin/env python3
"""s2_abstract_fill.py — fill missing abstracts from Semantic Scholar (David
2026-09-11: "start the 926 with semantic scholar now... an abstract with a
wrong word is better than no abstract").

Phase A: S2 BATCH endpoint (up to 500 ids/request) for papers holding a DOI.
Phase B: S2 title search, one by one, for the DOI-less (rate-gentle, checkpointed).
Phase C: REPAIR-NOT-REJECT — for papers S2 cannot supply, extract the abstract
region from docling/OCR and mechanically repair it: collapse letter-gap words,
rejoin hyphenated line breaks, strip markup/JSON debris. Store best-available
with quality labels: publisher/s2 > repaired_mechanical > dirty_flagged only
when repair still fails. Sample verification before DB writes (bulk rule).
Optional S2 key via env S2_API_KEY (raises rate limits)."""
import json, re, glob, sqlite3, sys, time, os, random, urllib.request, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
CKPT = AF / "data/topic_comparison/full1760_2026-09-09/s2_abstract_checkpoint.json"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
KEY = os.environ.get("S2_API_KEY")

def call(url, data=None, tries=4):
    delay = 12
    for a in range(tries):
        try:
            h = {"User-Agent": "AE-corpus (mailto:dkirsh@gmail.com)"}
            if KEY: h["x-api-key"] = KEY
            if data is not None: h["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=h)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if a < tries - 1: time.sleep(delay); delay *= 2
            else: return None
        except Exception:
            if a < tries - 1: time.sleep(5)
            else: return None

GAPPY = re.compile(r"(?:\b\w\s){4,}")
def repair(t):
    if not t: return None
    t = re.sub(r"\"cnt\":\s*\[\[[^\]]*\]\]?", " ", t)
    t = re.sub(r"\\\(|\\\)|\\begin\{[^}]*\}|\\end\{[^}]*\}", " ", t)
    t = re.sub(r"</?[a-z][^>]*>", " ", t)
    t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)                      # environ- ment
    def collapse(m):                                              # l i k e t h i s
        return m.group(0).replace(" ", "") + " "
    t = GAPPY.sub(collapse, t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) > 80 else None
def dirt(t):
    if not t: return 99
    s = 3 * len(GAPPY.findall(t)) + 2 * len(re.findall(r"\{|\}|\\\(|\"cnt\":", t))
    if sum(c.isalpha() for c in t) / max(1, len(t)) < 0.55: s += 5
    return s

def norm(t): return set(re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()) - {"the","a","of","and","in","on"}
def jac(a, b):
    A, B = norm(a), norm(b)
    return len(A & B) / max(1, len(A | B))

sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
src = get_lifecycle_db_connection()
need = src.execute("SELECT paper_id, doi, title FROM paper_bibliographic "
                   "WHERE abstract IS NULL OR abstract_quality='dirty_flagged'").fetchall()
src.close()
done = json.loads(CKPT.read_text()) if CKPT.exists() else {}
print(f"papers needing abstracts: {len(need)}; checkpointed: {len(done)}")

results = dict(done)
# Phase A: batch by DOI
withdoi = [(p, d) for p, d, _ in need if d and p not in results]
for i in range(0, len(withdoi), 400):
    chunk = withdoi[i:i+400]
    resp = call("https://api.semanticscholar.org/graph/v1/paper/batch?fields=abstract,title",
                data={"ids": [f"DOI:{d}" for _, d in chunk]})
    if resp:
        for (pid, _), item in zip(chunk, resp):
            ab = (item or {}).get("abstract")
            if ab and len(ab) > 80:
                results[pid] = {"abstract": repair(ab) or ab, "source": "s2_doi"}
    CKPT.write_text(json.dumps(results))
    print(f"  batch {i//400+1}: cumulative s2 abstracts {sum(1 for r in results.values() if r.get('abstract'))}")
    time.sleep(3)

# Phase B: title search for DOI-less
nodoi = [(p, t) for p, d, t in need if not d and t and len(t) > 14 and p not in results]
print(f"phase B (title search): {len(nodoi)}")
for i, (pid, title) in enumerate(nodoi):
    q = re.sub(r"^\[from text\]\s*", "", title)[:120]
    resp = call("https://api.semanticscholar.org/graph/v1/paper/search?limit=1&fields=abstract,title&query="
                + urllib.parse.quote(q))
    got = None
    if resp and resp.get("data"):
        it = resp["data"][0]
        if it.get("abstract") and jac(q, it.get("title")) >= 0.6:
            got = it["abstract"]
    if got: results[pid] = {"abstract": repair(got) or got, "source": "s2_title"}
    CKPT.write_text(json.dumps(results))
    time.sleep(3.2 if not KEY else 1.0)
    if (i + 1) % 40 == 0: print(f"  B {i+1}/{len(nodoi)} total={sum(1 for r in results.values() if r.get('abstract'))}")

# Phase C: docling extraction + mechanical repair for the rest
import urllib.parse
rest = [p for p, d, t in need if p not in results]
print(f"phase C (docling repair): {len(rest)}")
ABS = re.compile(r"(?:^|\n)#*\s*abstract\s*[:.\n]+(.{150,1800}?)(?:\n#|\nkeywords|\n1[\s.]|introduction)", re.I | re.S)
for pid in rest:
    txt = ""
    for sub in ("docling", "ocr_canonical"):
        for f in glob.glob(f"{AE}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: txt += open(f, errors="replace").read()[:12000]
                except OSError: pass
        if len(txt) > 2000: break
    m = ABS.search(txt)
    if m:
        fixed = repair(m.group(1))
        if fixed and dirt(fixed) <= 4:
            results[pid] = {"abstract": fixed, "source": "repaired_mechanical"}
CKPT.write_text(json.dumps(results))
ok = {p: r for p, r in results.items() if r.get("abstract")}
by = {}
for r in ok.values(): by[r["source"]] = by.get(r["source"], 0) + 1
print(f"abstracts obtained: {len(ok)}; by source: {by}")

# sample verification
def text_of(pid):
    t = ""
    for sub in ("docling", "ocr_canonical"):
        for f in glob.glob(f"{AE}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: t += open(f, errors="replace").read()[:30000]
                except OSError: pass
        if len(t) > 3000: break
    return t.lower()
sample = random.sample(list(ok.items()), min(6, len(ok)))
passed = 0
for pid, r in sample:
    body = text_of(pid)
    words = set(re.findall(r"[a-z]{6,}", r["abstract"].lower()))
    words = list(words)[:15]
    hit = sum(1 for w in words if w in body)
    okk = hit >= max(3, len(words) // 3)
    passed += okk
    print(f"  sample {pid} [{r['source']}]: {hit}/{len(words)} -> {'OK' if okk else 'FAIL'}")
print(f"SAMPLE VERIFICATION: {passed}/{len(sample)}")
if sample and passed < len(sample) - 1:
    sys.exit("SAMPLE FAILED — not writing.")
for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000")
    cx.executemany("UPDATE paper_bibliographic SET abstract=?, abstract_quality=?, imported_at=? WHERE paper_id=?",
                   [(r["abstract"], r["source"], NOW, p) for p, r in ok.items()])
    cx.commit()
    q = dict(cx.execute("SELECT abstract_quality, COUNT(*) FROM paper_bibliographic GROUP BY abstract_quality"))
    print(f"{label}: {q}")
    cx.close()
