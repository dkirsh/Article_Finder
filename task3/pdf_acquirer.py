#!/usr/bin/env python3
"""
pdf_acquirer.py — Task 3 Phase 5.

Walks the cascade for every ACCEPT (and optionally EDGE_CASE) row in
`article_references` that doesn't yet have a `pdf_status`:

  1. Unpaywall   (only if DOI present)   → method=unpaywall
  2. Semantic Scholar PDF link            → method=s2_pdf
  3. Publisher direct (if URL is OA)      → method=publisher
  4. scidownl                             → method=scidownl, GATED

scidownl is gated. ALL of the following must hold (config flag default false,
required env var, DOI present, prior cascade exhausted) before any call.

For Track 2 demo / mock-mode runs, the gate is closed by default so the cascade
records `no_oa` or `scidownl_blocked` rather than fetching anything. A real run
flips `--enable-scidownl` only when the user explicitly opts in.

Usage:
    python3 pdf_acquirer.py
    python3 pdf_acquirer.py --include-edge-case --enable-scidownl
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from db_schema import open_db, DEFAULT_DB

PDF_DIR_DEFAULT = Path(__file__).resolve().parent / "data" / "pdfs"


# ─────────────────────────────────────────────────────────────────────────────
# Cascade steps (real network calls would slot in here; for the offline demo
# they all return None)
# ─────────────────────────────────────────────────────────────────────────────
def try_unpaywall(doi: str | None) -> tuple[str, str | None]:
    if not doi:
        return ("skip", None)
    # Real impl would: GET https://api.unpaywall.org/v2/{doi}?email=...
    # For mock/demo: synthetic DOIs (10.1234/synth.*) → no OA hit.
    if doi.startswith("10.1234/synth."):
        return ("miss", None)
    return ("miss", None)


def try_s2(doi: str | None) -> tuple[str, str | None]:
    if not doi:
        return ("skip", None)
    return ("miss", None)


def try_publisher(url: str | None) -> tuple[str, str | None]:
    if not url:
        return ("skip", None)
    return ("miss", None)


# ─────────────────────────────────────────────────────────────────────────────
# scidownl gate — 4 conditions ALL required
# ─────────────────────────────────────────────────────────────────────────────
def scidownl_gate(*, enable_flag: bool, doi: str | None,
                  prior_cascade_exhausted: bool) -> tuple[bool, str]:
    if not enable_flag:
        return (False, "config_flag_off")
    if not os.environ.get("SCIDOWNL_USER_ACK") == "1":
        return (False, "user_ack_env_var_missing")
    if not doi:
        return (False, "no_doi")
    if not prior_cascade_exhausted:
        return (False, "prior_cascade_not_exhausted")
    return (True, "gate_open")


def try_scidownl(doi: str, out_dir: Path) -> tuple[str, str | None]:
    # Real impl would: from scidownl import scihub_download; scihub_download(doi, out=...)
    # Even when gate opens we keep this stub so the CLI surface is correct.
    return ("miss", None)


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────
def run(db_path: Path, include_edge_case: bool, enable_scidownl: bool,
        pdf_dir: Path) -> None:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    conn = open_db(db_path)
    cur = conn.execute("INSERT INTO run_log(stage, n_in) VALUES ('pdf', 0)")
    run_id = cur.lastrowid
    conn.commit()

    verdicts = ("accept",) + (("edge_case",) if include_edge_case else ())
    placeholders = ",".join("?" for _ in verdicts)
    rows = conn.execute(
        f"SELECT ref_id, doi, url FROM article_references "
        f"WHERE stage2_verdict IN ({placeholders}) AND pdf_status IS NULL",
        verdicts,
    ).fetchall()

    counts = {"got": 0, "no_oa": 0, "scidownl_blocked": 0}

    for r in rows:
        # Cascade
        for fn, label, args in [
            (try_unpaywall, "unpaywall", (r["doi"],)),
            (try_s2,         "s2_pdf",   (r["doi"],)),
            (try_publisher,  "publisher",(r["url"],)),
        ]:
            status, path = fn(*args)
            if status == "hit":
                conn.execute("UPDATE article_references SET pdf_status='got', "
                             "pdf_path=?, pdf_method=? WHERE ref_id=?",
                             (path, label, r["ref_id"]))
                counts["got"] += 1
                break
        else:
            # All cascade steps missed — consider scidownl
            ok, reason = scidownl_gate(
                enable_flag=enable_scidownl, doi=r["doi"],
                prior_cascade_exhausted=True,
            )
            if ok:
                status, path = try_scidownl(r["doi"], pdf_dir)
                if status == "hit":
                    conn.execute("UPDATE article_references SET pdf_status='got', "
                                 "pdf_path=?, pdf_method='scidownl' WHERE ref_id=?",
                                 (path, r["ref_id"]))
                    counts["got"] += 1
                else:
                    conn.execute("UPDATE article_references SET pdf_status='no_oa', "
                                 "pdf_method='scidownl_attempted' WHERE ref_id=?",
                                 (r["ref_id"],))
                    counts["no_oa"] += 1
            else:
                conn.execute("UPDATE article_references SET pdf_status=?, "
                             "pdf_method=? WHERE ref_id=?",
                             ("scidownl_blocked" if reason != "no_doi" else "no_oa",
                              f"gated:{reason}", r["ref_id"]))
                if reason == "no_doi":
                    counts["no_oa"] += 1
                else:
                    counts["scidownl_blocked"] += 1

    conn.commit()
    conn.execute("UPDATE run_log SET finished_at=CURRENT_TIMESTAMP, n_in=?, n_out=?, "
                 "notes=? WHERE run_id=?",
                 (len(rows), counts["got"],
                  json.dumps({**counts, "include_edge_case": include_edge_case,
                              "scidownl_enabled": enable_scidownl}),
                  run_id))
    conn.commit()
    conn.close()

    print(f"PDF acquisition over {len(rows)} candidates "
          f"(verdicts={verdicts}):")
    for k, v in counts.items():
        print(f"  {k:<20} {v}")
    print(f"  scidownl gate: {'OPEN' if enable_scidownl else 'CLOSED'} "
          f"(--enable-scidownl + SCIDOWNL_USER_ACK=1 required)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--include-edge-case", action="store_true",
                   help="Also attempt PDFs for EDGE_CASE rows")
    p.add_argument("--enable-scidownl", action="store_true",
                   help="Open the scidownl gate (still requires SCIDOWNL_USER_ACK=1)")
    p.add_argument("--pdf-dir", type=Path, default=PDF_DIR_DEFAULT)
    args = p.parse_args()
    run(args.db, args.include_edge_case, args.enable_scidownl, args.pdf_dir)


if __name__ == "__main__":
    main()
