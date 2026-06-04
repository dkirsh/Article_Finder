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


def evaluate(voi_threshold: float = 0.5) -> dict:
    items = json.loads(FIXTURE.read_text())
    type_clf, rel_clf, Candidate, consts = at._load_classifier()
    tp = fp = tn = fn = 0
    for i, it in enumerate(items):
        decision, _reason, _conf = at.stage2_decide(
            it["title"], it["abstract"], voi_score=0.7,
            type_clf=type_clf, rel_clf=rel_clf, Candidate=Candidate,
            constitutions=consts, voi_threshold=voi_threshold, ref_id=f"EVAL-{i}")
        pred_relevant = decision in ("ACCEPT", "EDGE_CASE")
        gold_relevant = it["label"] == "relevant"
        if pred_relevant and gold_relevant:        tp += 1
        elif pred_relevant and not gold_relevant:  fp += 1
        elif not pred_relevant and not gold_relevant: tn += 1
        else:                                      fn += 1
    n = len(items)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (tp + tn) / n if n else 0.0
    return {"n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "accuracy": round(accuracy, 3),
            "false_accepts": fp, "false_rejects": fn}


def main() -> None:
    r = evaluate()
    print(f"Labeled triage evaluation (n={r['n']}):")
    print(f"  confusion: tp={r['tp']} fp={r['fp']} tn={r['tn']} fn={r['fn']}")
    print(f"  precision={r['precision']}  recall={r['recall']}  accuracy={r['accuracy']}")
    print(f"  false_accepts (would pollute AE)={r['false_accepts']}  "
          f"false_rejects (would miss high-VOI)={r['false_rejects']}")


if __name__ == "__main__":
    main()
