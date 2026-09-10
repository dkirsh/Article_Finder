#!/usr/bin/env python3
"""pilot_typer_v0.py — pilot of the rebuilt article typer, run on the gold-20.

Design (David + Fable, 2026-09-09; see docs/GOLD20_ADJUDICATION_2026-09-09.md):
two axes (form / method), evidence layers with receipts, precedence combiner,
LLM adjudication only for the residue. This pilot computes the MECHANICAL layers
and emits per-paper evidence packets; the LLM layer is applied by the supervising
agent reading the packets, so its verdicts carry quoted spans and are auditable.

Layers here:
  1a structural detectors on AE full text (headers, stats, participants, PRISMA)
  1b AE extraction artifacts (sc_summary/gold.json: reported statistics, methods)
  2  Semantic Scholar publicationTypes by DOI (fail-soft, 20 requests max)
     + the OpenAlex block already stored in the comparison harness

Output: data/topic_comparison/pilot_typer_v0_2026-09-09/results.json (full)
        and a compact packet per paper on stdout for the judge.
Read-only against every corpus surface; writes only its own output dir.
"""
import json, re, sqlite3, glob, time, urllib.request, urllib.parse
from pathlib import Path

AE = Path("/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery")
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
CMP = AF / "data/topic_comparison/gold_sample_20_2026-08-29_r2/comparison.db"
OUT = AF / "data/topic_comparison/pilot_typer_v0_2026-09-09"
OUT.mkdir(parents=True, exist_ok=True)

# David's rulings 2026-09-09
REMOVED = {"PDF-0061", "PDF-0176", "PDF-0267", "PDF-0396", "PDF-1303", "PDF-1431"}
RETYPED = {"PDF-0404": "empirical_research", "PDF-0446": "empirical_research"}

# ---- signal patterns (method axis) ----
PAT = {
    "methods_header":  re.compile(r"^\s*#*\s*(\d+\.?\s*)?(materials?\s+and\s+)?methods?\b|^\s*#*\s*(participants|procedure|apparatus|experimental design)\b", re.I | re.M),
    "results_header":  re.compile(r"^\s*#*\s*(\d+\.?\s*)?results\b", re.I | re.M),
    "stats":           re.compile(r"\bp\s*[<=>]\s*\.?\d|\bF\s*\(\s*\d+\s*,|\bt\s*\(\s*\d+\s*\)|\bχ2|\bchi-square|\bANOVA\b|\bSD\s*=|\b95%\s*CI|\br\s*=\s*[-.\d]|\bβ\s*=", re.I),
    "participants":    re.compile(r"\b[nN]\s*=\s*\d+|\b\d+\s+(participants|subjects|respondents|students|adults|observers)\b", re.I),
    "conditions":      re.compile(r"\b(conditions?|trials?|sessions?|counterbalanc|within-subjects?|between-subjects?|randomi[sz]ed|control group)\b", re.I),
    "prisma":          re.compile(r"\bPRISMA\b|systematic(ally)?\s+search|databases?\s+(were\s+)?searched|inclusion\s+criteria", re.I),
    "meta":            re.compile(r"\bmeta-?anal|pooled\s+(effect|estimate)|random-effects\s+model", re.I),
    "qual":            re.compile(r"\b(interviews?|focus groups?|thematic analysis|grounded theory|ethnograph|content analysis)\b", re.I),
    "review_lang":     re.compile(r"\b(this|the present)\s+(narrative\s+)?review\b|we\s+review\b|literature\s+review\b", re.I),
}
FORM_PAT = {
    "commentary": re.compile(r"\b(response to|reply to|comment(ary)? on)\b", re.I),
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
            if f.lower().endswith((".md", ".txt", ".json", ".mmd")):
                try: txt += open(f, errors="replace").read()
                except OSError: pass
        if len(txt) > 5000: break
    return txt

def artifact_signals(pid):
    p = AE / f"data/papers/{pid}/sc_summary/gold.json"
    out = {"gold_json_present": p.exists()}
    if p.exists():
        try:
            g = json.load(open(p))
            blob = json.dumps(g)
            out["reported_statistics"] = bool(re.search(r"reported.?statistics", blob, re.I)) and bool(PAT["stats"].search(blob))
            out["abstract"] = (g.get("abstract") or "")[:400]
            out["has_findings"] = any("finding" in k.lower() for k in g)
        except Exception as e:
            out["error"] = str(e)[:80]
    return out

def s2_types(doi):
    if not doi: return None
    url = ("https://api.semanticscholar.org/graph/v1/paper/DOI:"
           + urllib.parse.quote(doi) + "?fields=publicationTypes")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r).get("publicationTypes")
    except Exception as e:
        return f"unavailable ({type(e).__name__})"

