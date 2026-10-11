#!/usr/bin/env bash
# E5 + ledger-path tests. Run from anywhere:  bash hooks/test/run_e5.sh
# Prints PASS/FAIL per case and exits non-zero if any case fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"; G="$HERE/../field-gate.py"; V="$HERE/../verify-ledger.py"
# Absolute paths as the hook sees them: Windows form under Git Bash (Claude Code passes C:/... paths).
abspath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf %s "$1"; fi; }
fail=0
call() { # session tool json-input -> prints exit code
  printf '{"session_id":"%s","tool_name":"%s","tool_input":%s}' "$1" "$2" "$3" | python3 "$G" >/dev/null 2>&1; echo $?
}
expect() { # label expected actual
  if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; fail=1; fi
}
run_suite() {
  rm -rf .claude
  export CLAUDE_PROJECT_DIR="$PWD"
  expect "write x.sh allowed"            0 "$(call t1 Write '{"file_path":"x.sh","content":"echo"}')"
  expect "write x.py allowed"            0 "$(call t1 Write '{"file_path":"'"$(abspath "$PWD")"'/x.py","content":"print()"}')"
  expect "write x.js allowed"            0 "$(call t1 Edit  '{"file_path":"./x.js","old_string":"a","new_string":"b"}')"
  expect "write approved/ok.sh allowed"  0 "$(call t1 Write '{"file_path":"approved/ok.sh","content":"echo"}')"
}
# ---- E5 on (fixture) ----
cd "$HERE"; run_suite
for c in 'bash ./x.sh' 'sh x.sh' 'source x.sh' '. ./x.sh' './x.sh' 'chmod +x x.sh && ./x.sh' \
         'bash -x x.sh' 'sudo -E bash x.sh' 'FOO=1 ./x.sh' 'python3 x.py' 'node x.js' "$(abspath "$PWD")/x.sh"; do
  expect "E5 deny: $c" 2 "$(call t1 Bash "{\"command\":\"$c\"}")"
done
# bypasses found in the pre-push security review (must all be denied)
for c in 'sudo -u root ./x.sh' 'sudo -E -H ./x.sh' 'env -u FOO ./x.sh' 'nice -n 10 ./x.sh' 'exec -a foo ./x.sh' \
         'bash -o posix x.sh' 'bash --rcfile /dev/null x.sh' 'python3 -W ignore x.py' 'python3 -X dev x.py' 'node -r fs x.js' \
         'bash -c ./x.sh' "sh -c 'bash x.sh'" 'bash < x.sh' 'cat x.sh | bash' '(./x.sh)' '{ ./x.sh; }' \
         'if ./x.sh; then :; fi' '! ./x.sh' 'echo $(./x.sh)' '2>/dev/null ./x.sh' 'timeout 5 ./x.sh' \
         'bash.exe x.sh' 'python.exe x.py' 'cp x.sh y.sh && ./y.sh'; do
  expect "E5 deny (review): $c" 2 "$(call t1 Bash "$(python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$c")")"
done
expect "E5 deny (review): quoted name" 2 "$(call t1 Bash '{"command":"bash \"x.sh\" \"a;b\""}')"
for c in 'cat x.sh' 'git add x.sh' 'ls x.sh' 'cat x.sh | grep a' 'bash ./approved/ok.sh' 'bash other.sh' 'python3 -m x' 'python3 -c pass'; do
  expect "allow: $c" 0 "$(call t1 Bash "{\"command\":\"$c\"}")"
done
expect "other session may run t1's file" 0 "$(call t2 Bash '{"command":"bash ./x.sh"}')"
# command word is a path, not a tool (second public review): a session-written file named after an
# allowlisted read-only tool must not borrow that tool's exemption; the real tool stays allowed
expect "write x3.sh allowed (t3)"            0 "$(call t3 Write '{"file_path":"x3.sh","content":"echo"}')"
for n in cat ls head tail less more wc grep rg diff stat file git sha256sum md5sum chmod echo printf test '['; do
  expect "write $n allowed (t3)"              0 "$(call t3 Write "{\"file_path\":\"$n\",\"content\":\"x\"}")"
  expect "E5 deny: ./$n (named like a read-only tool)" 2 "$(call t3 Bash "$(python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "./$n")")"
