#!/usr/bin/env python3
"""pilot_typer_sample50.py — blind-validation round: stratified 50-paper sample.

Samples 50 accepted gold papers (excluding the gold-20), stratified by the
registry's existing article_type (used ONLY for stratification — those labels are
under audit), runs the same mechanical layers as pilot_typer_v0, and emits:
  data/topic_comparison/blind50_2026-09-09/results.json      (full evidence)
  data/topic_comparison/blind50_2026-09-09/tasks.json        (for the HITL viewer:
        paper ids, titles, text file names — NO machine verdicts, NO receipts)
  data/topic_comparison/blind50_2026-09-09/papers/<id>.txt   (full text for scroll)
Compact packets print to stdout for the machine judge; the judge's verdicts are
kept SEPARATE from the human-facing tasks so the human round stays blind.
Seed fixed for reproducibility. Read-only against every corpus surface.
"""
import json, re, sqlite3, glob, random, time, urllib.request, urllib.parse
from pathlib import Path

AE = Path("/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery")
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
OUT = AF / "data/topic_comparison/blind50_2026-09-09"
(OUT / "papers").mkdir(parents=True, exist_ok=True)
SEED = 20260909
GOLD20 = {"PDF-0040","PDF-0061","PDF-0062","PDF-0071","PDF-0108","PDF-0154","PDF-0176",
          "PDF-0196","PDF-0267","PDF-0396","PDF-0404","PDF-0446","PDF-0461","PDF-0466",
          "PDF-0674","PDF-0802","PDF-0839","PDF-1106","PDF-1303","PDF-1431"}

PAT = {
    "methods_header":  re.compile(r"^\s*#*\s*(\d+\.?\s*)?(materials?\s+and\s+)?methods?\b|^\s*#*\s*(participants|procedure|apparatus|experimental design)\b", re.I | re.M),
    "stats":           re.compile(r"\bp\s*[<=>]\s*\.?\d|\bF\s*\(\s*\d+\s*,|\bt\s*\(\s*\d+\s*\)|\bχ2|\bchi-square|\bANOVA\b|\bSD\s*=|\b95%\s*CI|\br\s*=\s*[-.\d]|\bβ\s*=", re.I),
    "participants":    re.compile(r"\b[nN]\s*=\s*\d+|\b\d+\s+(participants|subjects|respondents|students|adults|observers)\b", re.I),
    "prisma":          re.compile(r"\bPRISMA\b|systematic(ally)?\s+search|databases?\s+(were\s+)?searched|inclusion\s+criteria", re.I),
    "meta":            re.compile(r"\bmeta-?anal|pooled\s+(effect|estimate)|random-effects\s+model", re.I),
    "qual":            re.compile(r"\b(interviews?|focus groups?|thematic analysis|grounded theory|ethnograph|content analysis)\b", re.I),
    "review_lang":     re.compile(r"\b(this|the present)\s+(narrative\s+)?review\b|we\s+review\b|literature\s+review\b", re.I),
}

def span(pat, text, w=70):
    m = pat.search(text)
    if not m: return None
    s = max(0, m.start() - 15)
    return re.sub(r"\s+", " ", text[s:m.end() + w - 15]).strip()[:w]

def load_text(pid):
    txt = ""
    for sub in ("ocr_canonical", "docling", "mathpix"):
        for f in glob.glob(str(AE / f"data/papers/{pid}/{sub}/*")):
            if f.lower().endswith((".md", ".txt", ".mmd")):
                try: txt += open(f, errors="replace").read() + "\n"
                except OSError: pass
        if len(txt) > 3000: break
    if len(txt) < 3000:  # json layers as fallback
        for f in glob.glob(str(AE / f"data/papers/{pid}/ocr_canonical/*.json")):
            try: txt += open(f, errors="replace").read()
            except OSError: pass
    return txt

def abstract_of(pid):
    p = AE / f"data/papers/{pid}/sc_summary/gold.json"
    if p.exists():
        try: return (json.load(open(p)).get("abstract") or "")[:400]
        except Exception: return ""
    return ""

def s2_types(doi):
    if not doi: return None
    url = ("https://api.semanticscholar.org/graph/v1/paper/DOI:"
           + urllib.parse.quote(str(doi)) + "?fields=publicationTypes")
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return json.load(r).get("publicationTypes")
    except Exception as e:
        return f"unavailable ({type(e).__name__})"

# --- sample ---
reg = sqlite3.connect(f"file:{AE/'data/verification_runs/v7_gold_extraction_registry.db'}?mode=ro", uri=True)
rows = [(pid, title, at, None) for pid, title, at in reg.execute(
    "SELECT paper_id, title, article_type FROM gold_papers "
    "WHERE accepted_for_rebuild=1").fetchall()]  # registry carries no DOI column; S2 layer idles this batch
pool = [r for r in rows if r[0] not in GOLD20]
by_type = {}
for r in pool: by_type.setdefault(r[2] or "untyped", []).append(r)
rng = random.Random(SEED)
total = len(pool)
sample, alloc = [], []
for t, papers in sorted(by_type.items()):
    k = max(1, round(50 * len(papers) / total))
    alloc.append((t, len(papers), min(k, len(papers))))
    sample += rng.sample(papers, min(k, len(papers)))
rng.shuffle(sample)
sample = sample[:50]
print("strata (type, pool, drawn):", alloc)
print(f"sampled {len(sample)} papers from pool of {total}")

results, tasks = [], []
for pid, title, regtype, doi in sample:
    text = load_text(pid)
    (OUT / "papers" / f"{pid}.txt").write_text(text)
    sig = {k: bool(p.search(text)) for k, p in PAT.items()}
    receipts = {k: span(p, text) for k, p in PAT.items() if sig[k]}
    results.append({"paper_id": pid, "title": title, "registry_type_stratum": regtype,
                    "doi": doi, "text_chars": len(text), "signals": sig,
                    "receipts": receipts, "abstract": abstract_of(pid),
                    "s2_publicationTypes": s2_types(doi)})
    tasks.append({"paper_id": pid, "title": title, "text_file": f"papers/{pid}.txt"})
    if doi: time.sleep(1.05)

(OUT / "results.json").write_text(json.dumps(results, indent=2))
(OUT / "tasks.json").write_text(json.dumps(
    {"schema": "hitl_tasks.v1", "mode": "blind", "created": "2026-09-09",
     "note": "Blind validation round: no machine verdicts or receipts in this file by design.",
     "tasks": tasks}, indent=2))

for r in results:
    print(f"\n=== {r['paper_id']} stratum={r['registry_type_stratum']} chars={r['text_chars']}")
    print(f"  title: {r['title'][:95]}")
    print(f"  s2: {r['s2_publicationTypes']}  " +
          " ".join(f"{k}={int(v)}" for k, v in r["signals"].items()))
    for k in ("stats", "participants", "prisma", "meta", "review_lang", "qual"):
        if r["receipts"].get(k): print(f"  receipt[{k}]: {r['receipts'][k]}")
    if r["abstract"]: print(f"  abstract: {r['abstract'][:240]}")
print(f"\nwrote {OUT}/results.json, tasks.json, and {len(results)} text files")
