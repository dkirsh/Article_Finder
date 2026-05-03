#!/usr/bin/env python3
"""
db_schema.py — Task 3 unified candidate buffer.

Creates / migrates the SQLite DB used by every Task 3 stage:
  search_runner → abstract_collector → abstract_triage → pdf_acquirer → prisma

Design contract: every harvested reference lands in `article_references`. The PRISMA
funnel must be reconstructible from a single GROUP BY over this table.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DB = REPO_ROOT / "data" / "task3.db"


SCHEMA_SQL = """
-- ============================================================================
-- article_references: candidate buffer (every harvested ref lands here)
-- ============================================================================
CREATE TABLE IF NOT EXISTS article_references (
    -- identity
    ref_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key           TEXT NOT NULL UNIQUE,    -- doi || title-hash fallback
    doi                 TEXT,
    title               TEXT,
    authors             TEXT,                    -- JSON array
    year                INTEGER,
    venue               TEXT,
    url                 TEXT,
    abstract            TEXT,

    -- provenance
    source              TEXT NOT NULL,           -- serpapi | scholarly | crossref | openalex | pubmed
    source_query        TEXT,                    -- the query that found it
    source_query_kind   TEXT,                    -- ai_citation | boolean
    gap_id              TEXT,                    -- which gap this query targeted
    framework_id        TEXT,
    voi_score           REAL,
    raw_payload         TEXT,                    -- JSON of upstream record

    -- triage state machine
    stage1_screen       TEXT,                    -- pass | reject_metadata
    stage1_reasons      TEXT,                    -- JSON array
    abstract_source     TEXT,                    -- s2 | crossref | pubmed | openalex | none
    stage2_verdict      TEXT,                    -- accept | edge_case | reject | missing_abstract
    stage2_confidence   REAL,
    stage2_reasons      TEXT,                    -- JSON array
    pdf_status          TEXT,                    -- got | unpaywall_only | no_oa | scidownl_blocked
    pdf_path            TEXT,
    pdf_method          TEXT,                    -- unpaywall | s2_pdf | publisher | scidownl

    -- timestamps
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ar_doi          ON article_references(doi);
CREATE INDEX IF NOT EXISTS idx_ar_source       ON article_references(source);
CREATE INDEX IF NOT EXISTS idx_ar_stage1       ON article_references(stage1_screen);
CREATE INDEX IF NOT EXISTS idx_ar_stage2       ON article_references(stage2_verdict);
CREATE INDEX IF NOT EXISTS idx_ar_pdf_status   ON article_references(pdf_status);
CREATE INDEX IF NOT EXISTS idx_ar_gap          ON article_references(gap_id);


-- ============================================================================
-- run_log: lightweight audit of each stage execution
-- ============================================================================
CREATE TABLE IF NOT EXISTS run_log (
    run_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stage               TEXT NOT NULL,           -- search | collect_abstract | triage | pdf | prisma
    started_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at         TEXT,
    n_in                INTEGER,
    n_out               INTEGER,
    notes               TEXT
);
"""


def open_db(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def reset_db(db_path: Path = DEFAULT_DB) -> None:
    if db_path.exists():
        db_path.unlink()
    open_db(db_path).close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="Drop and recreate the DB")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = p.parse_args()
    if args.reset:
        reset_db(args.db)
        print(f"Recreated {args.db}")
    else:
        open_db(args.db).close()
        print(f"Schema ensured at {args.db}")
