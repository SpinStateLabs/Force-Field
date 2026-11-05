#!/usr/bin/env bash
# Regression tests for four external-tester findings (field 1.5.2). Run from anywhere:  bash hooks/test/run_bypass.sh
#   1. manifest deletion: E2 on interpreter one-liners (python -c ...) and E0/E1 when a governed project loses its manifest
#   2. `cd .claude && rm -r state`, and a missing or empty ledger must never verify as intact
#   3. E3 irreversible patterns must not depend on how rm / git push flags are spelled
# Written for bash 3.2 (macOS): no associative arrays, no ${var,,}, no mapfile.
# Prints PASS/FAIL per case and exits non-zero if any case fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"; G="$HERE/../field-gate.py"; V="$HERE/../verify-ledger.py"
# first interpreter that can import PyYAML (a Windows Store python3 stub exists but cannot run anything)
PY=""; for c in python3 python; do command -v "$c" >/dev/null 2>&1 && "$c" -c 'import yaml' >/dev/null 2>&1 && { PY=$c; break; }; done
[ -n "$PY" ] || { echo "FAIL  no Python 3 with PyYAML on this machine"; exit 1; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
expect() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; fail=1; fi; }
pj() { "$PY" -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }

# proj <name> -> a fresh governed project dir (the fixture manifest, no state yet)
proj() { local d="$T/$1"; rm -rf "$d"; mkdir -p "$d"; cp "$HERE/field-manifest.yaml" "$d/"; printf %s "$d"; }
# gate <dir> <tool> <input-json> -> sets RC (exit code) and ERR (stderr); FIELD_MANIFEST/other env come from the caller
gate() {
  ERR=$(printf '{"session_id":"b1","tool_name":"%s","tool_input":%s,"permission_mode":"default"}' "$2" "$3" \
        | CLAUDE_PROJECT_DIR="$1" "$PY" "$G" 2>&1 >/dev/null); RC=$?
}
# deny <label> <dir> <tool> <input-json> <rule>: exit 2 and the rule named on stderr
deny() {
  gate "$2" "$3" "$4"
  case "$ERR" in *"[$5]"*) expect "$1" "2 $5" "$RC $5" ;; *) expect "$1" "2 $5" "$RC (stderr: $ERR)" ;; esac
}
allow() { gate "$2" "$3" "$4"; expect "$1" 0 "$RC"; [ "$RC" = 0 ] || echo "      stderr: $ERR"; }
bash_deny() { deny "$1" "$2" Bash "$(pj "$3")" "$4"; }
bash_allow() { allow "$1" "$2" Bash "$(pj "$3")"; }

# ---- finding 1a: E2 matches protected names inside interpreter one-liners (substring, not end-anchored) ----
P=$(proj p1)
allow "warm-up call creates the ledger" "$P" Bash '{"command":"ls"}'
for c in "python3 -c \"import os; os.remove('field-manifest.yaml')\"" \
         "python3 -c \"import os; os.remove('FIELD-Manifest.YML')\"" \
         "python3 -c 'import os; os.remove(\"field-manifest.yaml\")'" \
         "python -c \"import pathlib; pathlib.Path('field-manifest.yaml').unlink()\"" \
         "sudo python3 -c \"import os; os.remove('field-manifest.yaml')\"" \
         "node -e \"require('fs').unlinkSync('field-manifest.yaml')\"" \
         "perl -e 'unlink q(field-manifest.yaml)'" \
         "ruby -e \"File.delete('field-manifest.yaml')\"" \
         "python3 -c \"open('.claude/settings.json','w')\"" \
         "python3 -c \"open('.claude/settings.local.json','w')\"" \
         "python3 -c \"import os; os.remove('hooks/hooks.json')\"" \
         "python3 -c \"import os; os.remove('.claude/state/field-ledger.jsonl')\"" \
         "python3 -c \"import shutil; shutil.rmtree('.claude/state')\"" \
         "python3 -c \"import shutil; shutil.rmtree('.claude/state/')\"" \
         "node -e \"require('fs').rmSync('.claude/state',{recursive:true})\"" \
         "php -r \"unlink('field-manifest.yaml');\"" \
         "python3 <<EOF
