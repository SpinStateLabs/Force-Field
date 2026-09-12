#!/usr/bin/env bash
# FIELD Enforcement Gate smoke test. Run from anywhere:  bash hooks/test/run.sh
# Uses the fixture field-manifest.yaml in this directory; state goes under ./.claude/ here.
# Expected: allow (exit=0) / DENY E3 / DENY E2 / DENY E1 (exit=2 each), then LEDGER INTACT.
set -u
cd "$(dirname "$0")"
G=../field-gate.py
rm -rf .claude
export CLAUDE_PROJECT_DIR="$PWD"
echo '{"session_id":"t1","tool_name":"Bash","tool_input":{"command":"ls -la"}}' | python3 $G; echo "exit=$?"
echo '{"session_id":"t1","tool_name":"Bash","tool_input":{"command":"rm -rf build"}}' | python3 $G; echo "exit=$?"
echo '{"session_id":"t1","tool_name":"Edit","tool_input":{"file_path":"/x/.claude/settings.json"}}' | python3 $G; echo "exit=$?"
mkdir -p .claude/state && touch .claude/state/KILL
echo '{"session_id":"t1","tool_name":"Bash","tool_input":{"command":"echo hi"}}' | python3 $G; echo "exit=$?"
rm .claude/state/KILL
python3 ../verify-ledger.py
