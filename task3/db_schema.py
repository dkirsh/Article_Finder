#!/usr/bin/env python3
"""
db_schema.py — Task 3 unified candidate buffer.

Schema mirrors the documented spec (rubric §3A, AF_PIPELINE_RECON_2026-04-27 §3):

    article_references     candidate buffer (every harvested ref lands here)
    lifecycle_transitions  audit log of every stage transition (Stage 1→2→3)
    v_acquisition_queue    view of ACCEPT rows whose acquired_paper_id is NULL
    run_log                lightweight per-stage execution summary

Cardinal rule: every candidate that any harvester touches MUST be inserted into
article_references (or update an existing row's provenance). Free-floating JSON
files do not count for grading.

Note on substitution: the upstream pipeline_lifecycle_full.db file shipped with
this checkout is a populated local SQLite file (gitignored; created on first run) and the canonical scripts/coordination/
lifecycle/schema.sql is not present. This local schema is a faithful
implementation of the documented spec; columns and types match the rubric
verbatim so any later swap to the upstream DB is a drop-in.
"""

from __future__ import annotations
import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
# $TRACK2_DB lets every stage (and subprocess) run against an isolated DB — the
# test harness points it at a per-run temp file so repeated/parallel runs never
# share mutable SQLite state (no DOI-uniqueness collisions / stale PRISMA).
DEFAULT_DB = Path(os.environ.get(
    "TRACK2_DB", str(REPO_ROOT / "data" / "pipeline_lifecycle_full.db")))
# $TRACK2_OUT routes generated JSON/HTML outputs to a temp dir during tests, so
# a verification run leaves the committed data/ tree untouched (full isolation).
DEFAULT_OUT_DIR = Path(os.environ.get("TRACK2_OUT", str(REPO_ROOT / "data")))


