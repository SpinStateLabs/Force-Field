#!/usr/bin/env bash
# FIELD x FORCE composition (SessionStart hook) tests. bash hooks/test/run_compose.sh
# Prints PASS/FAIL per case; exits non-zero on a FAIL. The hook must only ever add context and fail open.
set -u
cd "$(dirname "$0")"
HOOKS="$PWD/.."
fail=0
ok()  { echo "PASS  $1"; }
bad() { echo "FAIL  $1"; fail=1; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

run() { # dir [env...]; stdin from $IN
  ( cd "$1" && shift && env CLAUDE_PROJECT_DIR= FIELD_MANIFEST= "$@" sh "$HOOKS/field-compose.sh" <<< "${IN:-{\}}" ); }
mk() { mkdir -p "$T/$1"; printf '%s\n' "$2" > "$T/$1/field-manifest.yaml"; }

mk analysis $'agent: x\nruntime_protocol:\n  name: FORCE\n  version: "1.0"\n  preset: analysis'
mk draft    $'runtime_protocol:\n  name: FORCE\n  preset: draft'
mk audit    $'runtime_protocol:\n  name: FORCE\n  preset: audit'
mk badpre   $'runtime_protocol:\n  name: FORCE\n  preset: nonsense'
mk other    $'runtime_protocol:\n  name: OTHER\n  preset: analysis'
mk none     $'agent: x'
mk garbage  $'runtime_protocol: [unclosed'
mkdir -p "$T/nomanifest"

out=$(run "$T/analysis"); rc=$?
[ $rc = 0 ] && ok "analysis: exit 0" || bad "analysis: exit $rc"
echo "$out" | python3 -c 'import sys,json;d=json.load(sys.stdin)["hookSpecificOutput"];assert d["hookEventName"]=="SessionStart";c=d["additionalContext"];assert all(("[%s]"%l) in c for l in "FORCE") and "OUTPUT RULES" in c' 2>/dev/null \
  && ok "analysis: valid SessionStart JSON with F,O,R,C,E blocks + output rules" || bad "analysis: output not as expected"

out=$(run "$T/draft"); c=$(echo "$out" | python3 -c 'import sys,json;print(json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"])' 2>/dev/null)
{ echo "$c" | grep -q '\[F\]' && echo "$c" | grep -q '\[C\]' && ! echo "$c" | grep -q '\[O\]\|\[R\]\|\[E\]'; } && ok "draft: only F and C" || bad "draft: wrong components"

out=$(run "$T/audit"); c=$(echo "$out" | python3 -c 'import sys,json;print(json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"])' 2>/dev/null)
{ echo "$c" | grep -q '\[R\]' && ! echo "$c" | grep -q '\[O\]'; } && ok "audit: F,R,C,E without O" || bad "audit: wrong components"

for d in badpre other none garbage nomanifest; do
  out=$(run "$T/$d" 2>/dev/null); rc=$?
  { [ $rc = 0 ] && [ -z "$out" ]; } && ok "$d: exit 0, nothing injected" || bad "$d: rc=$rc out=${out:0:60}"
done

out=$(IN='not json' run "$T/analysis"); rc=$?
{ [ $rc = 0 ] && [ -n "$out" ]; } && ok "bad hook input still injects (cwd fallback), exit 0" || bad "bad hook input: rc=$rc"

out=$(run "$T/nomanifest" FIELD_MANIFEST="$T/draft/field-manifest.yaml")
echo "$out" | grep -q 'preset `draft`' && ok "FIELD_MANIFEST absolute path honoured" || bad "FIELD_MANIFEST not honoured"

out=$(cd "$T/analysis" && PATH=/nonexistent /bin/sh "$HOOKS/field-compose.sh" <<< "{}" 2>/dev/null); rc=$?
{ [ $rc = 0 ] && [ -z "$out" ]; } && ok "no Python: exit 0, nothing injected" || bad "no Python: rc=$rc"

n=$(tr -cd '\r' < "$HOOKS/field-compose.sh" | wc -c | tr -d ' ')
[ "$n" = 0 ] && ok "field-compose.sh has no carriage return" || bad "field-compose.sh has CR"

[ $fail = 0 ] && echo "ALL COMPOSE TESTS PASSED" || { echo "COMPOSE TESTS FAILED"; exit 1; }
