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
pj() { python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }
is_windows() { case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0;; *) return 1;; esac; }
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
# path_key must canonicalise ('..' and symlinks): dropping normpath/realpath passed every case before 1.2.3
expect "E5 deny: bash ./sub/../x.sh"         2 "$(call t1 Bash '{"command":"bash ./sub/../x.sh"}')"
expect "E5 deny: python3 a/b/../../x.py"     2 "$(call t1 Bash '{"command":"python3 a/b/../../x.py"}')"
if is_windows; then echo "SKIP  E5 symlinked project root (Windows)"; else
  L=$(mktemp -d); ln -s "$HERE" "$L/rootlink"
  expect "E5 deny: bash <symlink-to-root>/x.sh" 2 "$(call t1 Bash '{"command":"bash '"$L"'/rootlink/x.sh"}')"
  rm -rf "$L"
fi
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
# ---- E2 hardening (field 1.2.3; independent review 2026-10-12) ----
# F1: Bash is tokenised. An unquoted word naming a governance file anywhere in the command is denied
# (1.2.2 only caught the command's last word). Quoted words count when they are arguments of a
# mutating command, redirect targets, or inside a command string a shell/eval/wrapper runs. Globs and
# braces are expanded against the real paths in those positions only; rm/mv aimed at the project
# directory, a parent or .claude/ is denied. Session e2 writes nothing (no E5).
for c in 'rm field-manifest.yaml; true' 'echo x > field-manifest.yaml; true' 'echo x >field-manifest.yaml && ls' \
         'mv field-manifest.yaml /tmp/m && ls' 'cp a.yaml field-manifest.yaml; true' 'sed -i s/a/b/ field-manifest.yaml; true' \
         'tee field-manifest.yaml < a; true' 'dd if=a of=field-manifest.yaml; true' 'truncate -s0 field-manifest.yaml; true' \
         'install a field-manifest.yaml; true' 'ln -sf a field-manifest.yaml; true' 'rm -f .claude/state/field-ledger.jsonl; ls' \
         'rm -f .claude/state/field-session-calls.json; ls' 'rm -r .claude/state; ls' 'cd .claude/state && ls' \
         'cat field-manifest.yaml' 'find . -name field-manifest.yaml' \
         'rm -r .claude; ls' 'mv .claude /tmp/c; ls' 'rm -r .; ls' 'rm -r ..; ls' 'rm -r -- .; ls' \
         "sh -c 'rm field-manifest.yaml;true'" "bash -c \"sh -c 'rm field-manifest.yaml'\"" 'bash -lc "rm field-manifest.yaml"' \
         'eval "rm field-manifest.yaml"' 'sudo sh -c "rm field-manifest.yaml"' 'su -c "rm field-manifest.yaml"' \
         'rm "field-manifest.yaml"' 'echo x > "field-manifest.yaml"; true' 'echo "x > field-manifest.yaml; true' \
         "rm fie'ld-manifest.yaml'; true" 'cat hooks.json; true' \
         'rm {field-manifest,x}.yaml; true' 'rm *.yaml' 'rm field-manifest.*' 'rm -r .claude/*' 'rm *' 'rm ./*.y?ml' \
         'rm field-manifest.yam[l]' 'rm .claude/settings*.json' 'mv *.yaml /tmp/' 'chmod 600 *.yaml' 'sed -i s/a/b/ *.yaml' \
         'perl -pi -e s/a/b/ *.yaml' 'tee *.yaml < x' 'ln -sf x *.yaml' 'cp x *.yaml' 'truncate -s0 *.yaml' 'echo x >> *.yaml' \
         'sudo -u root rm *.yaml' 'timeout 5 rm *.yaml' 'ls *.yaml | xargs rm' "find . -name '*.yaml' | xargs rm" \
         "find . -name '*.yaml' -delete" "find . -name '*.yaml' -exec rm {} \;" \
         'echo "rm field-manifest.yaml" | sh' 'printf "rm field-manifest.yaml" | bash -s' 'echo "rm *.yaml" | sh' \
         'find . -delete' 'find . -type f -delete' 'find . -mtime +7 -exec rm {} \;' 'find .claude -delete' \
         'echo x > sub/../field-manifest.yaml; true' 'echo x > ./.claude/state/../state/field-ledger.jsonl; true'; do
  expect "E2 deny (shell word): $c" 2 "$(call e2 Bash "$(pj "$c")")"
