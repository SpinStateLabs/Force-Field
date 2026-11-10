#!/usr/bin/env bash
# Ledger record provenance tests (gate 1.6.0): manifest digest, gate version, phase, one key set, ledgered E0 denies.
#   bash hooks/test/run_provenance.sh
set -u
cd "$(dirname "$0")"
python3 test_record_provenance.py
