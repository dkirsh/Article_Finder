#!/usr/bin/env python3
"""field_v2_calibrate.py — learn from David's 69 field rulings (2026-09-10) and
build field identifier v2 with the new pure_psychology bucket.

David's definition, verbatim, now canon: "pure_psychology is neither out_of_field
nor borderline. It is an adjacent-evidence bucket for studies of human cognition,
emotion, behaviour, or clinical outcomes that lack a substantive built, spatial,
environmental, or ambient exposure. This distinction prevents useful psychological
theory and measurement papers from being discarded while stopping them from
masquerading as direct CNfA evidence."

Steps: (1) confusion matrix machine-v1 vs David; (2) v2 = five lexicons
(environmental, perceptual-substrate, psychology, physiological-measurement,
hard-science) with rule order calibrated by coarse grid search against David's
rulings; (3) report agreement v1 vs v2; (4) rerun v2 over all 1,760.
Read-only against corpora; writes results + summary beside the v1 outputs."""
import json, re, glob, itertools
from pathlib import Path

AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
SRC = AF / "data/topic_comparison/full1760_2026-09-09"
B = AF / "data/topic_comparison/field_batch_2026-09-09"
AE = "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery"

rows = {r["paper_id"]: r for r in map(json.loads, open(SRC / "typer_v1_results.jsonl"))}
david = {}
for l in open(B / "judgments_autosave.jsonl"):
    r = json.loads(l)
    david[r["paper_id"]] = r["field"]

# 1. confusion: machine v1 bucket vs David (cluster heads only)
conf = {}
for pid, dv in david.items():
    mv = rows.get(pid, {}).get("field_bucket", "?")
    conf[(mv, dv)] = conf.get((mv, dv), 0) + 1
print("== machine v1 -> David ==")
for (mv, dv), n in sorted(conf.items(), key=lambda kv: -kv[1]):
    print(f"  {mv:24s} -> {dv:18s} {n}")

# 2. lexicons
ENV = re.compile(r"architect|built environment|building|indoor|interior|room\b|ceiling|facade|dwelling|residential|housing|urban|neighbou?rhood|city|street|landscape|park\b|green space|greenery|garden|workplace|office|classroom|school building|hospital design|lighting|illuminan|daylight|luminous|acoustic|soundscape|noise|reverberation|thermal comfort|ventilation|biophil|wayfinding|spatial (experience|quality|design)|place attachment|restorativ|environmental (psychology|design|stressor)|occupant", re.I)
PERCEP = re.compile(r"psychophysic|visual space|depth cue|optic flow|spatial orientation|slant|occlusion|transparen|transluc|haptic|tactile|multisensory|multi-sensory|cross-?modal|colou?r[- ](emotion|preference)|material (perception|experience|selection)|sensorial|olfact|\bsmell\b|\bodou?r\b|texture perception|shape (grammar|perception)|aesthetic", re.I)
PSYCH = re.compile(r"\bemotion|\bcognit|\bmemory\b|\battention\b|wellbeing|well-being|mental health|\banxiety|\bdepress|happiness|\bmotivat|personality|clinical (trial|outcome|population)|\btherapy|synesthe|eye[- ]movement|habit[- ]formation|judgment and decision|\blearning\b", re.I)
MEAS = re.compile(r"biomarker|cortisol|\bHRV\b|heart rate variability|skin conductance|electrodermal|psychophysiolog|physiological (measure|response|marker)|\bEEG\b|pupillometr|salivary", re.I)
HARD = re.compile(r"spacetime|quantum|spin-1/2|theorem|algebraic|hyperelliptic|metamaterial|tectonic|fault (displacement|model)|molecule|chemical bond|U\(1\)|developable surface|zitterbewegung", re.I)