done
expect "write tools/cat allowed (t3)"        0 "$(call t3 Write '{"file_path":"tools/cat","content":"x"}')"
for c in './tools/cat' 'chmod +x git && ./git' './cat x3.sh' 'sudo ./git' "bash -c './git'" '(./git)' 'FOO=1 ./git'; do
  expect "E5 deny (read-only name): $c"       2 "$(call t3 Bash "$(python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$c")")"
done
for c in 'cat x3.sh' 'git status' 'ls' 'head -n1 x3.sh' 'git add x3.sh'; do
  expect "allow: bare '$c' although t3 wrote files named cat/git/ls" 0 "$(call t3 Bash "$(python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$c")")"
done
expect "E5 deny: ./x3.sh still denied (t3)"  2 "$(call t3 Bash '{"command":"./x3.sh"}')"
expect "other session may run t3's ./git"    0 "$(call t2 Bash '{"command":"./git"}')"
# ledger: paths logged, root-relative, no plaintext absolute path
python3 - "$HERE" "$(abspath "$HERE")" <<'PY'
import json,sys
roots=[r for r in sys.argv[1:] if r]
recs=[json.loads(l) for l in open(".claude/state/field-ledger.jsonl")]
paths=[r.get("path") for r in recs if r["tool"] in ("Write","Edit")]
blob=json.dumps(recs).replace("\\\\","/").casefold()
ok = [p.casefold() for p in paths[:4]]==["x.sh","x.py","x.js","approved/ok.sh"] and not any(r.casefold() in blob for r in roots)
print(("PASS" if ok else "FAIL")+"  ledger paths root-relative, no absolute paths:",paths[:4]); sys.exit(0 if ok else 1)
PY
[ $? -eq 0 ] || fail=1
# outside-root path is hashed
OUT="$(abspath "$(cd "$HERE/../../../.." && pwd)")/field-e5-outside.sh"
expect "write outside root allowed"     0 "$(call t1 Write '{"file_path":"'"$OUT"'","content":"x"}')"
grep -q "field-e5-outside" .claude/state/field-ledger.jsonl && { echo "FAIL  outside-root path stored in plaintext"; fail=1; } || echo "PASS  outside-root path not stored in plaintext"
grep -q '"path": "sha256:' .claude/state/field-ledger.jsonl && echo "PASS  outside-root path stored as sha256" || { echo "FAIL  no sha256 path"; fail=1; }
expect "E5 deny outside-root exec" 2 "$(call t1 Bash '{"command":"bash '"$OUT"'"}')"
# deny reason does not leak other ledger entries
out=$(printf '{"session_id":"t1","tool_name":"Bash","tool_input":{"command":"./x.sh"}}' | python3 "$G" 2>&1 >/dev/null)
case "$out" in *x.py*|*approved*|*field-ledger*) echo "FAIL  deny reason leaks: $out"; fail=1;; *) echo "PASS  deny reason names only the command token";; esac
# ledger permissions (POSIX)
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) echo "SKIP  ledger mode check (Windows)";;
  *) m=$(stat -c %a .claude/state/field-ledger.jsonl 2>/dev/null || stat -f %Lp .claude/state/field-ledger.jsonl)
     [ "$m" = "600" ] && echo "PASS  new ledger is 0600" || { echo "FAIL  ledger mode $m"; fail=1; };;
esac
# ---- all-tools coverage (field 1.2): PowerShell, MCP and other tools ----
pj() { python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }
for c in 'bash x.sh' '& .\x.sh' 'python3 x.py' 'Start-Process bash -ArgumentList x.sh' 'Get-Content x.sh | iex' 'Get-Content x.sh'; do
  expect "PowerShell E5 deny: $c" 2 "$(call t1 PowerShell "$(pj "$c")")"
done
for c in 'Get-ChildItem' 'bash approved/ok.sh' 'Write-Output hi'; do
  expect "PowerShell allow: $c" 0 "$(call t1 PowerShell "$(pj "$c")")"
