"""Candidate staging buffer with lifecycle provenance.

The buffer borrows the useful part of Track 2's `article_references` table:
every harvested reference gets durable state before it is promoted into AF's
canonical `papers` table. This is deliberately smaller than AF's corpus schema.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candidate_references (
    reference_id TEXT PRIMARY KEY,
    doi TEXT,
    title_raw TEXT,
    title_normalized TEXT,
    first_author_surname TEXT,
    publication_year INTEGER,
    venue TEXT,
    discovered_via TEXT NOT NULL,
    discovered_query TEXT,
    discovery_run_id TEXT,
    source_note TEXT,
    triage_stage TEXT NOT NULL DEFAULT 'metadata_only',
    triage_decision TEXT,
    triage_reason TEXT,
    triage_confidence REAL,
    raw_citation TEXT,
    snippet TEXT,
    abstract TEXT,
    abstract_source TEXT,
    source_url TEXT,
    oa_pdf_url TEXT,
    cited_by_count INTEGER,
    is_open_access INTEGER,
    target_id TEXT,
    target_type TEXT,
    local_heuristic_voi REAL,
    voi_breakdown_json TEXT,
    pdf_acquisition_attempts INTEGER NOT NULL DEFAULT 0,
    pdf_acquisition_last_source TEXT,
    acquired_paper_id TEXT,
    pdf_path TEXT,
    pdf_sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_doi
    ON candidate_references(doi) WHERE doi IS NOT NULL AND doi <> '';
CREATE INDEX IF NOT EXISTS idx_candidate_decision
    ON candidate_references(triage_decision);
CREATE INDEX IF NOT EXISTS idx_candidate_target
    ON candidate_references(target_id, target_type);

CREATE TABLE IF NOT EXISTS candidate_lifecycle (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    agent TEXT NOT NULL,
    outcome TEXT,
    notes TEXT,
    FOREIGN KEY (reference_id) REFERENCES candidate_references(reference_id)
);

CREATE INDEX IF NOT EXISTS idx_candidate_lifecycle_ref
    ON candidate_lifecycle(reference_id);
"""


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi or None


def normalize_title(value: str | None) -> str | None:
    if not value:
        return None
    title = re.sub(r"\s+", " ", value.strip().lower())
    title = re.sub(r"[^\w\s]", "", title)
    return title or None


def _title_tokens(value: str) -> set[str]:
    tokens = set()
    for token in (value or "").split():
        if len(token) <= 2:
            continue
        if len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        tokens.add(token)
    return tokens


def _title_jaccard(left: str, right: str) -> float:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _reference_id(seq: int, when: dt.datetime | None = None) -> str:
    when = when or dt.datetime.now(dt.timezone.utc)
    return f"CAND-{when.strftime('%Y-%m-%d')}-{seq:06d}"


