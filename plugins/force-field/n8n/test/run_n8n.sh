#!/usr/bin/env bash
# n8n reference-enforcement tests. Run from anywhere:  bash plugins/force-field/n8n/test/run_n8n.sh
# Needs node and python3 (PyYAML for the differential and workflow tests; without it those cases SKIP).
set -u
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo "FAIL  node not found"; exit 1; }
PY=$(command -v python3 || command -v python)
[ -n "$PY" ] || { echo "FAIL  no Python 3"; exit 1; }
"$PY" test_n8n.py
