#!/usr/bin/env python3
"""
run_pipeline.py — Task 3 end-to-end driver.

Runs every stage in order against a fresh DB and prints a single summary.

    python3 run_pipeline.py --backend mock --per-query 10 --top-n 10
"""

from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def step(label: str, cmd: list[str]) -> None:
    print(f"\n── {label} ──")
    print("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        print(f"FAILED: {label}", file=sys.stderr)
        sys.exit(r.returncode)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["serpapi", "scholarly", "mock"], default="mock")
    p.add_argument("--per-query", type=int, default=10)
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--include-edge-case", action="store_true")
    p.add_argument("--enable-scidownl", action="store_true")
    args = p.parse_args()

    py = sys.executable

    step("0. Reset DB", [py, "db_schema.py", "--reset"])
    step("1. Search", [py, "search_runner.py",
                       "--queries", "../query_results.json",
                       "--backend", args.backend,
                       "--per-query", str(args.per_query),
                       "--top-n", str(args.top_n)])
    step("2. Triage", [py, "abstract_triage.py"])
    cmd_pdf = [py, "pdf_acquirer.py"]
    if args.include_edge_case: cmd_pdf.append("--include-edge-case")
    if args.enable_scidownl:   cmd_pdf.append("--enable-scidownl")
    step("3. PDF cascade", cmd_pdf)
    step("4. PRISMA dashboard", [py, "prisma_dashboard.py"])

    print("\n✓ Pipeline complete. See data/prisma_dashboard.html")


if __name__ == "__main__":
    main()
