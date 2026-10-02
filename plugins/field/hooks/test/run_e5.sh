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
