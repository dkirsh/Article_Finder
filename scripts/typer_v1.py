#!/usr/bin/env python3
"""typer_v1.py — finalized article typer + topic/field identifier, corpus-scale.

David 2026-09-09: finalize the pilot, run on all 1,760; pure neuroscience to its
own bucket for hand review; build a topic identifier, panel-reviewed
(docs/PANEL_REVIEW_TOPIC_IDENTIFIER_2026-09-09.md), run both.

v1 mechanizes the pilot's judge rules:
  - all signals computed on the PRE-REFERENCES body (citation-contamination cut)
  - title+abstract (TA) evidence outranks body evidence; body outranks references
  - PRISMA needs real search-strategy language ("inclusion criteria" alone was a
    false positive on participant screening — pilot finding, PDF-0481)
  - own-data dominance: participants+stats in body beat embedded review sections
  - abstention is a real output (OPEN -> HARD tier), never a guess

Field identifier (panel-reviewed): environmental density vs neuroscience density,
TA-weighted, per-10k-chars; buckets in_field / pure_neuroscience /
out_of_field_candidate / borderline; non-English -> HARD.

Usage:
  python3 scripts/typer_v1.py --gold20     # calibration receipt vs David's rulings
  python3 scripts/typer_v1.py --full       # all papers with a production PDF
"""
import json, re, sqlite3, glob, sys, csv, datetime
from pathlib import Path

AE = Path("/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery")
AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
OUT = AF / "data/topic_comparison/full1760_2026-09-09"
CAT = Path("/private/tmp/claude-501/-Users-davidusa-REPOS-New-VR-Platform/b07ed661-0ea6-4535-8b9d-cd0200658a81/scratchpad/drive_catalogue/pdf_holdings.jsonl")
TYPER_VERSION = "typer_v1_2026-09-09_fable"
FIELD_VERSION = "field_v1_2026-09-09_fable_panel_reviewed"

# David's final gold-20 rulings (family level) for the calibration receipt
GOLD20_FINAL = {
 "PDF-0040":"review","PDF-0062":"empirical","PDF-0071":"review","PDF-0108":"empirical",
 "PDF-0154":"empirical","PDF-0196":"empirical","PDF-0404":"empirical","PDF-0446":"empirical",
 "PDF-0461":"review","PDF-0466":"theoretical","PDF-0674":"empirical","PDF-0802":"review",
 "PDF-0839":"review","PDF-1106":"empirical",
}

P = {
 "stats": re.compile(r"\bp\s*[<=>]\s*\.?\d|\bF\s*\(\s*\d+\s*,|\bt\s*\(\s*\d+\s*\)|\bt\s*\[\s*\d+\s*\]|χ2|chi-square|\bANOVA\b|\bSD\s*=|95%\s*CI|\br\s*=\s*[-.\d]|β\s*=|Bonferroni|MANOVA|regression coefficient", re.I),
 "parts": re.compile(r"\b[nN]\s*=\s*\d{2,}|\b\d+\s*(participants|subjects|respondents|observers|informants|employees|residents|workers|occupants|users|students took|people from)\b|survey\s+of\s+\d+|\(\s*=?\s*\d{2,}\s*\)\s*were", re.I),
 "prisma": re.compile(r"\bPRISMA\b|search\s+strateg|systematic(ally)?\s+search|databases?\s+(were\s+)?searched|\bScopus\b.{0,60}\bsearch|\bWeb of Science\b.{0,60}\bsearch", re.I),
 "meta": re.compile(r"\bmeta-?analy|pooled\s+(effect|estimate)|random-effects\s+model|forest plot", re.I),
 "qual": re.compile(r"\b(semi-structured\s+)?interviews?\b|focus groups?|thematic analysis|grounded theory|ethnograph|content analysis|open coding|go-along", re.I),
 "review": re.compile(r"(this|the present|our)\s+(critical\s+|narrative\s+|literature\s+)?review\b|we\s+review\b|reviews?\s+the\s+literature|literature\s+review", re.I),
 "theory": re.compile(r"we\s+(propose|argue|develop|advance)\b|(proposes?|develops?|argues?|claims?|contends?)\s+(that|a\s+(model|framework|theory))|theoretical\s+framework|conceptual\s+model|is meant to equip|this (paper|article|chapter) (argues|discusses|contends)", re.I),
 "expt_ta": re.compile(r"\beffects? of\b|\bexperiment|randomi[sz]|were (each )?exposed to|\btrials?\b|we (tested|measured|conducted|examined)|\bconditions?\b.{0,40}\b(via|using|combinations)|\bsurvey\b|questionnaire", re.I),
 "review_ta_loose": re.compile(r"\breview\b", re.I),
}
FORM = {
 "commentary": re.compile(r"\b(response to|reply to|comment(ary)? on|letter to the editor|editorial)\b", re.I),
 "proceedings": re.compile(r"\bproceedings\b|conference\s+(proceedings|papers)|symposium\b", re.I),
 "thesis": re.compile(r"in partial fulfill?ment|doctoral dissertation|master'?s thesis|submitted .{0,60}degree", re.I),
}
ENV = re.compile(r"architect|built environment|building|indoor|interior|room\b|ceiling|facade|dwelling|residential|housing|urban|neighbou?rhood|city|street|landscape|park\b|green space|greenery|garden|workplace|office|classroom|school building|hospital design|lighting|illuminan|daylight|luminous|acoustic|soundscape|noise|reverberation|thermal comfort|ventilation|biophil|wayfinding|spatial (experience|quality|design)|place attachment|restorativ|environmental (psychology|design|stressor)|occupant", re.I)
NEURO = re.compile(r"\bfMRI\b|\bEEG\b|\bERP\b|\bMEG\b|neuroimaging|cortex|cortical|neural|neuron|amygdala|hippocamp|prefrontal|parietal|default mode network|electrophysiolog|brain activ|neurosci", re.I)
NONASCII = re.compile(r"[áéíóúñüàèìòùâêîôûäöß]", re.I)
REFS = re.compile(r"\n#*\s*(references|bibliography|works cited|literatura)\s*\n", re.I)

