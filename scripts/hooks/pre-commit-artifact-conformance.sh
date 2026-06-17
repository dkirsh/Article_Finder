#!/usr/bin/env bash
# Pre-commit conformance gate for the AF artifact catalog.
# Install:  ln -sf ../../scripts/hooks/pre-commit-artifact-conformance.sh .git/hooks/pre-commit
set -e
cd "$(git rev-parse --show-toplevel)"
export PYTHONPATH=. ARTIFACT_CATALOG_DB="$(mktemp -u /tmp/precommit_af_catalog.XXXX.db)"
trap 'rm -f "$ARTIFACT_CATALOG_DB"*' EXIT

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
