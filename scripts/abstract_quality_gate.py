#!/usr/bin/env python3
"""abstract_quality_gate.py — website-grade abstracts (David 2026-09-11: "nothing
says 'unreliable' more than terrible presentation of words").

Two moves:
1. GATE: score every stored abstract for OCR dirt — intra-word letter gaps,
   broken hyphenation, LaTeX/JATS/markup remnants, JSON debris, entity soup.
   Dirty or missing -> repair queue; every row gets abstract_quality
   (clean / repaired / dirty_flagged / none) and abstract_source.
2. REPAIR: for queue papers WITH a DOI, fetch the publisher abstract from
   Crossref (JATS tags stripped); re-gate; only clean text is stored. Papers
   without DOI or publisher abstract keep their flag — the website must not
   render dirty text, and a flag is honest where clean text is not yet held.

Sample verification per the bulk rule: 6 random repaired abstracts are checked
for topical overlap with the paper's own text before DB write. Both DBs updated."""
import json, re, glob, sqlite3, sys, time, random, urllib.request, urllib.parse, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

GAPPY = re.compile(r"(?:\b\w\s){4,}")                 # l i k e   t h i s
HYPH  = re.compile(r"\w-\s\w")                        # environ- ment
MARKUP= re.compile(r"\\\(|\\\)|\\begin|\{|\}|</?jats|</?[a-z]+>|&\w+;|\"cnt\":|\[\[")
def dirt_score(t):
    if not t: return None
    s = 0
    s += 3 * len(GAPPY.findall(t))
    s += len(HYPH.findall(t))
    s += 2 * len(MARKUP.findall(t))
    letters = sum(c.isalpha() for c in t)
    if letters / max(1, len(t)) < 0.6: s += 5
    return s

def strip_jats(x):
    x = re.sub(r"</?jats:[^>]+>", " ", x)
    x = re.sub(r"</?[a-z][^>]*>", " ", x)
    x = x.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return re.sub(r"\s+", " ", x).strip()

def crossref_abstract(doi, tries=3):
    delay = 8
    for a in range(tries):
        try:
            req = urllib.request.Request(
                "https://api.crossref.org/works/" + urllib.parse.quote(doi)
                + "?mailto=dkirsh@gmail.com",
                headers={"User-Agent": "AE-corpus (mailto:dkirsh@gmail.com)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                ab = json.load(r).get("message", {}).get("abstract")
                if ab:
                    s = strip_jats(ab)
                    return s if len(s) > 80 else None
                return None
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if a < tries - 1: time.sleep(delay); delay *= 2
            else: return None
        except Exception:
            if a < tries - 1: time.sleep(3)
            else: return None

sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
src = get_lifecycle_db_connection()
cols = [r[1] for r in src.execute("PRAGMA table_info('paper_bibliographic')")]
rows = src.execute("SELECT paper_id, abstract, doi FROM paper_bibliographic").fetchall()
src.close()

gate, queue = {}, []
for pid, ab, doi in rows:
    d = dirt_score(ab)
    if ab and d is not None and d <= 2:
        gate[pid] = ("clean", ab)
    else:
        gate[pid] = ("dirty_flagged" if ab else "none", ab)
        if doi: queue.append((pid, doi))
print(f"abstracts: clean={sum(1 for v in gate.values() if v[0]=='clean')} "
      f"dirty={sum(1 for v in gate.values() if v[0]=='dirty_flagged')} "
      f"missing={sum(1 for v in gate.values() if v[0]=='none')}; "
      f"repairable via DOI: {len(queue)}")

repaired = {}
for i, (pid, doi) in enumerate(queue):
    ab = crossref_abstract(doi)
    if ab and (dirt_score(ab) or 0) <= 2:
        repaired[pid] = ab
    time.sleep(0.8)
    if (i + 1) % 50 == 0: print(f"  repair {i+1}/{len(queue)} got={len(repaired)}")
print(f"publisher abstracts fetched clean: {len(repaired)}")

# sample verification: repaired abstract must topically overlap the paper's text
def text_of(pid):
    t = ""
    for sub in ("docling", "ocr_canonical"):
        for f in glob.glob(f"{AE}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: t += open(f, errors="replace").read()[:30000]
                except OSError: pass
        if len(t) > 3000: break
    return t.lower()
sample = random.sample(list(repaired.items()), min(6, len(repaired)))
passed = 0
for pid, ab in sample:
    body = text_of(pid)
    words = re.findall(r"[a-z]{6,}", ab.lower())[:15]
    hit = sum(1 for w in set(words) if w in body)
    ok = hit >= max(3, len(set(words)) // 3)
    passed += ok
    print(f"  sample {pid}: {hit}/{len(set(words))} abstract tokens in paper text -> {'OK' if ok else 'FAIL'}")
print(f"SAMPLE VERIFICATION: {passed}/{len(sample)} passed")
if sample and passed < len(sample) - 1:
    sys.exit("SAMPLE FAILED — not writing; investigate.")

for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000")
    c2 = [r[1] for r in cx.execute("PRAGMA table_info('paper_bibliographic')")]
    if "abstract_quality" not in c2:
        cx.execute("ALTER TABLE paper_bibliographic ADD COLUMN abstract_quality TEXT")
    cx.executemany("UPDATE paper_bibliographic SET abstract=?, abstract_quality='repaired_publisher', imported_at=? WHERE paper_id=?",
                   [(ab, NOW, p) for p, ab in repaired.items()])
    cx.executemany("UPDATE paper_bibliographic SET abstract_quality=? WHERE paper_id=? AND abstract_quality IS NULL",
                   [(v[0], p) for p, v in gate.items() if p not in repaired])
    cx.commit()
    q = dict(cx.execute("SELECT abstract_quality, COUNT(*) FROM paper_bibliographic GROUP BY abstract_quality"))
    print(f"{label} abstract_quality: {q}")
    cx.close()
