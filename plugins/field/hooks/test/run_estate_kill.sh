#!/usr/bin/env bash
# Estate kill sentinel tests (ADR-0072). Run from anywhere:  bash hooks/test/run_estate_kill.sh
# enforcement.kill_switch.local_sentinel names a local file a HOST WATCHER (field-platform tools/estate_kill_watcher.py)
# creates when the estate kills the agent and removes on revive; E1 denies every gated call while it exists.
# enforcement.kill_switch.sentinel_max_age_s (opt-in) also denies when the watcher's liveness stamp
# (<local_sentinel>.alive) is missing or older than N seconds, so a dead watcher cannot silently drop a kill.
# The gate makes no network call. Prints PASS/FAIL per case and exits non-zero if any case fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"; G="$HERE/../field-gate.py"; L="$HERE/../field-gate.sh"; V="$HERE/../verify-ledger.py"
PY=$(command -v python3 || command -v python)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
expect() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; fail=1; fi; }
has() { case $2 in *"$3"*) expect "$1" y y ;; *) expect "$1" y n; echo "      output was: $2" ;; esac; }

# project <name> <method> <endpoint> <local_sentinel-or-"-"> <max_age-or-"-"> -> dir
project() {
  local dir="$T/$1"; mkdir -p "$dir"
  "$PY" - "$HERE/field-manifest.yaml" "$dir/field-manifest.yaml" "$2" "$3" "$4" "$5" <<'EOF'
import sys, yaml
src, dst, method, endpoint, sentinel, max_age = sys.argv[1:7]
d = yaml.safe_load(open(src))
ks = d["enforcement"]["kill_switch"]
ks["method"], ks["endpoint"] = method, endpoint
if sentinel != "-":
    ks["local_sentinel"] = sentinel
if max_age != "-":
    ks["sentinel_max_age_s"] = yaml.safe_load(max_age)
d["enforcement"]["irreversible_actions"]["session_written_exec"] = "allow"
yaml.safe_dump(d, open(dst, "w"), sort_keys=False)
EOF
  printf %s "$dir"
}
# call <dir> <tool> <input-json> -> "exit|stdout"
call() {
  local out rc
  out=$(printf '{"session_id":"e1","tool_name":"%s","tool_input":%s,"permission_mode":"default"}' "$2" "$3" | CLAUDE_PROJECT_DIR="$1" "$PY" "$G" 2>/dev/null); rc=$?
  printf '%s|%s' "$rc" "$out"
}
bash_() { call "$1" Bash "$("$PY" -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$2")"; }
last() { tail -n 1 "$1/.claude/state/field-ledger.jsonl" | "$PY" -c 'import sys,json;r=json.loads(sys.stdin.read());print(r.get("decision"),r.get("rule"))'; }
# age <file> <seconds-ago>  (portable: python sets the mtime)
age() { "$PY" -c 'import os,sys,time;t=time.time()-float(sys.argv[2]);os.utime(sys.argv[1],(t,t))' "$1" "$2"; }

# 1. no key: an HTTP-method manifest still gets only the default sentinel (unchanged)
P=$(project plain "HTTP POST" "http://10.0.0.62:18080/killswitch/kill/x" - -)
r=$(bash_ "$P" "ls"); expect "no local_sentinel: allow" 0 "${r%%|*}"
mkdir -p "$P/estate"; : > "$P/estate/KILL"
r=$(bash_ "$P" "ls"); expect "an unnamed estate/KILL file means nothing" 0 "${r%%|*}"
mkdir -p "$P/.claude/state"; : > "$P/.claude/state/KILL"
r=$(bash_ "$P" "ls"); expect "default sentinel still halts" 2 "${r%%|*}"

# 2. local_sentinel with an HTTP kill method: the watcher's file halts, its removal revives
P=$(project est "HTTP POST" "http://10.0.0.62:18080/killswitch/kill/x" "estate/ESTATE_KILL" -)
r=$(bash_ "$P" "ls"); expect "local_sentinel absent: allow" 0 "${r%%|*}"
mkdir -p "$P/estate"; printf 'field-estate-kill-watcher\n' > "$P/estate/ESTATE_KILL"
r=$(bash_ "$P" "ls"); expect "local_sentinel present: deny" 2 "${r%%|*}"; has "deny names E1" "$r" '[E1]'
has "deny names the sentinel" "$r" 'estate kill sentinel'
expect "ledger records E1" "deny E1" "$(last "$P")"
r=$(call "$P" mcp__x__do '{"a":1}'); expect "an MCP tool is halted too" 2 "${r%%|*}"
r=$(call "$P" Read '{"file_path":"x"}'); expect "ungated Read is not halted (unchanged)" 0 "${r%%|*}"
rm "$P/estate/ESTATE_KILL"
r=$(bash_ "$P" "ls"); expect "revive (sentinel removed): allow" 0 "${r%%|*}"
expect "ledger verifies" 0 "$("$PY" "$V" "$P/.claude/state/field-ledger.jsonl" >/dev/null; echo $?)"

# 3. absolute path, and method file + local_sentinel: either file halts
ABS="$T/abs-sentinel/KILL"; mkdir -p "$(dirname "$ABS")"
P=$(project abs "HTTP POST" "http://x/kill" "$ABS" -)
r=$(bash_ "$P" "ls"); expect "absolute local_sentinel absent: allow" 0 "${r%%|*}"
: > "$ABS"; r=$(bash_ "$P" "ls"); expect "absolute local_sentinel present: deny" 2 "${r%%|*}"; rm -f "$ABS"
P=$(project both file ".claude/state/KILL" "estate/ESTATE_KILL" -)
mkdir -p "$P/estate" "$P/.claude/state"; : > "$P/estate/ESTATE_KILL"
r=$(bash_ "$P" "ls"); expect "method file + local_sentinel: the estate file halts" 2 "${r%%|*}"
rm "$P/estate/ESTATE_KILL"; : > "$P/.claude/state/KILL"
r=$(bash_ "$P" "ls"); expect "method file + local_sentinel: the endpoint file halts" 2 "${r%%|*}"

