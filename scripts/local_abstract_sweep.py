#!/usr/bin/env python3
"""local_abstract_sweep.py — pure-local abstract recovery for every paper still
lacking one: extract the abstract region from docling/OCR, mechanically REPAIR
it (David: "an abstract with a wrong word is better than no abstract"), keep it
when the dirt score clears, label repaired_mechanical. Merges the S2 checkpoint
abstracts too (184 held there but not yet in DBs). Sample-verified, both DBs."""
import json, re, glob, sqlite3, sys, random, datetime
from pathlib import Path

AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
CKPT = AF / "data/topic_comparison/full1760_2026-09-09/s2_abstract_checkpoint.json"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

GAPPY = re.compile(r"(?:\b\w\s){4,}")
def repair(t):
    if not t: return None
    t = re.sub(r"\"cnt\":\s*\[\[[^\]]*\]\]?", " ", t)
    t = re.sub(r"\\\(|\\\)|\\begin\{[^}]*\}|\\end\{[^}]*\}", " ", t)
    t = re.sub(r"</?[a-z][^>]*>", " ", t)
    t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)
    t = GAPPY.sub(lambda m: m.group(0).replace(" ", "") + " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) > 80 else None
def dirt(t):
    if not t: return 99
    s = 3 * len(GAPPY.findall(t)) + 2 * len(re.findall(r"\{|\}|\\\(|\"cnt\":", t))
    if sum(c.isalpha() for c in t) / max(1, len(t)) < 0.55: s += 5
    return s

ABS = re.compile(r"(?:^|\n)#*\s*a\s*b\s*s\s*t\s*r\s*a\s*c\s*t\s*[:.\n]+(.{150,2000}?)(?:\n#|\nkey\s*words|\n1[\s.]|introduction|©)", re.I | re.S)
ABS2 = re.compile(r"begin\{abstract\}(.{150,2000}?)end\{abstract\}", re.I | re.S)

sys.path.insert(0, AE)
from src.services.db_locator import get_lifecycle_db_connection  # noqa: E402
src = get_lifecycle_db_connection()
need = [r[0] for r in src.execute("SELECT paper_id FROM paper_bibliographic "
        "WHERE abstract IS NULL OR abstract_quality IN ('dirty_flagged','none')")]
src.close()
ck = json.loads(CKPT.read_text()) if CKPT.exists() else {}
results = {p: r for p, r in ck.items() if r.get("abstract")}  # S2 wins where held
got_local = 0
for pid in need:
    if pid in results: continue
    txt = ""
    for sub in ("docling", "ocr_canonical", "mathpix"):
        for f in glob.glob(f"{AE}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: txt += open(f, errors="replace").read()[:20000]
                except OSError: pass
        if len(txt) > 2000: break
    m = ABS.search(txt) or ABS2.search(txt)
    if m:
        fixed = repair(m.group(1))
        if fixed and dirt(fixed) <= 4:
            results[pid] = {"abstract": fixed, "source": "repaired_mechanical"}
            got_local += 1
print(f"needed: {len(need)}; from S2 checkpoint: {sum(1 for r in results.values() if r['source'].startswith('s2'))}; "
      f"local docling repairs: {got_local}; total to write: {len(results)}")

def text_of(pid):
    t = ""
    for sub in ("docling", "ocr_canonical"):
        for f in glob.glob(f"{AE}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: t += open(f, errors="replace").read()[:30000]
                except OSError: pass
        if len(t) > 3000: break
    return t.lower()
sample = random.sample(list(results.items()), min(6, len(results)))
passed = 0
for pid, r in sample:
    body = text_of(pid)
    words = list(set(re.findall(r"[a-z]{6,}", r["abstract"].lower())))[:15]
    hit = sum(1 for w in words if w in body)
    ok = hit >= max(3, len(words) // 3)
    passed += ok
    print(f"  sample {pid} [{r['source']}]: {hit}/{len(words)} -> {'OK' if ok else 'FAIL'}")
print(f"SAMPLE VERIFICATION: {passed}/{len(sample)}")
if sample and passed < len(sample) - 1:
    sys.exit("SAMPLE FAILED — not writing.")
for label, cx in (("AE", get_lifecycle_db_connection()),
                  ("AF", sqlite3.connect(str(AF / "data/article_finder.db")))):
    cx.execute("PRAGMA busy_timeout=15000")
    cx.executemany("UPDATE paper_bibliographic SET abstract=?, abstract_quality=?, imported_at=? "
                   "WHERE paper_id=? AND (abstract IS NULL OR abstract_quality IN ('dirty_flagged','none'))",
                   [(r["abstract"], r["source"], NOW, p) for p, r in results.items()])
    cx.commit()
    q = dict(cx.execute("SELECT COALESCE(abstract_quality,'(unset)'), COUNT(*) FROM paper_bibliographic GROUP BY 1"))
    print(f"{label}: {q}")
    cx.close()
