#!/usr/bin/env bash
# Pre-commit conformance gate for the AF artifact catalog.
# Install:  ln -sf ../../scripts/hooks/pre-commit-artifact-conformance.sh .git/hooks/pre-commit
set -e
cd "$(git rev-parse --show-toplevel)"
# FIXED 2026-08-03 -- THIS EXACT PAIR OF LINES DELETED 77 REPO-ROOT FILES IN Article_Eater, TWICE.
# This repo was ARMED with the identical defect and had not fired yet. It was found by a sweep only
# because the Article_Eater incident record asserted that Article_Finder "carries the same pattern
# with an equally valid template" -- an assertion made without testing it, and FALSE.
#
# BSD/macOS mktemp substitutes only TRAILING X's. With ".db" after them the template is returned
# UNCHANGED, so this was never a temporary name: it is a fixed constant path shared by every run and
# every agent. Once it exists, mktemp FAILS, $(...) yields the EMPTY STRING, and the trap below
# expands to `rm -f ""*` == `rm -f *` -- with the working directory set to the repo root by line 5.
# Files are destroyed; directories survive only because rm has no -r.
# Full account: _control/llm_cheating_corpus/cases/CASE-031_exonerating_test_contained_the_evidence.md
#
# Three independent guards, because one was demonstrably not enough:
#   1. X's at the END of the template, so substitution actually happens
#   2. an emptiness check that exits BEFORE the trap can fire
#   3. ${VAR:?} in the trap -- bash refuses to expand empty rather than globbing
export PYTHONPATH=.
ARTIFACT_CATALOG_DB="$(mktemp -u /tmp/precommit_af_catalog.XXXXXX).db"
if [ -z "$ARTIFACT_CATALOG_DB" ] || [ "$ARTIFACT_CATALOG_DB" = ".db" ]; then
  echo "FATAL: mktemp produced no path. Refusing to continue -- an empty path here becomes 'rm *'." >&2
  exit 1
fi
export ARTIFACT_CATALOG_DB
trap 'rm -f "${ARTIFACT_CATALOG_DB:?refusing to rm with an empty variable}"*' EXIT

python3 scripts/artifact_catalog.py crawl >/dev/null 2>&1

if ! python3 scripts/artifact_catalog.py doctor; then
  echo "BLOCKED: artifact-catalog invariants violated. Run 'python3 scripts/artifact_catalog.py doctor'."
  exit 1
fi

staged_added="$(git diff --cached --name-only --diff-filter=A)"
if echo "$staged_added" | grep -qiE '\.db$'; then
  echo "BLOCKED: a .db file is staged. Databases are referenced by the catalog, not committed (norm 4)."
  exit 1
fi
echo "artifact conformance: OK"

python3 /Users/davidusa/REPOS/_control_worktrees/codex-fsm-governance-clean/governance/check_contract_fsms.py \
  --repo "$(git rev-parse --show-toplevel)" \
  --repo-key Article_Finder_v3_2_3 \
  --registry /Users/davidusa/REPOS/_control_worktrees/codex-fsm-governance-clean/governance/contract_fsm_registry.json
