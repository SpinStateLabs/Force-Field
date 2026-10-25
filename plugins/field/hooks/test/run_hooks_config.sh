#!/usr/bin/env bash
# hooks.json configuration tests (ADR-0081). Run from anywhere:  bash hooks/test/run_hooks_config.sh
# The gate hook must fail closed: "onFailure": "block" with an explicit timeout, so a gate that times out, crashes,
# cannot start or prints invalid JSON blocks the tool call (Claude Code 2.1.295 and later) instead of letting it
# through. Static: parses hooks.json, no Claude Code needed. The live proof on a real build is run_timeout_live.sh,
# which is not in run_all.sh or CI (it needs a logged-in claude). Prints PASS/FAIL per case; exits non-zero on a FAIL.
set -u
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
[ -n "$PY" ] || { echo "FAIL  no Python 3 on this machine"; exit 1; }
"$PY" test_hooks_config.py
