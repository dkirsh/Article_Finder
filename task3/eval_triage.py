#!/usr/bin/env python3
"""
eval_triage.py — small labeled-abstract evaluation of the Stage 2B relevance triage.

Runs `fixtures/labeled_abstracts.json` (hand-labeled relevant / irrelevant for the
Nature & Attention question constitution) through the SAME classifier the pipeline
uses (`abstract_triage.stage2_decide`) and reports a confusion table + precision /
recall / accuracy, with the two error types named explicitly:

  - false ACCEPT  = irrelevant paper accepted  -> would pollute Article Eater
  - false REJECT  = relevant paper rejected    -> would miss a high-VOI target

This is the "does triage work scientifically" evidence (beyond parser tests).
Requires `atlas_shared` (see TRACK2_DELIVERABLE_MAP.md for how to supply it).

Fixture composition (honest disclosure): the 12 easy negatives are OFF-DOMAIN
papers (ML, materials, finance, genetics...) — they test cross-domain rejection.
The `tier:"hard"` items are WITHIN-DOMAIN near-misses that share environment OR
outcome vocabulary with the question but must still be rejected per the
constitution's own reject/exclusion indicators (ADHD clinical = exclusion_terms;
aesthetics-only / health-outcome-only = "no attention outcome"; mood-only =
edge_case) — they test within-domain discrimination, which is the harder task.
We report BOTH lenient (ACCEPT+EDGE_CASE counted relevant) and strict
(ACCEPT-only counted relevant) so the EDGE_CASE leniency is visible, plus the
hard-subset confusion on its own.

    python3 eval_triage.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import abstract_triage as at  # noqa: E402

FIXTURE = HERE / "fixtures" / "labeled_abstracts.json"


def _confusion(rows: list[tuple]) -> dict:
    """rows = list of (pred_relevant: bool, gold_relevant: bool) -> metrics."""
    tp = sum(1 for p, g in rows if p and g)
    fp = sum(1 for p, g in rows if p and not g)
    tn = sum(1 for p, g in rows if not p and not g)
    fn = sum(1 for p, g in rows if not p and g)
    n = len(rows)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (tp + tn) / n if n else 0.0
    return {"n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "accuracy": round(accuracy, 3), "false_accepts": fp, "false_rejects": fn}


def evaluate(voi_threshold: float = 0.5) -> dict:
    items = json.loads(FIXTURE.read_text())
    type_clf, rel_clf, Candidate, consts = at._load_classifier()
    lenient, strict, hard_lenient = [], [], []
    dist = {"ACCEPT": 0, "EDGE_CASE": 0, "REJECT": 0, "OTHER": 0}
    for i, it in enumerate(items):
        decision, _reason, _conf = at.stage2_decide(
            it["title"], it["abstract"], voi_score=0.7,
            type_clf=type_clf, rel_clf=rel_clf, Candidate=Candidate,
            constitutions=consts, voi_threshold=voi_threshold, ref_id=f"EVAL-{i}")
        dist[decision if decision in dist else "OTHER"] += 1
        gold = it["label"] == "relevant"
        pred_lenient = decision in ("ACCEPT", "EDGE_CASE")
        pred_strict = decision == "ACCEPT"
        lenient.append((pred_lenient, gold))
        strict.append((pred_strict, gold))
        if it.get("tier") == "hard":
            hard_lenient.append((pred_lenient, gold))
    out = _confusion(lenient)
    out["strict"] = _confusion(strict)                # ACCEPT-only counts as relevant
    out["hard_within_domain"] = _confusion(hard_lenient)  # tier:"hard" subset, lenient
    out["decision_distribution"] = dist
    return out


def main() -> None:
    r = evaluate()
    print(f"Labeled triage evaluation (n={r['n']}):")
    print(f"  decisions: {r['decision_distribution']}")
    print(f"  LENIENT (ACCEPT+EDGE_CASE = relevant):")
    print(f"    confusion: tp={r['tp']} fp={r['fp']} tn={r['tn']} fn={r['fn']}")
    print(f"    precision={r['precision']}  recall={r['recall']}  accuracy={r['accuracy']}")
    print(f"    false_accepts (would pollute AE)={r['false_accepts']}  "
          f"false_rejects (would miss high-VOI)={r['false_rejects']}")
    s = r["strict"]
    print(f"  STRICT (ACCEPT-only = relevant): precision={s['precision']} "
          f"recall={s['recall']} accuracy={s['accuracy']} (EDGE_CASE counted as not-relevant)")
    h = r["hard_within_domain"]
    print(f"  HARD within-domain subset (n={h['n']}): tp={h['tp']} fp={h['fp']} "
          f"tn={h['tn']} fn={h['fn']} precision={h['precision']} recall={h['recall']} "
          f"-- proves discrimination on near-misses, not just off-domain papers")


if __name__ == "__main__":
    main()
