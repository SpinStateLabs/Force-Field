#!/usr/bin/env bash
# E3 policy-driven verdict tests (ADR-0071). Run from anywhere:  bash hooks/test/run_e3_policy.sh
# Opt-in key enforcement.irreversible_actions.deny_patterns_verdict: deny | policy (default deny).
#   deny   -> an E3 match is always denied (field <=1.2 behaviour).
#   policy -> the match follows enforcement.irreversible_action_policy:
#             forbid -> deny; require_human_approval -> permissionDecision "ask"; allow_with_ledger -> allow + ledger.
# "ask" is only emitted for a permission_mode that was live-tested to show a prompt; anything else is denied.
# Prints PASS/FAIL per case and exits non-zero if any case fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"; G="$HERE/../field-gate.py"; L="$HERE/../field-gate.sh"; V="$HERE/../verify-ledger.py"
PY=$(command -v python3 || command -v python)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
expect() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; fail=1; fi; }
has() { case $2 in *"$3"*) expect "$1" y y ;; *) expect "$1" y n; echo "      output was: $2" ;; esac; }

# project <name> <verdict-or-"-"> <policy-or-"-"> [extra python on the manifest dict, as statements on d]
project() {
  local dir="$T/$1"; mkdir -p "$dir"
  "$PY" - "$HERE/field-manifest.yaml" "$dir/field-manifest.yaml" "$2" "$3" "${4:-}" <<'EOF'
import sys, yaml
src, dst, verdict, policy, extra = sys.argv[1:6]
d = yaml.safe_load(open(src))
ia = d["enforcement"]["irreversible_actions"]
ia["session_written_exec"] = "allow"
if verdict != "-":
    ia["deny_patterns_verdict"] = verdict
if policy == "DELETE":
    d["enforcement"].pop("irreversible_action_policy", None)
elif policy != "-":
    d["enforcement"]["irreversible_action_policy"] = policy
if extra:
    exec(extra)
yaml.safe_dump(d, open(dst, "w"), sort_keys=False)
EOF
  printf %s "$dir"
}
# call <project-dir> <session> <tool> <command> [permission_mode|NONE] -> "exit|stdout"
call() {
  local mode="${5-default}" out rc
  out=$("$PY" -c '
import json,sys
d={"session_id":sys.argv[1],"tool_name":sys.argv[2],"tool_input":{"command":sys.argv[3]}}
if sys.argv[4]!="NONE": d["permission_mode"]=sys.argv[4]
print(json.dumps(d))' "$2" "$3" "$4" "$mode" | CLAUDE_PROJECT_DIR="$1" "$PY" "$G" 2>/dev/null); rc=$?
  printf '%s|%s' "$rc" "$out"
}
last() { tail -n 1 "$1/.claude/state/field-ledger.jsonl" | "$PY" -c 'import sys,json;r=json.loads(sys.stdin.read());print(r.get("decision"),r.get("rule"))'; }
ASK='"permissionDecision": "ask"'
BAD='rm -rf build'

# 1. default behaviour is unchanged: no key, and every policy value, denies E3
for pol in forbid require_human_approval allow_with_ledger; do
  P=$(project "nokey-$pol" - "$pol"); r=$(call "$P" s1 Bash "$BAD")
  expect "no key + $pol -> deny" 2 "${r%%|*}"; has "no key + $pol -> E3 in reason" "$r" '[E3]'
  P=$(project "deny-$pol" deny "$pol"); r=$(call "$P" s1 Bash "$BAD")
  expect "verdict deny + $pol -> deny" 2 "${r%%|*}"
done

# 2. verdict policy
P=$(project p-forbid policy forbid); r=$(call "$P" s1 Bash "$BAD")
expect "policy + forbid -> deny" 2 "${r%%|*}"; expect "policy + forbid -> ledger deny E3" "deny E3" "$(last "$P")"

P=$(project p-ask policy require_human_approval); r=$(call "$P" s1 Bash "$BAD")
expect "policy + require_human_approval -> exit 0 (ask)" 0 "${r%%|*}"
has "policy + require_human_approval -> permissionDecision ask" "$r" "$ASK"
has "ask reason names the rule" "$r" '[E3]'
expect "ask is recorded in the ledger" "ask E3-policy" "$(last "$P")"
expect "ask ledger verifies" 0 "$("$PY" "$V" "$P/.claude/state/field-ledger.jsonl" >/dev/null; echo $?)"
r=$(call "$P" s1 Bash "ls -la"); expect "non-matching command still plain allow (exit 0)" 0 "${r%%|*}"
case ${r#*|} in *ask*) expect "non-matching command emits no ask" y n ;; *) expect "non-matching command emits no ask" y y ;; esac
expect "non-matching command ledger allow" "allow None" "$(last "$P")"

P=$(project p-allow policy allow_with_ledger); r=$(call "$P" s1 Bash "$BAD")
expect "policy + allow_with_ledger -> exit 0" 0 "${r%%|*}"
case ${r#*|} in *ask*|*deny*) expect "allow_with_ledger emits no verdict JSON" y n ;; *) expect "allow_with_ledger emits no verdict JSON" y y ;; esac
expect "allow_with_ledger ledger record" "allow E3-allowed" "$(last "$P")"

# 3. ask only where a prompt was live-tested; headless or unknown host -> deny, never allow
P=$(project p-modes policy require_human_approval)
for m in default acceptEdits auto dontAsk bypassPermissions; do
  r=$(call "$P" s1 Bash "$BAD" "$m"); expect "ask in permission_mode $m" 0 "${r%%|*}"; has "ask json in $m" "$r" "$ASK"
done
for m in NONE bogus ""; do
  r=$(call "$P" s1 Bash "$BAD" "$m"); expect "permission_mode '$m' -> deny, never allow" 2 "${r%%|*}"
  has "permission_mode '$m' deny names E3" "$r" '[E3]'
done

# 4. fail closed on a misconfigured key or policy
P=$(project p-badverdict maybe forbid); r=$(call "$P" s1 Bash "$BAD"); expect "bad deny_patterns_verdict -> E0 deny" 2 "${r%%|*}"; has "bad verdict E0" "$r" '[E0]'
r=$(call "$P" s1 Bash "ls"); expect "bad deny_patterns_verdict also denies a harmless shell call" 2 "${r%%|*}"
P=$(project p-badpol policy bogus); r=$(call "$P" s1 Bash "$BAD"); expect "policy + invalid policy -> E0 deny" 2 "${r%%|*}"; has "invalid policy E0" "$r" '[E0]'
P=$(project p-nopol policy DELETE); r=$(call "$P" s1 Bash "$BAD"); expect "policy + missing policy -> E0 deny" 2 "${r%%|*}"
P=$(project p-nopol-nomatch policy bogus); r=$(call "$P" s1 Bash "ls"); expect "policy + invalid policy, no match -> allow (E0 only on a match)" 0 "${r%%|*}"

# 5. ask never overrides another rule: E5, E4, E2, E1 still deny
P=$(project p-e5 policy require_human_approval 'd["enforcement"]["irreversible_actions"]["session_written_exec"]="deny"; d["enforcement"]["irreversible_actions"]["session_written_exec_allow"]=[]')
printf '{"session_id":"s5","tool_name":"Write","tool_input":{"file_path":"x.sh","content":"echo"},"permission_mode":"default"}' | CLAUDE_PROJECT_DIR="$P" "$PY" "$G" >/dev/null 2>&1
r=$(call "$P" s5 Bash "./x.sh && rm -rf build"); expect "E3 ask + E5 session-written exec -> deny" 2 "${r%%|*}"; has "E5 wins over ask" "$r" '[E5]'
P=$(project p-e4 policy require_human_approval 'd["enforcement"]["rate_limits"]=[{"action":"tool_call","max":2,"period":"session"}]')
r1=$(call "$P" s4 Bash "$BAD"); r2=$(call "$P" s4 Bash "$BAD"); r3=$(call "$P" s4 Bash "$BAD")
expect "ask #1 and #2 within budget" "0 0" "${r1%%|*} ${r2%%|*}"; expect "ask #3 over budget -> deny" 2 "${r3%%|*}"; has "E4 wins over ask" "$r3" '[E4]'
P=$(project p-e2 policy require_human_approval)
r=$(call "$P" s1 Bash "rm -rf build && echo x > field-manifest.yaml"); expect "E3 ask + write to the manifest -> deny" 2 "${r%%|*}"; has "E2 wins over ask" "$r" '[E2]'
mkdir -p "$P/.claude/state"; touch "$P/.claude/state/KILL"
r=$(call "$P" s1 Bash "$BAD"); expect "kill switch beats ask" 2 "${r%%|*}"; has "E1 wins over ask" "$r" '[E1]'

# 6. PowerShell is matched case-insensitively and follows the same verdict; non-shell tools are not E3
P=$(project p-ps policy require_human_approval)
r=$(call "$P" s1 PowerShell "remove-item x -recurse"); expect "PowerShell E3 match + policy -> ask" 0 "${r%%|*}"; has "PowerShell ask" "$r" "$ASK"
r=$(printf '{"session_id":"s1","tool_name":"mcp__x__run","tool_input":{"command":"rm -rf build"},"permission_mode":"default"}' | CLAUDE_PROJECT_DIR="$P" "$PY" "$G" 2>/dev/null); expect "non-shell tool: no E3 (unchanged)" 0 "$?"

# 7. the launcher passes the ask verdict through untouched
P=$(project p-launch policy require_human_approval)
out=$(printf '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"rm -rf build"},"permission_mode":"default"}' | CLAUDE_PROJECT_DIR="$P" sh "$L" 2>/dev/null); rc=$?
expect "launcher: ask -> exit 0" 0 "$rc"; has "launcher: ask JSON on stdout" "$out" "$ASK"

# 8. a stdout that cannot be written must not turn an ask into a silent allow
P=$(project p-closed policy require_human_approval)
printf '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"rm -rf build"},"permission_mode":"default"}' | CLAUDE_PROJECT_DIR="$P" "$PY" "$G" >&- 2>/dev/null; rc=$?
expect "ask with closed stdout -> exit 2 (deny), not 0" 2 "$rc"

if [ "$fail" = 0 ]; then echo "ALL E3 POLICY TESTS PASSED"; else echo "E3 POLICY TESTS FAILED"; exit 1; fi