# 4. opt-in staleness: a dead watcher must not silently drop a kill
P=$(project stale "HTTP POST" "http://x/kill" "estate/ESTATE_KILL" 30)
r=$(bash_ "$P" "ls"); expect "sentinel_max_age_s on, no stamp: deny" 2 "${r%%|*}"; has "stale deny names E1" "$r" '[E1]'; has "says heartbeat" "$r" 'heartbeat'
mkdir -p "$P/estate"; : > "$P/estate/ESTATE_KILL.alive"
r=$(bash_ "$P" "ls"); expect "fresh stamp: allow" 0 "${r%%|*}"
age "$P/estate/ESTATE_KILL.alive" 10; r=$(bash_ "$P" "ls"); expect "stamp 10 s old, limit 30: allow" 0 "${r%%|*}"
age "$P/estate/ESTATE_KILL.alive" 31; r=$(bash_ "$P" "ls"); expect "stamp 31 s old, limit 30: deny" 2 "${r%%|*}"
age "$P/estate/ESTATE_KILL.alive" -3600; r=$(bash_ "$P" "ls"); expect "stamp dated in the future: deny" 2 "${r%%|*}"
age "$P/estate/ESTATE_KILL.alive" 0; : > "$P/estate/ESTATE_KILL"
r=$(bash_ "$P" "ls"); expect "fresh stamp but sentinel present: deny" 2 "${r%%|*}"
P2=$(project nostale "HTTP POST" "http://x/kill" "estate/ESTATE_KILL" -)
r=$(bash_ "$P2" "ls"); expect "staleness is opt-in: no max age, no stamp: allow" 0 "${r%%|*}"

# 5. fail closed on a misconfigured key
P=$(project bad1 "HTTP POST" "http://x/kill" - 30);                 r=$(bash_ "$P" "ls"); expect "sentinel_max_age_s without local_sentinel -> E0" 2 "${r%%|*}"; has "E0" "$r" '[E0]'
P=$(project bad2 "HTTP POST" "http://x/kill" "NOSEP" -);             r=$(bash_ "$P" "ls"); expect "local_sentinel not a path -> E0" 2 "${r%%|*}"; has "E0 path" "$r" '[E0]'
for bad in 0 -5 "'x'" true 1.5; do
  P=$(project "badage$RANDOM" "HTTP POST" "http://x/kill" "estate/K" "$bad"); r=$(bash_ "$P" "ls")
  expect "sentinel_max_age_s=$bad -> E0" 2 "${r%%|*}"
done

# 6. the agent cannot write, delete or backdate the sentinel or the stamp (E2), wherever they live
P=$(project e2 "HTTP POST" "http://x/kill" "estate/ESTATE_KILL" 30)
mkdir -p "$P/estate"; : > "$P/estate/ESTATE_KILL.alive"
for c in 'touch estate/ESTATE_KILL.alive' 'rm estate/ESTATE_KILL.alive' 'echo x > estate/ESTATE_KILL.alive' 'cp /dev/null estate/ESTATE_KILL.alive' \
         'touch -d "1 hour ago" estate/ESTATE_KILL.alive' 'mv estate/ESTATE_KILL.alive /tmp/x' 'echo x > estate/ESTATE_KILL' 'rm -f estate/ESTATE_KILL'; do
  r=$(bash_ "$P" "$c"); expect "E2 deny: $c" 2 "${r%%|*}"; has "E2 rule: $c" "$r" '[E2]'
done
r=$(call "$P" Write '{"file_path":"estate/ESTATE_KILL.alive","content":"x"}'); expect "E2 deny: Write the stamp" 2 "${r%%|*}"
r=$(call "$P" Edit '{"file_path":"estate/ESTATE_KILL","old_string":"a","new_string":"b"}'); expect "E2 deny: Edit the sentinel" 2 "${r%%|*}"
r=$(bash_ "$P" "ls estate"); expect "reading the estate dir is still fine" 0 "${r%%|*}"
P=$(project e2s "HTTP POST" "http://x/kill" ".claude/state/ESTATE_KILL" 30)
mkdir -p "$P/.claude/state"; : > "$P/.claude/state/ESTATE_KILL.alive"
r=$(bash_ "$P" "touch .claude/state/ESTATE_KILL.alive"); expect "E2 deny: stamp inside the state dir" 2 "${r%%|*}"
r=$(bash_ "$P" "rm .claude/state/ESTATE_KILL"); expect "E2 deny: sentinel inside the state dir" 2 "${r%%|*}"

# 7. the launcher passes the verdict through
P=$(project launch "HTTP POST" "http://x/kill" "estate/ESTATE_KILL" -); mkdir -p "$P/estate"; : > "$P/estate/ESTATE_KILL"
out=$(printf '{"session_id":"e1","tool_name":"Bash","tool_input":{"command":"ls"}}' | CLAUDE_PROJECT_DIR="$P" sh "$L" 2>/dev/null); rc=$?
expect "launcher: estate kill -> exit 2" 2 "$rc"; has "launcher: E1 JSON" "$out" '[E1]'

if [ "$fail" = 0 ]; then echo "ALL ESTATE KILL TESTS PASSED"; else echo "ESTATE KILL TESTS FAILED"; exit 1; fi
