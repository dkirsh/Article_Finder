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
bib = {r[0]: (r[1], r[2]) for r in con.execute(
    f"SELECT paper_id, apa_citation, title_trust FROM paper_bibliographic WHERE paper_id IN ({q})", kappa_pids)}
rulings = [dict(zip(("paper_id", "field", "ruled_by", "ruled_at", "provenance"), r)) for r in con.execute(
    f"SELECT paper_id, field, ruled_by, ruled_at, provenance FROM field_rulings_human WHERE paper_id IN ({q})", kappa_pids)]
con.close()

resolved, remaining, records = [], [], []
for item in apa_items:
    pid = item["paper_id"]
    apa, _ = bib.get(pid, (None, None))
    clean = bool(apa) and not str(apa).startswith("SUSPECT")
    cand = item.get("candidate_projection")
    if cand is None:
        cand = (item.get("candidate_display") or {}).get("value")
    if not clean:
        remaining.append(item["item_id"])
        records.append({"item_id": item["item_id"], "paper_id": pid,
                        "disposition": "human_review", "reason": "no clean pipeline APA on record"})
        continue
    if cand in (None, ""):
        verdict, reason = "incorrect", "candidate claimed no citation; DOI-anchored pipeline APA exists"
    elif jac(cand, apa) >= 0.35:
        verdict, reason = "exactly_correct", f"candidate agrees with pipeline APA (jaccard {jac(cand, apa):.2f})"
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
print(f"apa items: {len(apa_items)} -> machine-adjudicated {len(resolved)}, remaining for Stephan {len(remaining)}")
for r in records:
    tag = r.get("machine_verdict", "HUMAN")
    print(f"  {r['item_id']:28s} {tag:16s} {r['reason'][:80]}")
print(f"David comparator: {len(rulings)} rulings on kappa-20 papers")