done
expect "PowerShell: other session may run t1's file" 0 "$(call t2 PowerShell '{"command":"bash x.sh"}')"
expect "PowerShell E3: Remove-Item -Recurse"     2 "$(call t1 PowerShell '{"command":"Remove-Item -Recurse -Force build"}')"
expect "PowerShell E3: rm -rf via bash"          2 "$(call t1 PowerShell '{"command":"bash -c \"rm -rf build\""}')"
expect "PowerShell E2: edit manifest"            2 "$(call t1 PowerShell '{"command":"Set-Content field-manifest.yaml x"}')"
expect "PowerShell: command under another key"   2 "$(call t1 PowerShell '{"script":"bash x.sh"}')"
expect "MCP E2: write manifest"                  2 "$(call t1 mcp__fs__write_file '{"path":"field-manifest.yaml","content":"x"}')"
expect "MCP E2: nested input"                    2 "$(call t1 mcp__fs__edit '{"edits":[{"path":".claude/settings.json"}]}')"
# PowerShell evasions from the all-tools review
for c in 'bash x`.sh' "bash ‘x.sh’" 'bash “x.sh”' '& $PWD/x.sh' '& "$PWD\x.sh"' 'Start-Process -FilePath:x.sh'; do
  expect "PowerShell E5 deny (review): $c" 2 "$(call t1 PowerShell "$(pj "$c")")"
done
for c in 'Re`move-Item -Recurse build' 'Remove-Item –Recurse build' 'RM -RF build'; do
  expect "PowerShell E3 deny (review): $c" 2 "$(call t1 PowerShell "$(pj "$c")")"