def densities(pid):
    r = rows.get(pid)
    if not r: return None
    txt = ""
    for sub in ("docling", "ocr_canonical", "mathpix"):
        for f in glob.glob(f"{AE}/data/papers/{pid}/{sub}/*"):
            if f.lower().endswith((".md", ".txt", ".mmd", ".json")):
                try: txt += open(f, errors="replace").read()
                except OSError: pass
        if len(txt) > 4000: break
    cut = None
    for m in re.finditer(r"\n#*\s*(references|bibliography)\s*\n", txt, re.I):
        if m.start() > len(txt) * 0.4: cut = m.start()
    body = txt[:cut] if cut else txt
    ta = (r.get("title") or "")
    n10 = max(1, len(body)) / 10000
    d = lambda p: (len(p.findall(body)) + 5 * len(p.findall(ta))) / n10
    return {"env": d(ENV), "percep": d(PERCEP), "psych": d(PSYCH), "meas": d(MEAS), "hard": d(HARD)}

dens = {}
for pid in set(list(david) + list(rows)):
    if pid in david:  # calibration set first; corpus later
        v = densities(pid)
        if v: dens[pid] = v
print(f"densities computed for {len(dens)} ruled papers")

def classify(v, tE, tP, tH):
    if v["hard"] >= tH and v["env"] < tE: return "out_of_field"
    if v["env"] >= tE: return "in_field"
    if v["meas"] >= 4: return "in_field"          # measurement infrastructure (David: biomarker papers IN)
    if v["percep"] >= tP: return "in_field" if v["env"] >= tE / 3 else "borderline"
    if rows_neuro >= 6 and v["env"] < tE: return "pure_neuroscience"
    if v["psych"] >= 4 and v["env"] < tE: return "pure_psychology"
    if v["env"] >= tE / 2.5: return "borderline"
    return "out_of_field"

best = None
for tE, tP, tH in itertools.product((4, 5, 6, 7), (3, 4, 6, 8), (2, 3, 5)):
    ok = 0
    for pid, dv in david.items():
        v = dens.get(pid)
        if not v: continue
        global rows_neuro; rows_neuro = rows.get(pid, {}).get("neuro_density", 0)
        mv = classify(v, tE, tP, tH)
        # scoring: exact match, plus credit when v2 says pure_psychology for a David borderline/out
        if mv == dv: ok += 1
        # David 2026-09-10: some borderlines were forced (no pure_psychology option
        # existed) -> full credit for pp where he said borderline, half for out.
        elif mv == "pure_psychology" and dv == "borderline": ok += 1
        elif mv == "pure_psychology" and dv == "out_of_field": ok += 0.5
    if not best or ok > best[0]: best = (ok, tE, tP, tH)
ok, tE, tP, tH = best
print(f"v2 grid best: agreement score {ok}/{len(dens)} at env>={tE}, percep>={tP}, hard>={tH}")

# v1 baseline agreement on same set
v1ok = sum(1 for pid, dv in david.items() if rows.get(pid, {}).get("field_bucket") == dv)
print(f"v1 exact agreement on ruled set: {v1ok}/{len(david)}")

# per-paper v2 vs David for the record
detail = []
for pid, dv in sorted(david.items()):
    v = dens.get(pid)
    if not v: continue
    rows_neuro = rows.get(pid, {}).get("neuro_density", 0)
    detail.append({"paper_id": pid, "david": dv, "v1": rows.get(pid, {}).get("field_bucket"),
                   "v2": classify(v, tE, tP, tH), **{k: round(x, 1) for k, x in v.items()}})
(SRC / "field_v2_calibration.json").write_text(json.dumps(
    {"thresholds": {"env": tE, "percep": tP, "hard": tH},
     "v1_exact_agreement": v1ok, "v2_score": ok, "n": len(dens),
     "david_definition_pure_psychology": "adjacent-evidence bucket for studies of human cognition, emotion, behaviour, or clinical outcomes that lack a substantive built, spatial, environmental, or ambient exposure",
     "detail": detail}, indent=1))
mism = [d for d in detail if d["v2"] != d["david"]]
print(f"v2 exact matches: {len(detail)-len(mism)}/{len(detail)}; wrote field_v2_calibration.json")
for d in mism[:12]:
    print(f"  v2 miss {d['paper_id']}: david={d['david']} v2={d['v2']} (env={d['env']} percep={d['percep']} psych={d['psych']})")