done
expect "E2 deny (shell word): rm <abs root>/*.yaml" 2 "$(call e2 Bash "$(pj "rm $(abspath "$HERE")/*.yaml")")"
# controls: read-only globs, and governance names inside quoted arguments of non-command-carrying words
for c in 'echo x > notes.md; true' 'cat README.md; ls' 'rm -f build/field-manifest.yaml.bak' 'git add .claude/commands/x.md' \
         'ls .claude' 'mkdir -p .claude/agents' 'mkdir -p ~/.claude/state' 'touch .claude/state/KILL' 'rm -r build; mv old new' \
         'rm *.py' 'rm build/*' 'ls src/*.yaml' 'rm *.json' 'cp src/* dst/' 'git commit -m "fix * handling"' \
         'python3 -c "print(2*3)"' 'find . -name "*.py"' 'rm {a,b}.txt' 'echo manifest > my-notes.yaml' \
         'git commit -m "notes about the manifest"' 'rm .claude/agents/*' \
         'ls *' 'for f in *; do echo $f; done' "find . -name '*.yaml'" 'cat *.md' 'grep -r x .' 'wc -l *' \
         'git commit -m "update field-manifest.yaml"' 'echo "see field-manifest.yaml"' 'grep "field-manifest.yaml" README.md' \
         'cp *.yaml backup/' 'sed s/a/b/ *.yaml' 'echo "rm field-manifest.yaml"' 'cat list.txt | xargs rm' 'ls *.yaml | xargs wc -l' \
         "find . -name '*.py' -delete" 'tar czf x.tgz *.md' 'echo "see field-manifest.yaml" | cat' 'echo hello | sh' \
         'find . -type f' 'find build -delete' "find . -path './build/*' -delete"; do
  expect "E2 allow: $c" 0 "$(call e2 Bash "$(pj "$c")")"
done
expect "E2 allow: Write <HOME>/.claude/state/field-manifest-template.yaml (not this project's state dir)" 0 \
  "$(call e2w Write '{"file_path":"'"$(abspath "$HOME")"'/.claude/state/field-manifest-template.yaml","content":"x"}')"
# F2: file-tool and MCP paths are normalised (., .., ~, backslashes, symlinks) and the whole state directory is protected
expect "E2 deny: Write ./.claude/state/../state/field-ledger.jsonl" 2 "$(call e2w Write '{"file_path":"./.claude/state/../state/field-ledger.jsonl","content":"x"}')"
expect "E2 deny: Write .claude/state/other.json (whole state dir)"   2 "$(call e2w Write '{"file_path":".claude/state/other.json","content":"x"}')"
expect "E2 deny: Write .claude\\state\\field-session-calls.json"     2 "$(call e2w Write '{"file_path":".claude\\\\state\\\\field-session-calls.json","content":"x"}')"
expect "E2 deny: Edit <abs>/sub/../.claude/state/field-ledger.jsonl" 2 "$(call e2w Edit '{"file_path":"'"$(abspath "$HERE")"'/sub/../.claude/state/field-ledger.jsonl","old_string":"a","new_string":"b"}')"
expect "E2 deny: NotebookEdit .claude/state/x.ipynb"                2 "$(call e2w NotebookEdit '{"notebook_path":".claude/state/x.ipynb"}')"
expect "E2 deny: MCP ./.claude/state/../state/field-ledger.jsonl"   2 "$(call e2w mcp__fs__write_file '{"path":"./.claude/state/../state/field-ledger.jsonl","content":"x"}')"
expect "E2 deny: MCP .claude/state/x.json"                          2 "$(call e2w mcp__fs__write_file '{"path":".claude/state/x.json","content":"x"}')"
expect "E2 deny: Write ./docs/../field-manifest.yaml"               2 "$(call e2w Write '{"file_path":"./docs/../field-manifest.yaml","content":"x"}')"
if is_windows; then echo "SKIP  E2 symlink to the state dir (Windows)"; else
  ln -s .claude/state "$HERE/statelink"
  expect "E2 deny: Write statelink/field-ledger.jsonl (symlink to the state dir)" 2 "$(call e2w Write '{"file_path":"statelink/field-ledger.jsonl","content":"x"}')"
  rm "$HERE/statelink"