import os
os.remove('field-manifest.yaml')
EOF"; do
  bash_deny "E2 deny (interpreter text): $c" "$P" "$c" E2
done
deny "E2 deny (PowerShell .NET delete)" "$P" PowerShell '{"command":"[IO.File]::Delete(\"field-manifest.yaml\")"}' E2
deny "E2 deny (PowerShell Get-Item .Delete())" "$P" PowerShell '{"command":"(Get-Item '"'"'field-manifest.yaml'"'"').Delete()"}' E2
deny "E2 deny (PowerShell ledger)" "$P" PowerShell '{"command":"[IO.File]::WriteAllText(\".claude/state/field-ledger.jsonl\",\"\")"}' E2
# controls: ordinary interpreter use, the kill sentinel, and prose that merely names the manifest
for c in 'python3 -c "print(1)"' 'python3 build.py' "node -e \"console.log(1)\"" "perl -e 'print 1'" \
         "python3 -c \"open('.claude/state/KILL','w')\"" "python3 -c \"open('.claude/state/field.json','w')\"" \
         "python3 -c \"open('field-manifest.yaml.example','w')\"" 'git commit -m "update field-manifest.yaml"' 'echo "see field-manifest.yaml"'; do
  bash_allow "E2 allow: $c" "$P" "$c"
done
allow "E2 allow: PowerShell Get-ChildItem" "$P" PowerShell '{"command":"Get-ChildItem"}'

# ---- finding 1b: a governed project that loses its manifest fails closed (E0), and KILL always wins ----
P=$(proj p2)
allow "governed project: first call allowed" "$P" Bash '{"command":"ls"}'
rm -f "$P/field-manifest.yaml"
deny "manifest deleted, state present: Bash -> E0"      "$P" Bash '{"command":"ls"}' E0
deny "manifest deleted, state present: Edit -> E0"      "$P" Edit '{"file_path":"notes.txt","old_string":"a","new_string":"b"}' E0
deny "manifest deleted, state present: MCP tool -> E0"  "$P" mcp__fs__write_file '{"path":"notes.txt","content":"x"}' E0
deny "manifest deleted, state present: PowerShell -> E0" "$P" PowerShell '{"command":"Get-ChildItem"}' E0
allow "manifest deleted: Read stays ungated"            "$P" Read '{"file_path":"notes.txt"}'
mkdir -p "$P/.claude/state"; : > "$P/.claude/state/KILL"
deny "manifest deleted + KILL present -> E1 (KILL wins)" "$P" Bash '{"command":"echo hi"}' E1
deny "manifest deleted + KILL present: Write -> E1"      "$P" Write '{"file_path":"a.txt","content":"x"}' E1
# the kill sentinel is read before the manifest: a manifest that points the kill switch elsewhere cannot hide it
P=$(proj p3)
"$PY" - "$P/field-manifest.yaml" <<'PYEOF'
import sys, yaml
p = sys.argv[1]; d = yaml.safe_load(open(p))
d["enforcement"]["kill_switch"]["endpoint"] = ".claude/other-kill"
yaml.safe_dump(d, open(p, "w"), sort_keys=False)
PYEOF
allow "manifest with a custom kill endpoint: allowed while no sentinel exists" "$P" Bash '{"command":"ls"}'
: > "$P/.claude/state/KILL"
deny "default .claude/state/KILL still wins over a custom endpoint" "$P" Bash '{"command":"ls"}' E1
# each FIELD artefact alone marks a project as governed; the manifest is then required
for art in field-ledger.jsonl field-session-calls.json field-gate.lock; do
  P="$T/art-$art"; rm -rf "$P"; mkdir -p "$P/.claude/state"; : > "$P/.claude/state/$art"
  deny "no manifest, state holds $art -> E0" "$P" Bash '{"command":"ls"}' E0
