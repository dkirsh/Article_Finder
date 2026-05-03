#!/usr/bin/env python3
"""
run_pipeline.py — Task 3 end-to-end driver.

Runs every stage in order against a fresh DB:

    0. reset DB
    1. search_runner.py     (Stage 1 candidate harvest)
    2. abstract_triage.py   (Stage 1 metadata screen pass)
    3. abstract_collector.py(Stage 2A — survivors of Stage 1 only)
    4. abstract_triage.py   (Stage 2B — classifier decision)
    5. pdf_acquirer.py      (Stage 3 — only ACCEPT rows)
    6. prisma_dashboard.py
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent


def step(label: str, cmd: list[str]) -> None:
    print(f"\n── {label} ──")
    print("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        print(f"FAILED: {label}", file=sys.stderr); sys.exit(r.returncode)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["serpapi","scholarly","paperscraper","mock"],
                   default="mock")
    p.add_argument("--per-query", type=int, default=10)
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--enable-network", action="store_true",
                   help="Allow real S2/CrossRef/PubMed/OpenAlex calls in collector")
    p.add_argument("--enable-scidownl", action="store_true")
    p.add_argument("--voi-threshold", type=float, default=0.50)
    args = p.parse_args()
    py = sys.executable

    step("0. Reset DB", [py, "db_schema.py", "--reset"])
    step("1. Search", [py, "search_runner.py",
                       "--queries", "../query_results.json",
                       "--backend", args.backend,
                       "--per-query", str(args.per_query),
                       "--top-n", str(args.top_n)])
    step("2. Triage Stage 1 (metadata screen)",
         [py, "abstract_triage.py", "--voi-threshold", str(args.voi_threshold)])
    cmd_collect = [py, "abstract_collector.py"]
    if args.enable_network: cmd_collect.append("--enable-network")
    step("3. Abstract collection (Stage 2A)", cmd_collect)
    step("4. Triage Stage 2B (decision)",
         [py, "abstract_triage.py", "--voi-threshold", str(args.voi_threshold)])
    cmd_pdf = [py, "pdf_acquirer.py"]
    if args.enable_scidownl: cmd_pdf.append("--enable-scidownl")
    step("5. PDF cascade (Stage 3)", cmd_pdf)
    step("6. PRISMA dashboard", [py, "prisma_dashboard.py"])

    print("\n✓ Pipeline complete. See task3/data/prisma_dashboard.html")


if __name__ == "__main__":
    main()