fi
expect "E2 allow: Write ./docs/../README.md"             0 "$(call e2w Write '{"file_path":"./docs/../README.md","content":"x"}')"
expect "E2 allow: Write .claude/state/KILL (/field kill)" 0 "$(call e2w Write '{"file_path":".claude/state/KILL","content":""}')"
expect "E2 allow: Write .claude/state/field.json (skill state)" 0 "$(call e2w Write '{"file_path":".claude/state/field.json","content":"{}"}')"
expect "E2 allow: Write .claude/agents/x.md"             0 "$(call e2w Write '{"file_path":".claude/agents/x.md","content":"x"}')"
expect "E2 allow: Write field-manifest.yaml.example"     0 "$(call e2w Write '{"file_path":"field-manifest.yaml.example","content":"x"}')"
# F4: case-insensitive on every platform (a case-insensitive file system is not a Windows-only thing)
expect "E2 deny: Write FIELD-MANIFEST.YAML"              2 "$(call e2w Write '{"file_path":"FIELD-MANIFEST.YAML","content":"x"}')"
expect "E2 deny: Bash echo x > Field-Manifest.yaml"      2 "$(call e2 Bash '{"command":"echo x > Field-Manifest.yaml"}')"
expect "E2 deny: Write .CLAUDE/Settings.json"            2 "$(call e2w Write '{"file_path":".CLAUDE/Settings.json","content":"x"}')"
expect "E2 deny: Write .Claude/State/x"                  2 "$(call e2w Write '{"file_path":".Claude/State/x","content":"x"}')"
expect "E2 deny: MCP HOOKS.JSON"                         2 "$(call e2w mcp__fs__write_file '{"path":"HOOKS.JSON","content":"x"}')"
expect "E2 deny: PowerShell Remove-Item *.yaml"          2 "$(call e2 PowerShell '{"command":"Remove-Item *.yaml"}')"
expect "E2 allow: PowerShell Remove-Item *.py"           0 "$(call e2 PowerShell '{"command":"Remove-Item *.py"}')"
expect "E2 allow: MCP content with '*' bullets is not a glob" 0 "$(call e2w mcp__fs__write_file '{"path":"notes.md","content":"* item\n* item two\na * b"}')"
# F3: size caps and a time budget. A hook killed by the hooks.json timeout fails open; the gate denies first.
expect "E0 deny: 70 KB shell command" 2 "$(call e2 Bash "$(python3 -c "import json; print(json.dumps({'command': '; '.join('bash a%d' % i for i in range(6000))}))")")"
r=$(python3 -c "import json; print(json.dumps({'session_id':'e2w','tool_name':'Write','tool_input':{'file_path':'big.txt','content':'A'*(5*1024*1024)}}))" | python3 "$G" >/dev/null 2>&1; echo $?)
expect "E0 deny: 5 MB hook input" 2 "$r"
r=$(python3 -c "import json; print(json.dumps({'session_id':'e2w','tool_name':'Write','tool_input':{'file_path':'big.txt','content':'A'*(3*1024*1024)}}))" | python3 "$G" >/dev/null 2>&1; echo $?)
expect "allow: 3 MB Write" 0 "$r"
s=$(date +%s); r=$(python3 -c "import json; print(json.dumps({'session_id':'e2','tool_name':'Bash','tool_input':{'command':'; '.join('bash a%d' % i for i in range(5000))}}))" | python3 "$G" >/dev/null 2>&1; echo $?); e=$(date +%s)
expect "allow: 58 KB / 5000-segment command (took 10 s in 1.2.2)" 0 "$r"
[ $((e-s)) -lt 10 ] && echo "PASS  5000-segment command checked in $((e-s)) s" || { echo "FAIL  5000-segment command took $((e-s)) s"; fail=1; }
python3 - "$G" <<'PY3'
import importlib.util, io, json, sys
spec = importlib.util.spec_from_file_location("g", sys.argv[1]); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
g.TIME_BUDGET_S = -1.0  # every check is already overdue: the E2 loop must deny E0, not run on
sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps({"session_id": "e2", "tool_name": "Bash", "tool_input": {"command": "ls"}}).encode()))
out, sys.stdout = io.StringIO(), io.StringIO()
try:
    g.main(); code = 0
except SystemExit as exc:
    code = exc.code
out, sys.stdout = sys.stdout, sys.__stdout__
ok = code == 2 and "[E0] E2 check exceeded" in out.getvalue()
print(("PASS" if ok else "FAIL") + "  time budget exceeded -> E0 deny"); sys.exit(0 if ok else 1)
PY3
[ $? -eq 0 ] || fail=1
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
expect "E5 off: E2 denies rm field-manifest.yaml; true" 2 "$(call t1 Bash '{"command":"rm field-manifest.yaml; true"}')"
expect "E5 off: E2 denies via crude tokens when shlex fails (unbalanced quote)" 2 "$(call t1 Bash "$(pj 'echo "x > field-manifest.yaml; true')")"
expect "E5 off: heredoc with an apostrophe still allowed (E2 tokeniser fallback is not fail-closed)" 0 "$(call t1 Bash "$(pj "cat <<EOF > notes.md
Don's notes
EOF")")"
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