done
expect "MCP E2: manifest mid-string"             2 "$(call t1 mcp__dc__start_process '{"command":"echo x > field-manifest.yaml; true"}')"
expect "MCP E2: trailing space"                  2 "$(call t1 mcp__fs__write_file '{"path":"./field-manifest.yaml ","content":"x"}')"
r=$(printf '{"session_id":"t1","tool_name":["Bash"],"tool_input":{}}' | python3 "$G" >/dev/null 2>&1; echo $?); expect "non-string tool_name -> E0 deny" 2 "$r"
expect "MCP allow: ordinary call"                0 "$(call t1 mcp__fs__write_file '{"path":"notes.txt","content":"x"}')"
grep -q '"tool": "mcp__fs__write_file"' .claude/state/field-ledger.jsonl && echo "PASS  MCP calls are ledgered" || { echo "FAIL  MCP call not ledgered"; fail=1; }
n0=$(wc -l < .claude/state/field-ledger.jsonl)
expect "Read is ungated"                         0 "$(call t1 Read '{"file_path":"field-manifest.yaml"}')"
[ "$(wc -l < .claude/state/field-ledger.jsonl)" = "$n0" ] && echo "PASS  ungated Read leaves no ledger record" || { echo "FAIL  Read was ledgered"; fail=1; }
mkdir -p .claude/state && touch .claude/state/KILL
expect "E1 kill: PowerShell denied"              2 "$(call t1 PowerShell '{"command":"Get-ChildItem"}')"
expect "E1 kill: MCP tool denied"                2 "$(call t1 mcp__fs__write_file '{"path":"notes.txt","content":"x"}')"
expect "E1 kill: WebFetch denied"                2 "$(call t1 WebFetch '{"url":"https://example.com","prompt":"x"}')"
expect "E1 kill: Read still ungated"             0 "$(call t1 Read '{"file_path":"x.sh"}')"
out=$(printf '{"session_id":"t1","tool_name":"Bash","tool_input":{"command":"ls"}}' | python3 "$G" 2>&1 >/dev/null)
case "${out,,}" in *"(.claude/state/kill)"*) echo "PASS  E1 reason names the root-relative sentinel";; *) echo "FAIL  E1 reason: $out"; fail=1;; esac
rm .claude/state/KILL
expect "E2: absolute ledger path via MCP"      2 "$(call t1 mcp__fs__write_file '{"path":"'"$(abspath "$HERE")"'/.claude/state/field-ledger.jsonl","content":"x"}')"
python3 - "$HERE" "$(abspath "$HERE")" <<'PY2'
import json,sys
roots=[r for r in sys.argv[1:] if r]
blob=open(".claude/state/field-ledger.jsonl").read().replace("\\\\","/").casefold()
bad=[r for r in roots if r.casefold() in blob]
print(("FAIL" if bad else "PASS")+"  no absolute project path anywhere in the ledger (incl. E1 reasons)"); sys.exit(1 if bad else 0)
PY2
[ $? -eq 0 ] || fail=1
# parallel calls: no false E0, every call ledgered, chain intact
n0=$(wc -l < .claude/state/field-ledger.jsonl)
for i in $(seq 1 30); do printf '{"session_id":"p1","tool_name":"mcp__x__y","tool_input":{"i":%s}}' "$i" | python3 "$G" >/dev/null 2>&1 & done; wait
n1=$(wc -l < .claude/state/field-ledger.jsonl)
[ $((n1-n0)) -eq 30 ] && echo "PASS  30 parallel calls ledgered" || { echo "FAIL  parallel calls ledgered: $((n1-n0))/30"; fail=1; }
grep -q '"session": "p1".*"decision": "deny"\|"decision": "deny".*"session": "p1"' .claude/state/field-ledger.jsonl && { echo "FAIL  parallel call denied"; fail=1; } || echo "PASS  no parallel call denied"
python3 "$V" >/dev/null && echo "PASS  ledger intact" || { echo "FAIL  ledger tampered"; fail=1; }
# fail-closed: corrupt ledger line -> E0 on Bash
echo 'not json' >> .claude/state/field-ledger.jsonl
expect "corrupt ledger -> E0 deny" 2 "$(call t1 Bash '{"command":"echo hi"}')"
# malformed hook input with a manifest present must fail closed (was an allow in 1.1)
r=$(printf 'not json' | python3 "$G" >/dev/null 2>&1; echo $?); expect "malformed hook input -> E0 deny" 2 "$r"
r=$(printf '["a"]' | python3 "$G" >/dev/null 2>&1; echo $?); expect "non-object hook input -> E0 deny" 2 "$r"
# exemption given as a string (not a list) must fail closed, not exempt everything
cp field-manifest.yaml .claude/m.bak
python3 - <<'PY'
p="field-manifest.yaml"; s=open(p).read()
s=s.replace("    session_written_exec_allow:        # E5 exemptions: root-relative path regexes\n      - '^approved/'\n","    session_written_exec_allow: '^approved/'\n")
open(p,"w").write(s)
PY
grep -q "session_written_exec_allow: '\^approved/'" field-manifest.yaml || { echo "FAIL  could not build string-exemption fixture"; fail=1; }
expect "string exemption -> E0 deny" 2 "$(call t1 Bash '{"command":"ls"}')"
cp .claude/m.bak field-manifest.yaml
# ---- E5 off: v1.1 behaviour unchanged ----
T=$(mktemp -d); sed '/session_written_exec/d; /\^approved\//d' field-manifest.yaml > "$T/field-manifest.yaml"
cd "$T"; run_suite
expect "E5 off: bash ./x.sh allowed" 0 "$(call t1 Bash '{"command":"bash ./x.sh"}')"
expect "E5 off: E3 still denies rm -rf" 2 "$(call t1 Bash '{"command":"rm -rf build"}')"
python3 "$V" >/dev/null && echo "PASS  ledger intact (E5 off)" || { echo "FAIL  ledger (E5 off)"; fail=1; }
# bad mode -> E0
python3 - <<'PY'
import re
p="field-manifest.yaml"; s=open(p).read()
s=re.sub(r"(\n  irreversible_actions:[^\n]*\n)", r"\1    session_written_exec: maybe\n", s, count=1)
open(p,"w").write(s)
PY
grep -q 'session_written_exec: maybe' field-manifest.yaml || { echo "FAIL  could not build invalid-mode fixture"; fail=1; }
expect "invalid mode -> E0 deny" 2 "$(call t1 Bash '{"command":"ls"}')"
cd "$HERE"; rm -rf "$T" .claude
[ $fail -eq 0 ] && echo "ALL E5 TESTS PASSED" || echo "E5 TESTS FAILED"
exit $fail
