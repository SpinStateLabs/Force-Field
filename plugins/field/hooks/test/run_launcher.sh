#!/usr/bin/env bash
# Launcher tests (field-gate.sh). Run from anywhere:  bash hooks/test/run_launcher.sh
# Each case runs the launcher with a PATH holding only the interpreters that case wants, so a missing or
# broken Python can be simulated on any machine. Prints PASS/FAIL per case; exits non-zero if any fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"; L="$HERE/../field-gate.sh"
SH=$(command -v sh); PY=$(command -v python3 || command -v python)
[ -n "$PY" ] || { echo "FAIL  no Python 3 on this machine to run the positive cases"; exit 1; }
"$PY" -c 'import yaml' 2>/dev/null || { echo "FAIL  PyYAML missing for $PY"; exit 1; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
expect() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; fail=1; fi; }
wrap() { # dir name script-body: a tiny executable, portable to Git Bash (no symlinks)
  printf '#!%s\n%s\n' "$SH" "$3" > "$1/$2"; chmod +x "$1/$2"
}
bin() { # fresh PATH dir with the utilities the launcher needs and nothing else
  local d="$T/bin$RANDOM$RANDOM"; mkdir -p "$d"
  for u in dirname cat; do wrap "$d" "$u" "exec $(command -v $u) \"\$@\""; done
  printf %s "$d"
}
run() { # path-dir project-dir json [FIELD_MANIFEST] -> "exit|stdout"
  local out rc
  out=$(printf %s "$3" | env -i PATH="$1" CLAUDE_PROJECT_DIR="$2" ${4:+FIELD_MANIFEST="$4"} "$SH" "$L" 2>/dev/null); rc=$?
  printf '%s|%s' "$rc" "$out"
}
ALLOW='{"session_id":"l1","tool_name":"Bash","tool_input":{"command":"ls -la"}}'
DENY3='{"session_id":"l1","tool_name":"Bash","tool_input":{"command":"rm -rf build"}}'
GOV="$T/gov"; mkdir -p "$GOV"; cp "$HERE/field-manifest.yaml" "$GOV/"
FREE="$T/free"; mkdir -p "$FREE"

# 1. no interpreter at all
B=$(bin)
r=$(run "$B" "$GOV" "$ALLOW"); expect "no Python + manifest -> deny E0" 2 "${r%%|*}"
case $r in *'"permissionDecision": "deny"'*'[E0]'*) expect "no Python + manifest -> deny JSON on stdout" y y ;;
  *) expect "no Python + manifest -> deny JSON on stdout" y n ;; esac
r=$(run "$B" "$FREE" "$ALLOW"); expect "no Python, no manifest -> allow" 0 "${r%%|*}"
r=$(run "$B" "$T" "$ALLOW" gov/field-manifest.yaml); expect "no Python + relative FIELD_MANIFEST -> deny" 2 "${r%%|*}"
r=$(run "$B" "$FREE" "$ALLOW" "$GOV/field-manifest.yaml"); expect "no Python + absolute FIELD_MANIFEST -> deny" 2 "${r%%|*}"
r=$(run "$B" "$GOV" "$ALLOW" missing.yaml); expect "no Python + FIELD_MANIFEST pointing nowhere -> allow" 0 "${r%%|*}"
r=$(printf %s "$ALLOW" | (cd "$GOV" && env -i PATH="$B" "$SH" "$L" >/dev/null 2>&1); echo $?)
expect "no Python, no CLAUDE_PROJECT_DIR, cwd has manifest -> deny" 2 "$r"

# 2. Store-alias stub (reads stdin, exits 9009 -> 49 under a POSIX shell) and Python 2 (exit 1), real python last
B=$(bin)
wrap "$B" python3 'cat >/dev/null; echo "Python was not found; run without arguments to install from the Microsoft Store" >&2; exit 49'
wrap "$B" py 'cat >/dev/null; exit 1'
wrap "$B" python "exec \"$PY\" \"\$@\""
rm -rf "$GOV/.claude"
r=$(run "$B" "$GOV" "$ALLOW"); expect "stub python3 + broken py -> python runs the gate (allow)" 0 "${r%%|*}"
r=$(run "$B" "$GOV" "$DENY3"); expect "stub python3 + broken py -> python runs the gate (E3 deny)" 2 "${r%%|*}"
case $r in *'[E3]'*) expect "stdin replayed intact to the third attempt" y y ;; *) expect "stdin replayed intact to the third attempt" y n ;; esac
n=$(wc -l < "$GOV/.claude/state/field-ledger.jsonl" | tr -d ' ')
expect "one ledger record per call, none from failed attempts" 2 "$n"
(cd "$GOV" && CLAUDE_PROJECT_DIR="$GOV" "$PY" "$HERE/../verify-ledger.py" >/dev/null 2>&1); expect "ledger chain intact" 0 $?