done
P="$T/art-kill"; rm -rf "$P"; mkdir -p "$P/.claude/state"; : > "$P/.claude/state/KILL"
deny "no manifest, only KILL present -> E1" "$P" Bash '{"command":"ls"}' E1
P="$T/envm"; rm -rf "$P"; mkdir -p "$P"
FIELD_MANIFEST=custom-manifest.yaml; export FIELD_MANIFEST
deny "FIELD_MANIFEST set, manifest missing, no state -> E0" "$P" Bash '{"command":"ls"}' E0
cp "$HERE/field-manifest.yaml" "$P/custom-manifest.yaml"
allow "FIELD_MANIFEST set, manifest present -> allowed" "$P" Bash '{"command":"ls"}'
unset FIELD_MANIFEST
P=$(proj bad-yaml); printf 'enforcement: [unclosed\n' > "$P/field-manifest.yaml"
deny "unparseable manifest -> E0 (unchanged)" "$P" Bash '{"command":"ls"}' E0
# negatives: no manifest and no FIELD state is not a governed project, and the hook must leave it untouched
P="$T/ungoverned"; rm -rf "$P"; mkdir -p "$P"
allow "ungoverned (no manifest, no state): Bash allowed"  "$P" Bash '{"command":"ls"}'
allow "ungoverned: Write allowed"                         "$P" Write '{"file_path":"a.txt","content":"x"}'
allow "ungoverned: python -c naming the manifest allowed" "$P" Bash "$(pj "python3 -c \"open('field-manifest.yaml','w')\"")"
[ -e "$P/.claude" ] && expect "ungoverned project: hook creates no .claude directory" absent present || expect "ungoverned project: hook creates no .claude directory" absent absent
mkdir -p "$P/.claude/agents" "$P/.claude/state"; : > "$P/.claude/settings.json"; : > "$P/.claude/agents/x.md"; : > "$P/.claude/state/field.json"
allow "ungoverned: unrelated .claude files and the skill's field.json are not FIELD state" "$P" Bash '{"command":"ls"}'

# ---- finding 2: a wiped or emptied ledger never verifies as intact; cd-relative removal of the state dir is denied ----
P=$(proj p4)
allow "verify setup: governed call" "$P" Bash '{"command":"ls"}'
vr() { OUT=$(cd "$1" && CLAUDE_PROJECT_DIR="$1" "$PY" "$V" 2>&1); VRC=$?; }
vr "$P"; intact=n; case "$OUT" in *"LEDGER INTACT"*) intact=y;; esac  # not inside $(): bash 3.2 mis-parses a case pattern's ')' there
expect "verify: populated ledger is INTACT (control)" "0 y" "$VRC $intact"
: > "$P/.claude/state/field-ledger.jsonl"
vr "$P"; case "$OUT" in *"INTACT"*) expect "verify: EMPTY ledger must not report INTACT" "not intact" "$OUT";; *) expect "verify: EMPTY ledger must not report INTACT" ok ok;; esac
[ "$VRC" != 0 ] && expect "verify: EMPTY ledger exits non-zero" ok ok || expect "verify: EMPTY ledger exits non-zero" "non-zero" "$VRC"
case "$OUT" in *MISSING*) expect "verify: EMPTY ledger says MISSING" ok ok;; *) expect "verify: EMPTY ledger says MISSING" "MISSING in output" "$OUT";; esac
rm -rf "$P/.claude/state"
vr "$P"; [ "$VRC" != 0 ] && expect "verify: deleted state dir exits non-zero" ok ok || expect "verify: deleted state dir exits non-zero" "non-zero" "$VRC"
case "$OUT" in *"INTACT"*) expect "verify: deleted state dir must not report INTACT" "not intact" "$OUT";; *) expect "verify: deleted state dir must not report INTACT" ok ok;; esac
OUT=$(cd "$P" && "$PY" "$V" "$P/.claude/state/none.jsonl" 2>&1); VRC=$?
[ "$VRC" != 0 ] && expect "verify: explicit missing path exits non-zero" ok ok || expect "verify: explicit missing path exits non-zero" "non-zero" "$VRC"
: > "$T/empty.jsonl"; OUT=$("$PY" "$V" "$T/empty.jsonl" 2>&1); VRC=$?
[ "$VRC" != 0 ] && expect "verify: explicit empty file exits non-zero" ok ok || expect "verify: explicit empty file exits non-zero" "non-zero" "$VRC"
P=$(proj p5)
allow "cd-relative setup: governed call" "$P" Bash '{"command":"ls"}'
for c in 'cd .claude && rm -r state' 'cd .claude && rm -rf state/' 'cd ./.claude; rm -r ./state' 'cd .claude && mv state /tmp/s' \
         'cd .claude && rm state/field-ledger.jsonl' 'cd .claude && rm -f state/field-session-calls.json' \
         'cd .claude && cd state && rm field-ledger.jsonl' 'cd "$PWD/.claude" && rm -r state'; do
  case "$c" in *'$PWD'*) continue;; esac  # a variable: not resolvable from text (documented limit)
  bash_deny "E2 deny (cd-relative): $c" "$P" "$c" E2