def mech_method(sig):
    """Precedence combiner over the mechanical signals. Returns (label, basis)."""
    if sig["meta"]:                          return "meta_analysis", "meta-analysis language"
    if sig["prisma"]:                        return "systematic_review", "PRISMA/search-strategy"
    empirical = (sig["participants"] or sig["methods_header"]) and sig["stats"]
    if empirical and sig["qual"] and not sig["stats"]: return "empirical_qual", "qual methods, no stats"
    if empirical:                            return "empirical_quant", "participants/methods + statistics"
    if sig["qual"] and sig["participants"]:  return "empirical_qual", "qual methods + participants"
    if sig["review_lang"] and not sig["methods_header"]: return "review_narrative", "review language, no methods"
    return "OPEN", "mechanical layers abstain -> LLM judge"

con = sqlite3.connect(f"file:{CMP}?mode=ro", uri=True)
rows = con.execute("SELECT paper_id, title, gold_article_type, stored_doi, result_json "
                   "FROM paper ORDER BY paper_id").fetchall()
results = []
for pid, title, gold, doi, rj in rows:
    text = load_text(pid)
    sig = {k: bool(p.search(text)) for k, p in PAT.items()}
    receipts = {k: span(p, text) for k, p in PAT.items() if sig[k]}
    art = artifact_signals(pid)
    oa = (json.loads(rj).get("openalex") or {})
    oa_slim = {k: oa[k] for k in ("work_type", "type", "topics", "keywords") if k in oa}
    label, basis = mech_method(sig)
    corrected = RETYPED.get(pid, gold)
    rec = {
        "paper_id": pid, "title": title, "removed_by_david": pid in REMOVED,
        "gold_original": gold, "gold_corrected": corrected,
        "text_chars": len(text), "signals": sig, "receipts": receipts,
        "artifacts": art, "s2_publicationTypes": s2_types(doi),
        "openalex_slim": oa_slim, "form_commentary_title": bool(FORM_PAT["commentary"].search(title)),
        "mechanical_method": label, "mechanical_basis": basis,
    }
    results.append(rec)
    time.sleep(1.1)  # S2 unauthenticated rate courtesy

(OUT / "results.json").write_text(json.dumps(results, indent=2))

# compact packets for the LLM judge
for r in results:
    tag = "REMOVED" if r["removed_by_david"] else "kept"
    print(f"\n=== {r['paper_id']} [{tag}] gold(corrected)={r['gold_corrected']} "
          f"mech={r['mechanical_method']} ({r['mechanical_basis']})")
    print(f"  title: {r['title'][:95]}")
    print(f"  s2: {r['s2_publicationTypes']}  chars={r['text_chars']}  "
          f"stats={r['signals']['stats']} parts={r['signals']['participants']} "
          f"prisma={r['signals']['prisma']} qual={r['signals']['qual']} rev={r['signals']['review_lang']}")
    for k in ("stats", "participants", "prisma", "review_lang", "qual"):
        if r["receipts"].get(k): print(f"  receipt[{k}]: {r['receipts'][k]}")
    ab = (r["artifacts"].get("abstract") or "")[:260]
    if ab: print(f"  abstract: {ab}")
print(f"\nwrote {OUT/'results.json'} ({len(results)} papers)")