# 3. `py -3` (Windows launcher) is used, with -3, when python3 is absent
B=$(bin)
wrap "$B" py "[ \"\$1\" = -3 ] || exit 1; shift; exec \"$PY\" \"\$@\""
r=$(run "$B" "$GOV" "$DENY3"); expect "py -3 runs the gate when python3 is absent" 2 "${r%%|*}"

# 4. a working python3 is used first and its verdicts pass through unchanged
B=$(bin)
wrap "$B" python3 "exec \"$PY\" \"\$@\""
wrap "$B" python 'exit 0'  # must never be reached: python3 already answered
r=$(run "$B" "$GOV" "$ALLOW"); expect "python3 allow passes through" 0 "${r%%|*}"
r=$(run "$B" "$GOV" "$DENY3"); expect "python3 deny passes through (not masked by python)" 2 "${r%%|*}"
r=$(run "$B" "$FREE" "$DENY3"); expect "python3, no manifest -> gate does nothing" 0 "${r%%|*}"

# 5. a large input survives the replay
B=$(bin); wrap "$B" python3 "exec \"$PY\" \"\$@\""
big=$("$PY" -c 'import json;print(json.dumps({"session_id":"l2","tool_name":"Write","tool_input":{"file_path":"big.txt","content":"x"*200000}}))')
r=$(run "$B" "$GOV" "$big"); expect "200 KB input -> allow" 0 "${r%%|*}"

# 6. no double count: once the gate has run (state written), no second interpreter may run it again
fresh() { local d="$T/p$RANDOM$RANDOM"; mkdir -p "$d"; cp "$HERE/field-manifest.yaml" "$d/"; printf %s "$d"; }
records() { wc -l < "$1/.claude/state/field-ledger.jsonl" | tr -d ' '; }
#    6a. stdout closed by the reader (Claude Code gone): the deny's print fails after the ledger write
B=$(bin)
wrap "$B" python3 "exec \"$PY\" -c 'import os,subprocess,sys; r,w=os.pipe(); os.close(r); sys.exit(subprocess.run([sys.executable]+sys.argv[1:], stdout=w).returncode)' \"\$@\""
wrap "$B" python "exec \"$PY\" \"\$@\""
P6=$(fresh); r=$(run "$B" "$P6" "$DENY3")
expect "closed stdout after the ledger write -> still exit 2" 2 "${r%%|*}"
expect "closed stdout -> one ledger record, no retry" 1 "$(records "$P6")"
#    6b. the gate is killed after it ran (exit 137)
B=$(bin)
wrap "$B" python3 "\"$PY\" \"\$@\" >/dev/null 2>&1; exit 137"
wrap "$B" python "exec \"$PY\" \"\$@\""
P6=$(fresh); r=$(run "$B" "$P6" "$ALLOW")
expect "gate killed mid-run + manifest -> deny E0, no retry" 2 "${r%%|*}"
expect "gate killed mid-run -> one ledger record" 1 "$(records "$P6")"
r=$(run "$B" "$FREE" "$ALLOW"); expect "gate killed mid-run, no manifest -> allow" 0 "${r%%|*}"

# 7. a missing field-gate.py (Python would exit 2 for it) is not taken as a verdict
mkdir -p "$T/lonely"; cp "$L" "$T/lonely/"
B=$(bin); wrap "$B" python3 "exec \"$PY\" \"\$@\""
r=$(printf %s "$ALLOW" | env -i PATH="$B" CLAUDE_PROJECT_DIR="$FREE" "$SH" "$T/lonely/field-gate.sh" 2>/dev/null; echo "|$?")
expect "missing gate file, no manifest -> allow" 0 "${r##*|}"
r=$(printf %s "$ALLOW" | env -i PATH="$B" CLAUDE_PROJECT_DIR="$GOV" "$SH" "$T/lonely/field-gate.sh" 2>/dev/null; echo "|$?")
expect "missing gate file + manifest -> deny E0" 2 "${r##*|}"

# 8. the gate itself: an exception outside main()'s handlers (here: in the manifest lookup) exits 2, not 1
cat > "$T/t8.py" <<'PY'
import pathlib, runpy, sys
def boom(self):
    raise RuntimeError("boom")
pathlib.Path.exists = boom
sys.argv = [sys.argv[1]]
runpy.run_path(sys.argv[0], run_name="__main__")
PY
r=$(printf %s "$ALLOW" | CLAUDE_PROJECT_DIR="$(fresh)" "$PY" "$T/t8.py" "$HERE/../field-gate.py" >/dev/null 2>&1; echo $?)
expect "gate error outside main()'s handlers -> exit 2" 2 "$r"

exit $fail
