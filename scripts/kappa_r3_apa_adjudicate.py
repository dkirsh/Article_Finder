#!/usr/bin/env python3
"""kappa_r3_apa_adjudicate.py — David Kirsh's descope ruling (2026-09-13): the
apa_citation stratum is a lookup problem, not a judgment problem. Every apa item
whose paper has a clean, DOI-anchored pipeline APA is adjudicated BY MACHINE
(candidate vs pipeline citation); only items on papers without a clean pipeline
APA remain in the human queue. Also assembles the David-rulings comparator: his
existing human rulings on kappa-20 papers, folded in at ANALYSIS time (never
into the frozen pack).

Outputs (repo-side; the pack receives only the id list via the reviser):
  apps/kappa_review_r3/receipts/apa_machine_adjudication.json
  apps/kappa_review_r3/receipts/david_rulings_comparator.json
  apps/kappa_review_r3/machine_resolved_items.json   (id list for the payload)
"""
import json, re, sys, datetime
from pathlib import Path

sys.path.insert(0, "/Users/davidusa/REPOS/Article_Eater_PostQuinean_v1_recovery")
from src.services.db_locator import get_lifecycle_db_connection

AF = Path("/Users/davidusa/REPOS/Article_Finder_v3_2_3")
PACK = Path("/Users/davidusa/REPOS/_shared_artifacts/AE_HITL/"
            "AE_KAPPA_PILOT_FROZEN_20_PLUS_DEMO_HITL_R2_2026-08-20")  # frozen source of items
OUT = AF / "apps/kappa_review_r3"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def tokens(v):
    return {t for t in re.findall(r"[a-z0-9]{3,}", str(v or "").lower())}

def jac(a, b):
    A, B = tokens(a), tokens(b)
    return len(A & B) / max(1, len(A | B))

data = json.loads((PACK / "review_data.json").read_text())
apa_items = [i for i in data["items"] if i["stratum"] == "apa_citation"]
kappa_pids = sorted({i["paper_id"] for i in data["items"]
                     if i["evaluation_role"] == "human_kappa_evaluation"})

con = get_lifecycle_db_connection()
q = ",".join("?" * len(kappa_pids))
bib = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
    f"SELECT paper_id, apa_citation, title_trust, source FROM paper_bibliographic WHERE paper_id IN ({q})", kappa_pids)}
rulings = [dict(zip(("paper_id", "field", "ruled_by", "ruled_at", "provenance"), r)) for r in con.execute(
    f"SELECT paper_id, field, ruled_by, ruled_at, provenance FROM field_rulings_human WHERE paper_id IN ({q})", kappa_pids)]
con.close()

def years_of(v):
    return set(re.findall(r"\b(?:19|20)\d\d\b", str(v or "")))

resolved, remaining, records, t17_seed = [], [], [], []
for item in apa_items:
    pid = item["paper_id"]
    apa, trust, src = bib.get(pid, (None, None, None))
    src, trust = str(src or ""), str(trust or "")
    # Cleanliness is LINEAGE-AWARE (round-4 review F3; the PDF-0814 lesson):
    # a row whose source passed through the quarantine or an OpenAlex title
    # match is not clean unless a document/human trust class has since
    # overridden it. A trust label never outranks its own contradicting lineage.
    lineage_ok = not ("QUARANTINED" in src or "oa_title_match" in src) or \
        trust.startswith(("document_front_matter", "human"))
    clean = bool(apa) and not str(apa).startswith("SUSPECT") and lineage_ok
    cand = item.get("candidate_projection")
    if cand is None:
        cand = (item.get("candidate_display") or {}).get("value")
    if not clean:
        reason = ("pipeline APA lineage untrusted (source: " + src[:60] + ")"
                  if apa and not str(apa).startswith("SUSPECT") and not lineage_ok
                  else "no clean pipeline APA on record")
        remaining.append(item["item_id"])
        records.append({"item_id": item["item_id"], "paper_id": pid,
                        "disposition": "human_review", "reason": reason})
        if apa and not lineage_ok:
            t17_seed.append({"paper_id": pid, "source": src, "title_trust": trust,
                             "note": "kappa-20 apa row with contradicted lineage (round-4 review F2/F3)"})
        continue
    cy, py = years_of(cand), years_of(apa)
    if cand in (None, ""):
        verdict, reason = "incorrect", "candidate claimed no citation; DOI-anchored pipeline APA exists"
    elif jac(cand, apa) >= 0.35 and (cy & py):
        verdict, reason = "exactly_correct", (
            f"candidate agrees with pipeline APA (jaccard {jac(cand, apa):.2f}, year {sorted(cy & py)[0]})")
    elif jac(cand, apa) >= 0.35 and cy and py and not (cy & py):
        # High overlap but the years disagree (online-first vs print, thesis vs
        # article): a lookup cannot settle which record is right — a human can.
        remaining.append(item["item_id"])
        records.append({"item_id": item["item_id"], "paper_id": pid,
                        "disposition": "human_review",
                        "reason": f"candidate/pipeline year disagreement ({sorted(cy)} vs {sorted(py)})"})
        continue
    elif not cy:
        verdict, reason = "incorrect", (
            "candidate is an incomplete citation (no year/authors — bare title); "
            "pipeline APA supplies the full record")
    else:
        verdict, reason = "incorrect", f"candidate conflicts with pipeline APA (jaccard {jac(cand, apa):.2f})"
    resolved.append(item["item_id"])
    records.append({"item_id": item["item_id"], "paper_id": pid,
                    "disposition": "machine_adjudicated", "machine_verdict": verdict,
                    "corrected_value": (None if verdict == "exactly_correct" else apa),
                    "reason": reason,
                    "adjudicator": "AF metadata pipeline (doi.org content negotiation / document front matter)",
                    "authority": "David Kirsh descope ruling, chat 2026-09-13"})

(OUT / "receipts/apa_machine_adjudication.json").write_text(json.dumps({
    "schema": "kappa_r3_apa_machine_adjudication.v1", "generated_at": NOW,
    "principle": "APA correctness is a lookup problem; human judgment is reserved for papers the pipeline cannot anchor to a DOI.",
    "items": records,
    "summary": {"machine_adjudicated": len(resolved), "human_review": len(remaining)}}, indent=1))
(OUT / "machine_resolved_items.json").write_text(json.dumps(
    {"schema": "kappa_r3_machine_resolved.v1", "machine_resolved_items": sorted(resolved)}, indent=1))
(OUT / "receipts/david_rulings_comparator.json").write_text(json.dumps({
    "schema": "kappa_r3_david_comparator.v1", "generated_at": NOW,
    "purpose": ("David Kirsh's existing human rulings on kappa-20 papers, applied as a "
                "third comparator at ANALYSIS time (Stephan vs machine vs David where "
                "available). Never merged into the frozen pack; human provenance outranks machine."),
    "field_rulings": rulings,
    "note": "Extend with David's blind-50 export and any later rulings before scoring."}, indent=1))
if t17_seed:
    (OUT / "receipts/t17_seed_from_kappa.json").write_text(json.dumps(
        {"schema": "t17_seed.v1", "generated_at": NOW, "rows": t17_seed}, indent=1))
print(f"apa items: {len(apa_items)} -> machine-adjudicated {len(resolved)}, remaining for Stephan {len(remaining)}; T17 seeds: {len(t17_seed)}")
for r in records:
    tag = r.get("machine_verdict", "HUMAN")
    print(f"  {r['item_id']:28s} {tag:16s} {r['reason'][:80]}")
print(f"David comparator: {len(rulings)} rulings on kappa-20 papers")