def split_refs(text):
    cut = None
    for m in REFS.finditer(text):
        if m.start() > len(text) * 0.4: cut = m.start()
    return (text[:cut], text[cut:]) if cut else (text, "")

def span(pat, text, w=80):
    m = pat.search(text)
    if not m: return None
    s = max(0, m.start() - 15)
    return re.sub(r"\s+", " ", text[s:m.end() + w - 15]).strip()[:w]

def load_text(pid):
    txt = ""
    for sub in ("ocr_canonical", "docling", "mathpix"):
        for f in glob.glob(str(AE / f"data/papers/{pid}/{sub}/*")):
            if f.lower().endswith((".md", ".txt", ".mmd", ".json")):
                try: txt += open(f, errors="replace").read() + "\n"
                except OSError: pass
        if len(txt) > 4000: break
    return txt

def abstract_of(pid):
    p = AE / f"data/papers/{pid}/sc_summary/gold.json"
    if p.exists():
        try: return (json.load(open(p)).get("abstract") or "")
        except Exception: return ""
    return ""

def classify(pid, title, text):
    body, refs = split_refs(text)
    ab = abstract_of(pid)
    ta = (title or "") + "\n" + ab[:1500]
    tl = (title or "").lower()
    sig = {k: bool(p.search(body)) for k, p in P.items()}
    tasig = {k: bool(p.search(ta)) for k, p in P.items()}
    rec = {k: span(p, ta) or span(p, body) for k, p in P.items() if sig[k] or tasig[k]}

    form = "journal_article"
    for f, p in FORM.items():
        if p.search(tl) or (f == "thesis" and p.search(body[:4000])) or \
           (f == "proceedings" and p.search(ta)):
            form = {"commentary": "commentary", "proceedings": "edited_collection",
                    "thesis": "thesis"}[f]
            break

    # method — precedence with own-data dominance
    method, conf, basis = "OPEN", 0.35, "no decisive signals"
    empirical_core = sig["parts"] and sig["stats"]
    if "meta-analysis" in tl or "meta analysis" in tl or tasig["meta"]:
        method, conf, basis = "meta_analysis", 0.85, "meta-analysis in title/abstract"
    elif "systematic review" in tl or ("review" in tl and sig["prisma"]):
        method, conf, basis = "review_systematic", 0.85, "systematic review in title or review+search-strategy"
    elif empirical_core and sig["qual"]:
        method, conf, basis = "mixed", 0.7, "participants+stats+qualitative methods in body"
    elif empirical_core:
        method, conf, basis = "empirical_quant", 0.85, "participants+statistics in pre-references body"
    elif sig["stats"] and not ("review" in tl or tasig["review"] or tasig["meta"]):
        method, conf, basis = "empirical_quant", 0.6, "statistics in body without participant count (GREY: verify count)"
    elif (sig["parts"] or tasig["parts"]) and tasig["expt_ta"]:
        method, conf, basis = "empirical_quant", 0.65, "participants + experiment language in title/abstract"
    elif sig["qual"] and (sig["parts"] or tasig["qual"]):
        method, conf, basis = "empirical_qual", 0.7, "qualitative data-collection language"
    elif "review" in tl or tasig["review"]:
        method, conf, basis = "review_narrative", 0.8, "review in title/abstract"
    elif tasig["review_ta_loose"] and not sig["parts"]:
        method, conf, basis = "review_narrative", 0.7, "self-described review in title/abstract (loose cue)"
    elif sig["prisma"] and sig["review"]:
        method, conf, basis = "review_systematic", 0.6, "search-strategy + review language in body"
    elif sig["review"] and not sig["parts"]:
        method, conf, basis = "review_narrative", 0.6, "review language, no own data"
    elif tasig["theory"] or (sig["theory"] and not sig["parts"] and not sig["stats"]):
        method, conf, basis = "theoretical", 0.6, "theory-building language, no data collection (theory required, not just abstraction - DK criterion)"
    if form == "edited_collection":
        method, conf, basis = "OPEN", 0.5, "collection volume; per-paper typing needs splitting"
    if len(text) < 6000:
        conf = min(conf, 0.45); basis += "; TEXT THIN"

    # field
    n10 = max(1, len(body)) / 10000
    env_d = (len(ENV.findall(body)) + 5 * len(ENV.findall(ta))) / n10
    neuro_d = (len(NEURO.findall(body)) + 5 * len(NEURO.findall(ta))) / n10
    nonenglish = len(NONASCII.findall(ta)) > 8
    if env_d >= 6:      bucket = "in_field"
    elif neuro_d >= 6:  bucket = "pure_neuroscience"
    elif env_d >= 2.5:  bucket = "borderline"
    else:               bucket = "out_of_field_candidate"
    if nonenglish: bucket, conf = "borderline", min(conf, 0.4)

    tier = ("CLEAN" if conf >= 0.8 and bucket == "in_field" else
            "HARD" if conf < 0.5 or method == "OPEN" or nonenglish
                     or bucket == "pure_neuroscience" else "GREY")
    fam = ("empirical" if method.startswith(("empirical", "mixed")) else
           "review" if method.startswith(("review", "meta")) else method)
    return {"paper_id": pid, "title": (title or "")[:140], "method": method,
            "family": fam, "form": form, "confidence": round(conf, 2),
            "basis": basis, "field_bucket": bucket,
            "env_density": round(env_d, 1), "neuro_density": round(neuro_d, 1),
            "non_english": nonenglish, "tier": tier, "text_chars": len(text),
            "receipts": {k: v for k, v in rec.items() if v},
            "typer_version": TYPER_VERSION, "field_version": FIELD_VERSION}