done
for c in 'cd src && rm -r build' 'cd .claude/agents && ls' 'cd .claude && ls' 'cd docs && cat state.md'; do
  bash_allow "E2 allow (cd-relative control): $c" "$P" "$c"
done

# the shell's directory persists between calls: `cd .claude` in one call, `rm -r state` in the next. The hook input carries cwd.
abspath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf %s "$1"; fi; }
gate_cwd() { # dir cwd-subdir command -> sets RC, ERR
  ERR=$(printf '{"session_id":"b1","tool_name":"Bash","cwd":"%s","tool_input":%s,"permission_mode":"default"}'         "$(abspath "$1")/$2" "$(pj "$3")" | CLAUDE_PROJECT_DIR="$1" "$PY" "$G" 2>&1 >/dev/null); RC=$?
}
mkdir -p "$P/.claude/agents" "$P/src"
for c in 'rm -r state' 'rm -rf state/' 'rm state/field-ledger.jsonl' 'mv state /tmp/s'; do
  gate_cwd "$P" .claude "$c"; case "$ERR" in *"[E2]"*|*"[E3]"*) expect "E2/E3 deny (cwd .claude): $c" ok ok;; *) expect "E2/E3 deny (cwd .claude): $c" "deny" "$RC $ERR";; esac
done
gate_cwd "$P" .claude 'rm -r state'; case "$ERR" in *"[E2]"*) expect "cwd .claude: rm -r state is E2" ok ok;; *) expect "cwd .claude: rm -r state is E2" "[E2]" "$ERR";; esac
gate_cwd "$P" .claude/state 'rm field-ledger.jsonl'; case "$ERR" in *"[E2]"*) expect "cwd .claude/state: rm field-ledger.jsonl is E2" ok ok;; *) expect "cwd .claude/state: rm field-ledger.jsonl is E2" "[E2]" "$ERR";; esac
gate_cwd "$P" src 'rm -r build';  expect "allow (cwd src): rm -r build" 0 "$RC"
gate_cwd "$P" .claude/agents 'rm x.md'; expect "allow (cwd .claude/agents): rm x.md" 0 "$RC"
gate_cwd "$P" "" 'rm -r build'; expect "allow (cwd is the root): rm -r build" 0 "$RC"

# hardening: quoted names given to git, and git commands that remove untracked files without naming them
P=$(proj p7)
for c in 'git rm "field-manifest.yaml"' "git rm -f 'field-manifest.yaml'" 'git checkout -- "field-manifest.yaml"' \
         'git restore "field-manifest.yaml"' 'git mv "field-manifest.yaml" x' 'git rm -r ".claude/state"' \
         'git clean -fdx' 'git clean -n' 'git stash -u' 'git stash push --include-untracked' 'git stash -a'; do
  bash_deny "E2 deny (git): $c" "$P" "$c" E2
done
for c in 'git status' 'git stash' 'git stash pop' 'git checkout main' 'git rm old.txt' 'git commit -m "x"'; do
  bash_allow "E2 allow (git): $c" "$P" "$c"
done

