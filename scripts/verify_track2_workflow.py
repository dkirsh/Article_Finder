#!/usr/bin/env python3
"""
verify_track2_workflow.py — Track 2 end-to-end chain verifier.

ONE command a grader runs to confirm the whole module does what its contracts
say — Task 1 (Contribute Page), Task 2 (gap/query), Task 3 (search -> triage ->
acquire -> HANDOFF) — with the last-mile handoff artefact asserted end to end.

It does three things:
  1. Runs the Task 1 suite (Knowledge_Atlas/data/test_pdfs/validate_task1.py)
     when the sibling fork is checked out next to this one; SKIPs with a clear
     note otherwise (the forks are separate repos).
  2. Runs the Task 2 + Task 3 suite (task3/tests_task2_task3.py).
  3. Exercises the LAST MILE directly on a fresh temp lifecycle DB:
       - seeds one ACCEPT+abstract row and one MISSING_ABSTRACT row,
       - runs ae_handoff.write_handoffs,
       - asserts: a data/handoff/<id>.json exists for the ACCEPT row, NONE for
         the MISSING_ABSTRACT row (the abstract gate), the JSON carries the full
         schema with a non-empty abstract, a second run writes nothing
         (idempotency), and a 'handed_off' lifecycle transition was logged.

Exit 0 only if every checked layer passes.

Usage:  python3 scripts/verify_track2_workflow.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AF_ROOT = Path(__file__).resolve().parent.parent          # track2/Article_Finder
TASK3 = AF_ROOT / "task3"
KA_ROOT = AF_ROOT.parent / "Knowledge_Atlas"              # sibling fork
sys.path.insert(0, str(TASK3))

results: list[tuple[str, bool]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))


def run_suite(label: str, cwd: Path, script: str) -> None:
    p = cwd / script
    if not p.exists():
        check(f"{label}: suite present", False, f"missing {p}")
        return
    r = subprocess.run([sys.executable, script], cwd=str(cwd),
                       capture_output=True, text=True)
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    check(f"{label}: {tail or 'ran'}", r.returncode == 0,
          "" if r.returncode == 0 else r.stdout[-400:])


print("=== Track 2 chain verification ===\n")
print("--- per-task suites ---")

# 1. Task 1 (sibling fork)
if KA_ROOT.exists():
    run_suite("Task 1 (Knowledge_Atlas)", KA_ROOT, "data/test_pdfs/validate_task1.py")
else:
    print(f"  SKIP  Task 1 suite — sibling fork not checked out at {KA_ROOT}")

# 2. Task 2 + 3
run_suite("Task 2+3 (Article_Finder)", TASK3, "tests_task2_task3.py")

# 3. LAST MILE — handoff end to end on a fresh temp DB
print("\n--- last mile: handoff artefact ---")
import ae_handoff  # noqa: E402
import db_schema  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="t2_verify_"))
db = tmp / "lifecycle.db"
out = tmp / "handoff"
conn = db_schema.open_db(db)


def _ins(rid: str, decision: str, abstract: str | None, doi: str) -> None:
    conn.execute(
        "INSERT INTO article_references (reference_id, doi, title_raw, discovered_via, "
        "triage_stage, triage_decision, abstract, abstract_source, gap_template_id, "
        "voi_score, raw_citation, acquired_paper_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, doi, f"Title {rid}", "mock_synthetic", "acquired", decision, abstract,
         "s2" if abstract else "none", "GAP-VERIFY-001", 0.8, f"cite {rid}",
         f"paper:{rid}" if decision == "ACCEPT" else None),
    )


_ins("REF-ACC", "ACCEPT", "A genuine abstract with more than enough length to clear the gate.", "10.1/acc")
_ins("REF-MISS", "MISSING_ABSTRACT", None, "10.1/miss")
conn.commit()

res1 = ae_handoff.write_handoffs(conn, out)
acc_file = (out / "REF-ACC.json").exists()
miss_file = (out / "REF-MISS.json").exists()
check("handoff written for ACCEPT row", acc_file and res1["written"] == ["REF-ACC"], str(res1))
check("NO handoff for MISSING_ABSTRACT row (abstract gate is real)", not miss_file)
if acc_file:
    obj = json.loads((out / "REF-ACC.json").read_text())
    check("handoff JSON has full schema + non-empty abstract",
          set(obj) == set(ae_handoff.HANDOFF_SCHEMA_FIELDS) and bool(obj["abstract"]),
          f"keys={sorted(obj)}")

res2 = ae_handoff.write_handoffs(conn, out)
check("idempotent: second run writes nothing", res2["written"] == [], str(res2))
n_log = conn.execute("SELECT COUNT(*) FROM handoff_log").fetchone()[0]
check("handoff_log has exactly 1 row (UNIQUE reference_id)", n_log == 1, f"n={n_log}")
n_tx = conn.execute(
    "SELECT COUNT(*) FROM lifecycle_transitions WHERE to_stage='handed_off'"
).fetchone()[0]
check("handed_off transition logged", n_tx == 1, f"n={n_tx}")

conn.close()
try:
    shutil.rmtree(tmp)
except Exception:
    pass

n_pass = sum(1 for _, ok in results if ok)
print(f"\n{'=' * 60}")
print(f"CHAIN: {n_pass}/{len(results)} checks passed")
print(f"{'=' * 60}")
sys.exit(0 if n_pass == len(results) else 1)