def titles_map():
    t = {}
    if CAT.exists():
        for line in CAT.read_text().splitlines():
            try:
                h = json.loads(line); t[h["paper_id"]] = h.get("title") or ""
            except Exception: pass
    con = sqlite3.connect(f"file:{AE/'data/verification_runs/v7_gold_extraction_registry.db'}?mode=ro", uri=True)
    for pid, title in con.execute("SELECT paper_id, title FROM gold_papers"):
        t.setdefault(pid, title or "")
    return t

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--gold20"
    titles = titles_map()
    if mode == "--gold20":
        pids = sorted(GOLD20_FINAL)
    else:
        con = sqlite3.connect(f"file:{AE/'data/article_eater_lifecycle.db'}?mode=ro", uri=True)
        pids = sorted({r[0] for r in con.execute(
            "SELECT DISTINCT paper_id FROM papers WHERE pdf_path LIKE '%production/pdfs%'")})
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for i, pid in enumerate(pids):
        try:
            results.append(classify(pid, titles.get(pid, ""), load_text(pid)))
        except Exception as e:
            results.append({"paper_id": pid, "method": "ERROR", "tier": "HARD",
                            "error": str(e)[:120]})
        if (i + 1) % 200 == 0: print(f"...{i+1}/{len(pids)}")

    if mode == "--gold20":
        ok = 0
        for r in results:
            want = GOLD20_FINAL[r["paper_id"]]
            got = r.get("family")
            hit = got == want
            ok += hit
            print(f"{r['paper_id']} want={want:11s} got={str(r.get('method')):17s} "
                  f"fam={str(got):11s} conf={r.get('confidence')} {'OK' if hit else 'MISS'}")
        print(f"CALIBRATION: {ok}/{len(results)} family agreement vs David's final rulings")
        (OUT / "calibration_gold20.json").write_text(json.dumps(results, indent=2))
        return

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with open(OUT / "typer_v1_results.jsonl", "w") as f:
        for r in results: f.write(json.dumps(r) + "\n")
    with open(OUT / "typer_v1_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["paper_id","method","family","form","confidence","field_bucket",
                    "tier","env_density","neuro_density","non_english","title"])
        for r in results:
            w.writerow([r.get(k, "") for k in ("paper_id","method","family","form",
                        "confidence","field_bucket","tier","env_density",
                        "neuro_density","non_english","title")])
    def cnt(key):
        c = {}
        for r in results: c[r.get(key, "?")] = c.get(r.get(key, "?"), 0) + 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))
    summary = {"run_at": stamp, "papers": len(results),
               "typer_version": TYPER_VERSION, "field_version": FIELD_VERSION,
               "method": cnt("method"), "family": cnt("family"), "form": cnt("form"),
               "field_bucket": cnt("field_bucket"), "tier": cnt("tier"),
               "pure_neuroscience": sorted(r["paper_id"] for r in results
                                           if r.get("field_bucket") == "pure_neuroscience"),
               "out_of_field_candidates": sorted(r["paper_id"] for r in results
                                                 if r.get("field_bucket") == "out_of_field_candidate")}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("papers","family","field_bucket","tier")}, indent=2))
    print(f"pure_neuroscience bucket: {len(summary['pure_neuroscience'])}")
    print(f"out_of_field candidates: {len(summary['out_of_field_candidates'])}")

if __name__ == "__main__":
    main()
