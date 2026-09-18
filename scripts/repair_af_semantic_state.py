#!/usr/bin/env python3
"""Repair small AF semantic-state drifts exposed by semantic integrity checks."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "article_finder.db"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.contract_fsm_runtime import enforce_transition  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(stored_path: str | None, repo_root: Path) -> Path | None:
    if not stored_path:
        return None
    p = Path(stored_path)
    if p.is_absolute():
        return p
    return repo_root / p


def _append_note(existing: str | None, extra: str) -> str:
    base = (existing or "").strip()
    return f"{base} {extra}".strip() if base else extra


def _load_result(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "result.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def repair(db_path: Path = DB_PATH, *, repo_root: Path = REPO_ROOT) -> dict[str, int]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    stats = {
        "triage_needs_review_normalized": 0,
        "ae_pending_promoted_from_result": 0,
        "ae_stale_terminal_downgraded_to_pending": 0,
        "ae_stale_terminal_cleared_unbuilt": 0,
    }
    now = _now_iso()

    # Normalize deprecated triage vocabulary.
    rowcount = cur.execute(
        """
        UPDATE papers
        SET triage_decision = 'review',
            updated_at = ?
        WHERE triage_decision = 'needs_review'
        """,
        (now,),
    ).rowcount
    stats["triage_needs_review_normalized"] = int(rowcount or 0)

    rows = cur.execute(
        """
        SELECT paper_id, ae_status, ae_job_path, ae_output_path, human_notes
        FROM papers
        WHERE ae_status IS NOT NULL AND TRIM(ae_status) != ''
        """
    ).fetchall()
    for row in rows:
        output_path = _resolve_path(row["ae_output_path"], repo_root)
        output_exists = bool(output_path and output_path.exists())
        job_path = _resolve_path(row["ae_job_path"], repo_root)
        job_exists = bool(job_path and job_path.is_dir())
        if row["ae_status"] == "pending" and output_exists:
            payload = _load_result(output_path)
            if payload:
                summary = payload.get("summary") or {}
                quality = payload.get("quality") or {}
                repaired_status = enforce_transition(
                    "ae_handoff",
                    "pending",
                    f"record:{payload.get('status')}",
                    guards={"output_path_exists": output_exists},
                )
                cur.execute(
                    """
                    UPDATE papers
                    SET ae_status = ?,
                        ae_run_id = ?,
                        ae_n_claims = ?,
                        ae_n_rules = ?,
                        ae_confidence = ?,
                        updated_at = ?
                    WHERE paper_id = ?
                    """,
                    (
                        repaired_status,
                        payload.get("run_id"),
                        summary.get("n_claims"),
                        summary.get("n_rules"),
                        quality.get("confidence"),
                        now,
                        row["paper_id"],
                    ),
                )
                stats["ae_pending_promoted_from_result"] += 1
        elif row["ae_status"] in {"SUCCESS", "PARTIAL_SUCCESS", "FAIL"} and not output_exists:
            if job_exists:
                repaired_state = enforce_transition(
                    "ae_handoff",
                    row["ae_status"],
                    "record_job",
                    guards={"job_path_exists": True},
                )
            else:
                repaired_state = enforce_transition(
                    "ae_handoff", row["ae_status"], "invalidate_evidence"
                )
            repaired_status = None if repaired_state == "unbuilt" else repaired_state
            repair_phrase = (
                "pending"
                if repaired_status == "pending"
                else "unbuilt because neither output nor job bundle exists"
            )
            note = _append_note(
                row["human_notes"],
                f"Downgraded stale terminal ae_status to {repair_phrase} "
                "during AF semantic repair 2026-05-10.",
            )
            cur.execute(
                """
                UPDATE papers
                SET ae_status = ?,
                    ae_output_path = NULL,
                    ae_run_id = NULL,
                    ae_n_claims = NULL,
                    ae_n_rules = NULL,
                    ae_confidence = NULL,
                    human_notes = ?,
                    updated_at = ?
                WHERE paper_id = ?
                """,
                (repaired_status, note, now, row["paper_id"]),
            )
            if repaired_status == "pending":
                stats["ae_stale_terminal_downgraded_to_pending"] += 1
            else:
                stats["ae_stale_terminal_cleared_unbuilt"] += 1

    con.commit()
    con.close()
    return stats


def main() -> int:
    stats = repair()
    print(json.dumps({"status": "ok", "repairs": stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
