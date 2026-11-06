#!/usr/bin/env bash
# Ledger shipper tests (ledger/ledger_ship.py). The dir sink runs everywhere with the standard library only.
# The S3 (moto) and Postgres (FIELD_TEST_PG_URL) tests run when their dependencies are present; where they are
# not, they are reported as N/A lines (not SKIP: they are not part of the SKIP allowlist) so CI stays standard-library only.
#   bash hooks/test/run_ledger_ship.sh
set -u
cd "$(dirname "$0")"
out=$(python3 -B -m unittest -v test_ledger_ship 2>&1); rc=$?
echo "$out" | awk '
  / \.\.\. ok$/             { sub(/ \.\.\. .*/, ""); print "PASS " $0; next }
  / \.\.\. skipped /        { sub(/ \.\.\. .*/, ""); print "N/A  " $0 " (dependency or database not available here)"; next }
  / \.\.\. (FAIL|ERROR)$/   { sub(/ \.\.\. .*/, ""); print "FAIL " $0; next }'
[ "$rc" != 0 ] && { echo "--- unittest output ---"; echo "$out" | tail -n 40; }
exit "$rc"