class CandidateBuffer:
    """SQLite-backed staging buffer for discovered candidate papers."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._ensure_columns(conn)

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(candidate_references)").fetchall()
        }
        additions = {
            "source_url": "TEXT",
            "oa_pdf_url": "TEXT",
            "cited_by_count": "INTEGER",
            "is_open_access": "INTEGER",
        }
        for column, sql_type in additions.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE candidate_references ADD COLUMN {column} {sql_type}")

    def reset(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        self.ensure_schema()

    def _next_seq(self, conn: sqlite3.Connection) -> int:
        today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM candidate_references WHERE reference_id LIKE ?",
            (f"CAND-{today}-%",),
        ).fetchone()
        return int(row["n"] or 0) + 1

    def log_transition(
        self,
        conn: sqlite3.Connection,
        *,
        reference_id: str,
        from_stage: str | None,
        to_stage: str,
        agent: str,
        outcome: str,
        notes: str = "",
    ) -> None:
        conn.execute(
            "INSERT INTO candidate_lifecycle "
            "(reference_id, from_stage, to_stage, agent, outcome, notes) "
            "VALUES (?,?,?,?,?,?)",
            (reference_id, from_stage, to_stage, agent, outcome, notes),
        )

    def add_candidate(
        self,
        candidate: dict[str, Any],
        *,
        discovered_via: str,
        discovered_query: str | None = None,
        discovery_run_id: str | None = None,
        target_id: str | None = None,
        target_type: str | None = None,
        local_heuristic_voi: float | None = None,
        voi_breakdown_json: str | None = None,
        fuzzy_title_threshold: float = 0.8,
    ) -> tuple[str, str]:
        """Insert or dedupe a candidate.

        Returns `(reference_id, action)` where action is `inserted`,
        `dedup_doi`, or `dedup_title`.
        """
        doi = normalize_doi(candidate.get("doi"))
        title_raw = candidate.get("title") or candidate.get("title_raw") or ""
        title_norm = normalize_title(title_raw)

        with self.connect() as conn:
            existing = None
            action = "inserted"
            if doi:
                existing = conn.execute(
                    "SELECT reference_id, discovered_via FROM candidate_references "
                    "WHERE doi = ?",
                    (doi,),
                ).fetchone()
                action = "dedup_doi"
            if existing is None and title_norm:
                existing = conn.execute(
                    "SELECT reference_id, discovered_via FROM candidate_references "
                    "WHERE title_normalized = ? AND (doi IS NULL OR doi = '')",
                    (title_norm,),
                ).fetchone()
                action = "dedup_title"
            if existing is None and title_norm and len(title_norm.split()) >= 4:
                rows = conn.execute(
                    "SELECT reference_id, discovered_via, title_normalized "
                    "FROM candidate_references "
                    "WHERE (doi IS NULL OR doi = '') AND title_normalized IS NOT NULL"
                ).fetchall()
                for row in rows:
                    if _title_jaccard(title_norm, row["title_normalized"]) >= fuzzy_title_threshold:
                        existing = row
                        action = "dedup_title"
                        break

            if existing is not None:
                provenance = existing["discovered_via"] or ""
                channels = [c for c in provenance.split(",") if c]
                if discovered_via not in channels:
                    channels.append(discovered_via)
                    conn.execute(
                        "UPDATE candidate_references SET discovered_via=?, "
                        "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                        "WHERE reference_id=?",
                        (",".join(channels), existing["reference_id"]),
                    )
                self.log_transition(
                    conn,
                    reference_id=existing["reference_id"],
                    from_stage="metadata_only",
                    to_stage="metadata_only",
                    agent="candidate_buffer",
                    outcome="dedup",
                    notes=f"merged provenance from {discovered_via}",
                )
                return existing["reference_id"], action

            reference_id = _reference_id(self._next_seq(conn))
            authors = candidate.get("authors") or []
            first_author = ""
            if authors:
                first = authors[0] if isinstance(authors[0], str) else authors[0].get("name", "")
                first_author = first.split(",")[0].strip().split()[-1] if first else ""

            conn.execute(
                "INSERT INTO candidate_references "
                "(reference_id, doi, title_raw, title_normalized, first_author_surname, "
                "publication_year, venue, discovered_via, discovered_query, discovery_run_id, "
                "source_note, triage_stage, raw_citation, snippet, abstract, abstract_source, "
                "source_url, oa_pdf_url, cited_by_count, is_open_access, "
                "target_id, target_type, local_heuristic_voi, voi_breakdown_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    reference_id,
                    doi,
                    title_raw,
                    title_norm,
                    first_author,
                    candidate.get("year") or candidate.get("publication_year"),
                    candidate.get("venue") or candidate.get("journal"),
                    discovered_via,
                    discovered_query,
                    discovery_run_id,
                    candidate.get("source_note"),
                    "metadata_only",
                    candidate.get("raw_citation"),
                    candidate.get("snippet"),
                    candidate.get("abstract"),
                    candidate.get("abstract_source"),
                    candidate.get("url") or candidate.get("source_url") or candidate.get("openalex_id"),
                    candidate.get("oa_url") or candidate.get("oa_pdf_url"),
                    candidate.get("cited_by_count") or candidate.get("citation_count"),
                    1 if candidate.get("open_access") or candidate.get("is_open_access") else 0,
                    target_id,
                    target_type,
                    local_heuristic_voi,
                    voi_breakdown_json,
                ),
            )
            self.log_transition(
                conn,
                reference_id=reference_id,
                from_stage=None,
                to_stage="metadata_only",
                agent="candidate_buffer",
                outcome="success",
                notes=f"harvested via {discovered_via}",
            )
            return reference_id, "inserted"

    def set_triage(
        self,
        reference_id: str,
        *,
        decision: str,
        reason: str,
        confidence: float | None = None,
        stage: str = "abstract_collected",
        agent: str = "candidate_triage",
    ) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT triage_stage FROM candidate_references WHERE reference_id=?",
                (reference_id,),
            ).fetchone()
            if not row:
                raise KeyError(reference_id)
            conn.execute(
                "UPDATE candidate_references SET triage_stage=?, triage_decision=?, "
                "triage_reason=?, triage_confidence=?, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE reference_id=?",
                (stage, decision, reason, confidence, reference_id),
            )
            self.log_transition(
                conn,
                reference_id=reference_id,
                from_stage=row["triage_stage"],
                to_stage=stage,
                agent=agent,
                outcome=decision.lower(),
                notes=reason[:200],
            )

    def record_pdf(
        self,
        reference_id: str,
        *,
        pdf_path: str | Path,
        pdf_sha256: str,
        source: str,
        agent: str = "candidate_pdf_acquirer",
    ) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT triage_stage FROM candidate_references WHERE reference_id=?",
                (reference_id,),
            ).fetchone()
            if not row:
                raise KeyError(reference_id)
            conn.execute(
                "UPDATE candidate_references SET pdf_acquisition_attempts="
                "pdf_acquisition_attempts+1, pdf_acquisition_last_source=?, "
                "acquired_paper_id=?, pdf_path=?, pdf_sha256=?, triage_stage='acquired', "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE reference_id=?",
                (source, f"paper:{reference_id}", str(pdf_path), pdf_sha256, reference_id),
            )
            self.log_transition(
                conn,
                reference_id=reference_id,
                from_stage=row["triage_stage"],
                to_stage="acquired",
                agent=agent,
                outcome="success",
                notes=f"source={source} sha256={pdf_sha256[:12]}",
            )

    def fetchone(self, reference_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM candidate_references WHERE reference_id=?",
                (reference_id,),
            ).fetchone()
            return dict(row) if row else None

    def rows_for_triage(
        self,
        *,
        include_unset_only: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        where = "WHERE triage_decision IS NULL" if include_unset_only else ""
        limit_sql = " LIMIT ?" if limit is not None else ""
        params = (limit,) if limit is not None else ()
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM candidate_references {where} "
                f"ORDER BY created_at ASC{limit_sql}",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def rows_for_promotion(self, include_edge_cases: bool = False) -> list[dict[str, Any]]:
        decisions = ["ACCEPT"]
        if include_edge_cases:
            decisions.append("EDGE_CASE")
        placeholders = ",".join("?" for _ in decisions)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM candidate_references WHERE triage_decision IN ({placeholders}) "
                "ORDER BY local_heuristic_voi DESC, created_at ASC",
                decisions,
            ).fetchall()
            return [dict(row) for row in rows]
