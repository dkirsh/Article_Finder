#!/usr/bin/env python3
"""
pdf_acquirer.py — Task 3 Phase 5 (Stage 3).

Reads from `v_acquisition_queue` (ACCEPT rows whose acquired_paper_id is NULL),
walks the documented source cascade in order, and logs every attempt to
`lifecycle_transitions`. EDGE_CASE rows are intentionally NOT processed here.

Cascade (rubric §5A):
  1. Unpaywall          → discovered free OA
  2. OpenAlex OA URL    → publisher-hosted OA
  3. scidownl           → ONLY if all four policy conditions in §5B are met

scidownl gate (rubric §5B — all four required):
  (a) --enable-scidownl flag passed
  (b) `policy_clearance.json` present in repo root, countersigned by instructor
  (c) row's triage_decision == 'ACCEPT' (enforced by view)
  (d) Unpaywall AND OpenAlex BOTH already failed for this reference_id

The clearance file is git-ignored. Without it (the default state), every
attempt at Step 3 is denied with reason='gated:no_policy_clearance' and the
row stays in the queue with pdf_acquisition_attempts incremented.

Usage:
    python3 pdf_acquirer.py
    python3 pdf_acquirer.py --enable-scidownl    # still requires the file
"""

from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path

from db_schema import open_db, DEFAULT_DB, log_transition

REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = REPO_ROOT / "task3" / "data" / "pdfs"
POLICY_CLEARANCE = REPO_ROOT / "policy_clearance.json"


# ─────────────────────────────────────────────────────────────────────────────
# Cascade steps — return (status, path, source_label)
# status ∈ {'hit','miss','skip'}
# ─────────────────────────────────────────────────────────────────────────────
def try_unpaywall(doi: str | None) -> tuple[str, str | None, str]:
    """Real impl would call api.unpaywall.org. For offline/mock runs all miss."""
    if not doi: return ("skip", None, "unpaywall")
    return ("miss", None, "unpaywall")


def try_openalex_oa(doi: str | None) -> tuple[str, str | None, str]:
    if not doi: return ("skip", None, "openalex_oa")
    return ("miss", None, "openalex_oa")


# ─────────────────────────────────────────────────────────────────────────────
# scidownl 4-condition policy gate
# ─────────────────────────────────────────────────────────────────────────────
def scidownl_gate(*, enable_flag: bool, doi: str | None,
                  prior_failed: bool) -> tuple[bool, str]:
    if not enable_flag:
        return (False, "config_flag_off")
    if not POLICY_CLEARANCE.exists():
        return (False, "no_policy_clearance")
    if not doi:
        return (False, "no_doi")
    if not prior_failed:
        return (False, "prior_cascade_not_exhausted")
    return (True, "gate_open")


def try_scidownl(doi: str, out_dir: Path) -> tuple[str, str | None, str]:
    """Stub: real call would be `from scidownl import scihub_download`.
       Synthetic DOIs return miss so the pipeline still runs offline."""
    return ("miss", None, "scidownl")


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────
def run(db_path: Path, enable_scidownl: bool, pdf_dir: Path) -> dict:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    conn = open_db(db_path)
    cur = conn.execute("INSERT INTO run_log (stage) VALUES ('pdf')")
    run_id = cur.lastrowid; conn.commit()

    rows = conn.execute("SELECT * FROM v_acquisition_queue").fetchall()

    counts = {"queue": len(rows), "got": 0, "no_oa": 0,
              "scidownl_blocked": 0, "scidownl_attempted": 0}

    for r in rows:
        ref_id, doi = r["reference_id"], r["doi"]
        result = None
        for fn in (try_unpaywall, try_openalex_oa):
            status, path, src = fn(doi)
            conn.execute(
                "UPDATE article_references SET pdf_acquisition_attempts=pdf_acquisition_attempts+1, "
                "pdf_acquisition_last_source=? WHERE reference_id=?", (src, ref_id))
            log_transition(conn, reference_id=ref_id,
                           from_stage="abstract_collected",
                           to_stage=f"pdf_attempt:{src}",
                           agent="pdf_acquirer", outcome=status,
                           notes=f"source={src}")
            if status == "hit":
                result = (src, path); break

        if result is None:
            ok, reason = scidownl_gate(enable_flag=enable_scidownl,
                                       doi=doi, prior_failed=True)
            if ok:
                status, path, _ = try_scidownl(doi, pdf_dir)
                counts["scidownl_attempted"] += 1
                conn.execute(
                    "UPDATE article_references SET pdf_acquisition_attempts=pdf_acquisition_attempts+1, "
                    "pdf_acquisition_last_source='scidownl' WHERE reference_id=?",
                    (ref_id,))
                log_transition(conn, reference_id=ref_id,
                               from_stage="pdf_attempt:openalex_oa",
                               to_stage="pdf_attempt:scidownl",
                               agent="pdf_acquirer",
                               outcome=status, notes="gate_open")
                if status == "hit":
                    result = ("scidownl", path)
                else:
                    counts["no_oa"] += 1
            else:
                conn.execute(
                    "UPDATE article_references SET pdf_acquisition_last_source=? "
                    "WHERE reference_id=?", (f"gated:{reason}", ref_id))
                log_transition(conn, reference_id=ref_id,
                               from_stage="pdf_attempt:openalex_oa",
                               to_stage="pdf_attempt:scidownl",
                               agent="pdf_acquirer", outcome="gated",
                               notes=f"reason={reason}")
                counts["scidownl_blocked"] += 1

        if result is not None:
            src, path = result
            conn.execute(
                "UPDATE article_references SET acquired_paper_id=?, pdf_path=?, "
                "triage_stage='acquired', "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE reference_id=?",
                (f"paper:{ref_id}", str(path) if path else None, ref_id))
            log_transition(conn, reference_id=ref_id,
                           from_stage="abstract_collected", to_stage="acquired",
                           agent="pdf_acquirer", outcome="success",
                           notes=f"final_source={src}")
            counts["got"] += 1

    conn.commit()
    conn.execute(
        "UPDATE run_log SET finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), "
        "n_in=?, n_out=?, notes=? WHERE run_id=?",
        (counts["queue"], counts["got"], json.dumps(counts), run_id))
    conn.commit(); conn.close()

    print(f"PDF acquisition (queue size={counts['queue']}):")
    for k, v in counts.items():
        print(f"  {k:<20} {v}")
    print(f"  scidownl gate: enable_flag={enable_scidownl} "
          f"clearance_file={'YES' if POLICY_CLEARANCE.exists() else 'NO'}")
    return counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--enable-scidownl", action="store_true",
                   help="Open the scidownl gate (still requires policy_clearance.json)")
    p.add_argument("--pdf-dir", type=Path, default=PDF_DIR)
    args = p.parse_args()
    run(args.db, args.enable_scidownl, args.pdf_dir)


if __name__ == "__main__":
    main()
