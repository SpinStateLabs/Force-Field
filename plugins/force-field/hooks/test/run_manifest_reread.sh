#!/usr/bin/env bash
# Manifest re-read tests. Run from anywhere:  bash hooks/test/run_manifest_reread.sh
# The gate must decide every gated call under the manifest that is on disk at that call: a manifest change takes
# effect on the next gated call, because nothing keeps a copy of the manifest between calls.
# test_manifest_reread.py rewrites the manifest in place between calls (same file, same byte length, modification
# time put back) and expects every decision to follow it: an E3 deny pattern, an E2 protected path, then an
# unparsable manifest (E0). It then runs the same calls against a mutant gate that caches the manifest by size and
# modification time, and fails unless the mutant is caught. Static in the sense that no Claude Code is needed.
# Prints PASS/FAIL per case; exits non-zero on a FAIL.
set -u
cd "$(dirname "$0")"
# first interpreter that can import PyYAML (a Windows Store python3 stub exists but cannot run anything)
PY=""; for c in python3 python; do command -v "$c" >/dev/null 2>&1 && "$c" -c 'import yaml' >/dev/null 2>&1 && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "FAIL  no Python 3 with PyYAML on this machine"; exit 1; }
"$PY" test_manifest_reread.py