SCHEMA_SQL = """
-- ============================================================================
-- article_references: every harvested candidate lives here
-- Spec: rubric Phase 3A — column names match verbatim
-- ============================================================================
CREATE TABLE IF NOT EXISTS article_references (
    -- identity (rubric §3A — Identity)
    reference_id            TEXT PRIMARY KEY,             -- format: REF-YYYY-MM-DD-NNNNNN
    doi                     TEXT,                         -- normalised, lowercased, no URL prefix
    title_raw               TEXT,
    title_normalized        TEXT,
    first_author_surname    TEXT,
    publication_year        INTEGER,
    venue                   TEXT,

    -- provenance (rubric §3A — Provenance)
    discovered_via          TEXT NOT NULL,                -- enum (see CHECK below)
    discovered_from_paper_id TEXT,                        -- FK to papers (when harvested from PDF)
    discovered_query        TEXT,
    discovery_run_id        TEXT,

    -- triage state machine (rubric §3A — Triage state)
    triage_stage            TEXT NOT NULL DEFAULT 'metadata_only',
                                                          -- metadata_only | abstract_pending |
                                                          -- abstract_collected | rejected_at_metadata |
                                                          -- duplicate | acquired
    triage_decision         TEXT,                         -- ACCEPT | EDGE_CASE | REJECT |
                                                          -- MISSING_ABSTRACT
    triage_reason           TEXT,
    triage_confidence       REAL,
    discovered_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    -- raw evidence (rubric §3A)
    raw_citation            TEXT,
    snippet                 TEXT,
    abstract                TEXT,
    abstract_source         TEXT,                         -- s2 | crossref | pubmed | openalex | none

    -- VOI inherited from the gap that produced the query
    gap_template_id         TEXT,
    voi_score               REAL,

    -- PDF acquisition (Stage 3 — Phase 5)
    pdf_acquisition_attempts INTEGER NOT NULL DEFAULT 0,
    pdf_acquisition_last_source TEXT,                     -- unpaywall | openalex_oa | scidownl
    acquired_paper_id       TEXT,                         -- set on success
    pdf_path                TEXT,
    pdf_sha256              TEXT,                         -- SHA-256 of retrieved PDF bytes

    updated_at              TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    -- discovered_via is a comma-separated list of channels (rubric §3B:
    -- duplicates "preserve the multi-channel provenance" via UPDATE-append).
    -- We validate the format with a CHECK on the alphabet, not an IN list.
    CHECK (discovered_via GLOB '[a-z_,]*' AND length(discovered_via) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ar_doi
    ON article_references(doi) WHERE doi IS NOT NULL AND doi <> '';
CREATE UNIQUE INDEX IF NOT EXISTS uq_ar_title_norm
    ON article_references(title_normalized) WHERE doi IS NULL OR doi = '';
CREATE INDEX IF NOT EXISTS idx_ar_triage_stage  ON article_references(triage_stage);
CREATE INDEX IF NOT EXISTS idx_ar_triage_dec    ON article_references(triage_decision);
CREATE INDEX IF NOT EXISTS idx_ar_voi           ON article_references(voi_score DESC);


-- ============================================================================
-- lifecycle_transitions: every stage change is logged here (rubric Phase 5/6)
-- ============================================================================
CREATE TABLE IF NOT EXISTS lifecycle_transitions (
    transition_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id            TEXT NOT NULL,
    timestamp               TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    from_stage              TEXT,
    to_stage                TEXT NOT NULL,
    agent                   TEXT NOT NULL,                -- search_runner | abstract_collector |
                                                          -- abstract_triage | pdf_acquirer
    outcome                 TEXT,                         -- success | failure | skipped | gated
    notes                   TEXT,
    FOREIGN KEY (reference_id) REFERENCES article_references(reference_id)
);

CREATE INDEX IF NOT EXISTS idx_lt_ref ON lifecycle_transitions(reference_id);


-- ============================================================================
-- v_acquisition_queue: rubric §5C — ACCEPT rows awaiting PDF retrieval
-- ============================================================================
CREATE VIEW IF NOT EXISTS v_acquisition_queue AS
SELECT reference_id, doi, title_raw, voi_score, gap_template_id,
       pdf_acquisition_attempts, pdf_acquisition_last_source
FROM article_references
WHERE triage_decision = 'ACCEPT' AND acquired_paper_id IS NULL
ORDER BY voi_score DESC;


-- ============================================================================
-- run_log: per-stage execution summary
-- ============================================================================
CREATE TABLE IF NOT EXISTS run_log (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    stage       TEXT NOT NULL,
    started_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    finished_at TEXT,
    n_in        INTEGER,
    n_out       INTEGER,
    notes       TEXT
);


-- ============================================================================
-- handoff_log: the Track 2 -> Article Eater last mile (rubric ka_track2_setup
-- .html:101-102 — AF "writes a well-defined handoff artefact data/handoff/*.json
-- that the Eater reads"). One row per artefact written by ae_handoff.py.
-- UNIQUE(reference_id) enforces idempotency: a paper is handed off at most once.
-- ============================================================================
CREATE TABLE IF NOT EXISTS handoff_log (
    handoff_id      TEXT PRIMARY KEY,                     -- HANDOFF-<8 hex>
    reference_id    TEXT NOT NULL UNIQUE,                 -- idempotency key
    artefact_path   TEXT NOT NULL,                        -- data/handoff/<reference_id>.json
    handoff_status  TEXT NOT NULL,                        -- written
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY (reference_id) REFERENCES article_references(reference_id)
);
"""


def open_db(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    return conn


def reset_db(db_path: Path = DEFAULT_DB) -> None:
    if db_path.exists():
        db_path.unlink()
    open_db(db_path).close()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers used across stages
# ─────────────────────────────────────────────────────────────────────────────
import re
import datetime as _dt


def normalize_doi(s: str | None) -> str | None:
    """Lowercase, strip URL prefix and whitespace; return None if empty."""
    if not s:
        return None
    s = s.strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    return s or None


def normalize_title(s: str | None) -> str | None:
    if not s:
        return None
    t = re.sub(r"\s+", " ", s.strip().lower())
    t = re.sub(r"[^\w\s]", "", t)
    return t or None


def make_reference_id(seq: int, when: _dt.datetime | None = None) -> str:
    """Format: REF-YYYY-MM-DD-NNNNNN."""
    when = when or _dt.datetime.now(_dt.timezone.utc)
    return f"REF-{when.strftime('%Y-%m-%d')}-{seq:06d}"


def log_transition(conn: sqlite3.Connection, *, reference_id: str,
                   from_stage: str | None, to_stage: str, agent: str,
                   outcome: str, notes: str = "") -> None:
    conn.execute(
        "INSERT INTO lifecycle_transitions (reference_id, from_stage, to_stage, "
        "agent, outcome, notes) VALUES (?,?,?,?,?,?)",
        (reference_id, from_stage, to_stage, agent, outcome, notes),
    )


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = p.parse_args()
    if args.reset:
        reset_db(args.db)
        print(f"Recreated {args.db}")
    else:
        open_db(args.db).close()
        print(f"Schema ensured at {args.db}")