# ---- opt-in ledger anchor (FIELD_ANCHOR_DIR): a deleted, emptied or truncated ledger is a rollback, not a fresh start ----
FIELD_ANCHOR_DIR="$T/anchors"; export FIELD_ANCHOR_DIR
P=$(proj p8)
allow "anchor: call 1" "$P" Bash '{"command":"ls"}'
allow "anchor: call 2" "$P" Bash '{"command":"ls"}'
vr "$P"; expect "anchor: intact ledger verifies" 0 "$VRC"
rm -rf "$P/.claude/state"
deny "anchor: state wiped, next call -> E0" "$P" Bash '{"command":"ls"}' E0
vr "$P"; [ "$VRC" != 0 ] && expect "anchor: wiped ledger fails verify" ok ok || expect "anchor: wiped ledger fails verify" "non-zero" "$VRC"
case "$OUT" in *"ROLLED BACK"*|*MISSING*) expect "anchor: verify names the problem" ok ok;; *) expect "anchor: verify names the problem" "ROLLED BACK" "$OUT";; esac
P=$(proj p9)
allow "anchor: truncate setup 1" "$P" Bash '{"command":"ls"}'
allow "anchor: truncate setup 2" "$P" Bash '{"command":"ls"}'
allow "anchor: truncate setup 3" "$P" Bash '{"command":"ls"}'  # one record of lag is tolerated, so cut two
head -n 1 "$P/.claude/state/field-ledger.jsonl" > "$P/l.tmp"; cp "$P/l.tmp" "$P/.claude/state/field-ledger.jsonl"
deny "anchor: truncated ledger -> E0" "$P" Bash '{"command":"ls"}' E0
rm -rf "$FIELD_ANCHOR_DIR"
allow "anchor: a human removing the anchor starts over" "$P" Bash '{"command":"ls"}'
unset FIELD_ANCHOR_DIR
P=$(proj p10); allow "no anchor configured: unchanged" "$P" Bash '{"command":"ls"}'; rm -rf "$P/.claude/state"
allow "no anchor configured: a wiped state restarts as before" "$P" Bash '{"command":"ls"}'

# ---- finding 3: E3 must not depend on flag spelling ----
P=$(proj p6)
for c in 'rm -rf node_modules' 'rm -fr x' 'rm -Rf x' 'rm -rfv x' 'rm -vfr x' 'rm -r -f x' 'rm -f -r x' 'rm -R -f x' \
         'rm --recursive --force x' 'rm --force --recursive x' 'rm -r --force x' 'rm --recursive -f x' 'rm -f --recursive x' \
         'rm x -rf' 'rm x -r -f' 'rm -rf -- x' 'sudo rm -fr x' 'sudo -u root rm -r -f x' 'xargs rm -fr' 'find . -type f | xargs rm -r -f' \
         'bash -c "rm -fr x"' "sh -c 'rm --recursive --force x'" 'eval "rm -r -f x"' 'ls; rm -fr x' 'ls && rm -r -f x' \
         'git push --force-with-lease' 'git push -f' 'git push origin main -f' 'git push --force' 'git push -uf origin main' \
         'git push origin +main' 'git push origin --delete main' 'git push -d origin main' 'git push origin :main' 'git push origin +HEAD:main' 'git push +main' 'git push --force-with-lease=main' \
         'git push --force-with-lease=main:abc123' 'git push --force-if-includes' 'git -C repo push -f' 'git -c x=y push -f origin' \
         'sudo git push -f' 'cd repo && git push -f' 'bash -c "git push origin +main"'; do
  bash_deny "E3 deny: $c" "$P" "$c" E3
done
deny "E3 deny (PowerShell): rm -fr x" "$P" PowerShell '{"command":"rm -fr x"}' E3
deny "E3 deny (PowerShell): git push -f" "$P" PowerShell '{"command":"git push -f"}' E3
for c in 'rm x' 'rm -f x' 'rm -r build' 'rm -v x' 'rm -rv build' 'rm --force x' 'rm --recursive build' \
         'git push' 'git push origin main' 'git push -u origin main' 'git push origin HEAD:refs/heads/topic' 'git push --follow-tags' \
         'git push --dry-run origin main' 'git push -n origin main' 'git push -v origin main' 'git push origin feature/a+b' \
         'git pull -f' 'git fetch -f' 'git branch -f x' 'git commit -m "x"' 'git commit -m "never git push -f"' \
         'echo "rm -fr is dangerous"' 'ls -fr' 'cp -rf a b' 'echo a+b'; do
  bash_allow "E3 allow: $c" "$P" "$c"
done

[ $fail -eq 0 ] && echo "ALL BYPASS TESTS PASSED" || echo "BYPASS TESTS FAILED"
exit $fail
