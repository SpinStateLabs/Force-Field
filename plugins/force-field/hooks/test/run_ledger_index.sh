#!/usr/bin/env bash
# Incremental ledger index tests (differential against the old code, sidecar attacks, complexity, concurrency).
#   bash hooks/test/run_ledger_index.sh
set -u
cd "$(dirname "$0")"
python3 test_ledger_index.py
