#!/usr/bin/env python3
"""
prisma_dashboard.py — Task 3 Phase 6.

Reconstructs the PRISMA funnel from a SINGLE GROUP BY over `article_references`,
then writes:
  - data/prisma_funnel.json   (machine-readable)
  - data/prisma_dashboard.html (human-readable, no JS framework — vanilla HTML/CSS)

This satisfies the contract: "PRISMA funnel from one SQL GROUP BY".
"""

from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path

from db_schema import open_db, DEFAULT_DB

OUT_DIR = Path(__file__).resolve().parent / "data"

# The single SQL statement that reconstructs the funnel.
PRISMA_SQL = """
SELECT
    COUNT(*)                                                            AS identified,
    SUM(CASE WHEN stage1_screen='reject_metadata' THEN 1 ELSE 0 END)    AS removed_metadata,
    SUM(CASE WHEN stage1_screen='pass'            THEN 1 ELSE 0 END)    AS screened,
    SUM(CASE WHEN stage2_verdict='missing_abstract' THEN 1 ELSE 0 END)  AS missing_abstract,
    SUM(CASE WHEN stage2_verdict='reject'          THEN 1 ELSE 0 END)   AS reject_topic,
    SUM(CASE WHEN stage2_verdict='edge_case'       THEN 1 ELSE 0 END)   AS edge_case,
    SUM(CASE WHEN stage2_verdict='accept'          THEN 1 ELSE 0 END)   AS accept,
    SUM(CASE WHEN pdf_status='got'                 THEN 1 ELSE 0 END)   AS pdf_got,
    SUM(CASE WHEN pdf_status='scidownl_blocked'    THEN 1 ELSE 0 END)   AS pdf_blocked,
    SUM(CASE WHEN pdf_status='no_oa'               THEN 1 ELSE 0 END)   AS pdf_no_oa
FROM article_references
"""


def compute(conn: sqlite3.Connection) -> dict:
    row = conn.execute(PRISMA_SQL).fetchone()
    funnel = dict(row)
    funnel["included"] = funnel["accept"] + funnel["edge_case"]
    return funnel


HTML_TPL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>PRISMA Funnel — Task 3</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 760px; margin: 2em auto;
          background: #fafafa; color: #222; }}
  h1 {{ font-size: 1.6em; margin-bottom: 0.2em; }}
  .stage {{ background: white; border-left: 6px solid #B45F14; padding: 1em 1.2em;
            margin: 0.6em 0; box-shadow: 0 1px 2px rgba(0,0,0,0.04); border-radius: 6px; }}
  .stage h3 {{ margin: 0 0 0.3em 0; font-size: 1em; color: #555; }}
  .count {{ font-size: 1.6em; font-weight: 600; color: #222; }}
  .sub {{ color: #888; font-size: 0.85em; margin-left: 1em; }}
  .out {{ border-left-color: #999; }}
  .accept {{ border-left-color: #2e7d32; }}
  .edge {{ border-left-color: #ed8936; }}
  .reject {{ border-left-color: #c53030; }}
  footer {{ font-size: 0.8em; color: #888; margin-top: 2em; }}
</style></head>
<body>
<h1>PRISMA Funnel — Article Finder Task 3</h1>
<p>Reconstructed from a single <code>GROUP BY</code> over <code>article_references</code>.</p>

<div class="stage">
  <h3>Identification</h3>
  <div class="count">{identified}</div>
  records harvested across all queries.
</div>

<div class="stage out">
  <h3>Removed at metadata screen (Stage 1)</h3>
  <div class="count">{removed_metadata}</div>
  off-topic ML jargon / pre-2005 / other heuristic rejects.
</div>

<div class="stage">
  <h3>Screened with abstract</h3>
  <div class="count">{screened}</div>
  passed Stage 1.
  <div class="sub">missing_abstract: {missing_abstract}</div>
</div>

<div class="stage reject">
  <h3>Stage 2 rejects (off-topic)</h3>
  <div class="count">{reject_topic}</div>
</div>

<div class="stage edge">
  <h3>Edge cases (manual review)</h3>
  <div class="count">{edge_case}</div>
</div>

<div class="stage accept">
  <h3>Accepted</h3>
  <div class="count">{accept}</div>
</div>

<div class="stage">
  <h3>PDFs acquired</h3>
  <div class="count">{pdf_got}</div>
  via OA cascade (Unpaywall → S2 → Publisher).
  <div class="sub">scidownl_blocked: {pdf_blocked} · no_oa: {pdf_no_oa}</div>
</div>

<div class="stage accept">
  <h3>Included in synthesis</h3>
  <div class="count">{included}</div>
  ACCEPT + EDGE_CASE.
</div>

<footer>Generated from <code>{db}</code> · single SQL: see <code>prisma_dashboard.py</code></footer>
</body></html>
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    conn = open_db(args.db)
    funnel = compute(conn)
    conn.close()

    json_path = args.out_dir / "prisma_funnel.json"
    json_path.write_text(json.dumps(funnel, indent=2), encoding="utf-8")

    html_path = args.out_dir / "prisma_dashboard.html"
    html_path.write_text(HTML_TPL.format(db=args.db.name, **funnel), encoding="utf-8")

    print("PRISMA funnel:")
    for k, v in funnel.items():
        print(f"  {k:<20} {v}")
    print(f"\nWrote: {json_path}")
    print(f"Wrote: {html_path}")


if __name__ == "__main__":
    main()
