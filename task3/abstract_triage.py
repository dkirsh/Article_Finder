#!/usr/bin/env python3
"""
abstract_triage.py — Task 3 Phase 4.

Implements the three-stage triage:

  Stage 1  metadata-only screen
           - reject if title looks like an off-topic ML/CS paper
           - reject if year < min_year (default 2005)
           - else pass

  Stage 2A abstract collection
           - if `abstract` already populated from search_runner → use it
             (atlas_shared S2/CrossRef/PubMed/OpenAlex fallbacks would slot in here)
           - else mark `missing_abstract`

  Stage 2B classification (delegates to atlas_shared)
           - HeuristicArticleTypeClassifier → article_type
           - QuestionArticleRelevanceFilter against the loaded constitutions
             → verdict in {accept, edge_case, reject}

Stage 3 (PDF acquisition) lives in pdf_acquirer.py.

Usage:
    python3 abstract_triage.py
    python3 abstract_triage.py --min-year 2010 --db data/task3.db
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

from db_schema import open_db, DEFAULT_DB

REPO_ROOT = Path(__file__).resolve().parent.parent
ATLAS_SHARED_SRC = REPO_ROOT.parent / "atlas_shared" / "src"
sys.path.insert(0, str(ATLAS_SHARED_SRC))

CONSTITUTIONS_PATH = (
    ATLAS_SHARED_SRC / "atlas_shared" / "data" / "question_constitutions_starter.json"
)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — metadata screen
# ─────────────────────────────────────────────────────────────────────────────
ML_REJECT_PATTERNS = [
    r"\bdeep learning\b", r"\bconvolutional neural\b", r"\btransformer\b",
    r"\bimagenet\b", r"\bGAN\b", r"\bbatch normalization\b",
]


def stage1_screen(title: str, year: int | None, min_year: int) -> tuple[str, list[str]]:
    reasons: list[str] = []
    t = (title or "").lower()
    for pat in ML_REJECT_PATTERNS:
        if re.search(pat, t):
            reasons.append(f"ml_jargon:{pat}")
    if year is not None and year < min_year:
        reasons.append(f"too_old:{year}<{min_year}")
    return ("reject_metadata" if reasons else "pass", reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — classifier (atlas_shared)
# ─────────────────────────────────────────────────────────────────────────────
def _load_classifier_bits():
    from atlas_shared.article_types import HeuristicArticleTypeClassifier
    from atlas_shared.relevance import (
        QuestionArticleRelevanceFilter, ArticleCandidate, QuestionConstitution,
    )
    data = json.loads(CONSTITUTIONS_PATH.read_text())
    constitutions = [QuestionConstitution.from_panel_spec(q) for q in data["questions"]]
    return (HeuristicArticleTypeClassifier(),
            QuestionArticleRelevanceFilter(),
            ArticleCandidate, constitutions)


def stage2_classify(title: str, abstract: str, type_clf, rel_clf,
                    Candidate, constitutions, ref_id: int) -> dict:
    if not abstract or len(abstract.strip()) < 30:
        return {"verdict": "missing_abstract", "confidence": 0.0,
                "reasons": ["no_abstract"], "article_type": None}

    candidate = Candidate(paper_id=f"task3-{ref_id}", title=title or "", abstract=abstract)
    type_decision = type_clf.classify(abstract=abstract, title=title or "")

    best = None
    for c in constitutions:
        a = rel_clf.assess(c, candidate)
        if a.verdict == "accept":
            best = (a, c); break
        if a.verdict == "edge_case":
            if best is None or best[0].confidence < a.confidence:
                best = (a, c)
    if best is None:
        all_a = [(rel_clf.assess(c, candidate), c) for c in constitutions]
        best = max(all_a, key=lambda x: x[0].confidence)
    a, _c = best

    return {
        "verdict":     a.verdict,
        "confidence":  round(a.confidence, 3),
        "reasons":     list(a.reasons)[:5],
        "article_type": type_decision.value,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────
def run(db_path: Path, min_year: int) -> None:
    conn = open_db(db_path)
    cur = conn.execute("INSERT INTO run_log(stage, n_in) VALUES ('triage', "
                       "(SELECT COUNT(*) FROM article_references WHERE stage1_screen IS NULL))")
    run_id = cur.lastrowid
    conn.commit()

    type_clf, rel_clf, Candidate, constitutions = _load_classifier_bits()
    print(f"Loaded {len(constitutions)} question constitution(s)")

    rows = conn.execute(
        "SELECT ref_id, title, year, abstract FROM article_references "
        "WHERE stage1_screen IS NULL"
    ).fetchall()

    counts = {"reject_metadata": 0, "pass": 0,
              "accept": 0, "edge_case": 0, "reject": 0, "missing_abstract": 0}

    for r in rows:
        s1, s1_reasons = stage1_screen(r["title"], r["year"], min_year)
        counts[s1] += 1
        if s1 == "reject_metadata":
            conn.execute(
                "UPDATE article_references SET stage1_screen=?, stage1_reasons=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE ref_id=?",
                (s1, json.dumps(s1_reasons), r["ref_id"]),
            )
            continue

        cls = stage2_classify(r["title"] or "", r["abstract"] or "",
                              type_clf, rel_clf, Candidate, constitutions, r["ref_id"])
        verdict = cls["verdict"]
        counts[verdict] += 1

        abstract_source = "search_payload" if (r["abstract"] or "").strip() else "none"
        conn.execute(
            "UPDATE article_references SET stage1_screen=?, stage1_reasons=?, "
            "abstract_source=?, stage2_verdict=?, stage2_confidence=?, "
            "stage2_reasons=?, updated_at=CURRENT_TIMESTAMP WHERE ref_id=?",
            (s1, json.dumps(s1_reasons), abstract_source,
             verdict, cls["confidence"], json.dumps(cls["reasons"]),
             r["ref_id"]),
        )

    conn.commit()
    conn.execute("UPDATE run_log SET finished_at=CURRENT_TIMESTAMP, n_out=?, "
                 "notes=? WHERE run_id=?",
                 (len(rows), json.dumps(counts), run_id))
    conn.commit()
    conn.close()

    print("Triage results:")
    for k, v in counts.items():
        print(f"  {k:<20} {v}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--min-year", type=int, default=2005)
    args = p.parse_args()
    run(args.db, args.min_year)


if __name__ == "__main__":
    main()
