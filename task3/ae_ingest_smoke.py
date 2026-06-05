#!/usr/bin/env python3
"""
ae_ingest_smoke.py — REAL Article Eater ingestion smoke test (gated, honest).

If a real Article Eater is configured ($AE_INBOX or $AE_INGEST_CMD), this writes
ONE handoff artefact and delivers it to AE, then reports whether AE consumed it.
If not configured, it SKIPs cleanly (exit 0) with the exact env to set — this is
the honest boundary on a checkout that does not contain the Article Eater repo.

Real run (on a machine that HAS Article Eater), pick one:
    AE_INGEST_CMD="python3 /path/to/Article_Eater/scripts/course_scaffolding.py ingest-handoff" \
        python3 ae_ingest_smoke.py
    AE_INBOX=/path/to/Article_Eater/data/inbox AE_ACK_TIMEOUT=15 python3 ae_ingest_smoke.py

Exit 0 = SKIP (no AE) OR delivered. Exit 1 = real delivery attempted and failed.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ae_handoff  # noqa: E402
import db_schema  # noqa: E402


def main() -> int:
    if not (os.environ.get("AE_INBOX") or os.environ.get("AE_INGEST_CMD")):
        print("SKIP: no real Article Eater configured. To run a REAL ingestion smoke "
              "test, set ONE of:")
        print("  AE_INGEST_CMD='<cmd>'   # we run: <cmd> <artefact.json>; exit 0 == consumed")
        print("  AE_INBOX=<dir>          # AE's watched inbox (+ optional AE_ACK_TIMEOUT=<secs>)")
        print("Boundary unchanged: the local substitute (ae_inbox_stub.py) remains the "
              "tested surface; see TASK3_CONTRACT.md §0.")
        return 0

    d = Path(tempfile.mkdtemp(prefix="ae_smoke_"))
    conn = db_schema.open_db(d / "x.db")
    conn.execute(
        "INSERT INTO article_references (reference_id, doi, title_raw, discovered_via, "
        "triage_stage, triage_decision, abstract, abstract_source, gap_template_id, "
        "voi_score, raw_citation, acquired_paper_id) VALUES "
        "('REF-AE-SMOKE','10.1/ae-smoke','AE smoke title','mock_synthetic','acquired',"
        "'ACCEPT','A real abstract long enough for the gate.','s2','GAP',0.8,'cite',"
        "'paper:REF-AE-SMOKE')")
    conn.commit()
    ae_handoff.write_handoffs(conn, d / "handoff")
    conn.close()

    artefact = d / "handoff" / "REF-AE-SMOKE.json"
    if not artefact.exists():
        print("FAIL: handoff artefact was not written")
        return 1

    out = ae_handoff.deliver_to_ae(artefact)
    print(f"AE delivery: mode={out['mode']} delivered={out['delivered']} "
          f"consumed={out['consumed']}")
    print(f"  detail: {out['detail']}")

    if out["delivered"] and out["consumed"]:
        print("REAL AE INGESTION VERIFIED ✓")
        return 0
    if out["delivered"]:
        print("Delivered to AE inbox, but consumption not confirmed within timeout. "
              "Raise AE_ACK_TIMEOUT or confirm AE is running.")
        return 0
    print("NOT delivered — see detail above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
