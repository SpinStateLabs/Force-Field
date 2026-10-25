#!/usr/bin/env bash
# LIVE test (ADR-0081): a gate hook that times out BLOCKS the tool call on a real Claude Code build.
#   bash hooks/test/run_timeout_live.sh
# NOT in run_all.sh or CI: it needs a logged-in `claude` (2.1.295 or later) and makes three model calls (`claude -p`,
# each up to --max-turns 2). Without a usable claude it prints SKIP with the reason and exits 0.
#
# Each case runs `claude -p --plugin-dir <dir>` from a fresh, empty project directory (no field-manifest.yaml, so an
# installed copy of the gate, if the user has one, finds no manifest and allows; it cannot block or mask a case):
#   A  a copy of plugins/field whose hooks/field-gate.sh sleeps 20 s (past the 10 s timeout), hooks.json verbatim:
#      the shell call (Bash or PowerShell tool) must be BLOCKED (its tool_result is an error, no tool_result shows the
#      echo's output);
#   B  CONTROL: the same copy with "onFailure" removed from its hooks.json: the call must go through, which shows the
#      key is what blocks and that a plugin without it fails open on this build;
#   C  SANITY: this branch's plugins/field unmodified (the real gate): the call goes through and the run completes.
# The stub writes a marker line when it starts, so A and B prove the stub hook actually ran.
# Windows: hooks must run under Git Bash for B to mean anything. Without Git Bash, Claude Code runs the hook in
# PowerShell and (2.1.299 and later) blocks a failed PreToolUse hook that sets no "shell" whatever onFailure says, so B
# would block too. When CLAUDE_CODE_GIT_BASH_PATH is unset the child gets the Git Bash running this script
# (FIELD_LIVE_GIT_BASH=off leaves it unset, to observe Claude Code's own detection). Each case prints the hook shell.
# The child claude runs with every CLAUDE_* (except CLAUDE_CONFIG_DIR, CLAUDE_CODE_GIT_BASH_PATH), ANTHROPIC_*,
# *_TOKEN, *_KEY, *_SECRET, STRIPE_*, FLY_*, NETLIFY_*, GH_*, GITHUB_*, FIELD_* and AWS_* variable removed (the claude.ai
# login is read from claude's own config, not the env).
# Transcripts (stream-json, each line prefixed with its arrival time) are saved under $FIELD_LIVE_OUT (default: a new
# temporary directory), never in the repository. Only assertion lines and timings are printed.
# Optional: FIELD_LIVE_MODEL (default sonnet), FIELD_LIVE_CASES (default "A B C"; one model call per case).
set -u
LC_NUMERIC=C   # EPOCHREALTIME with a '.' decimal point (not exported: the child keeps the caller's locale)
cd "$(dirname "$0")"
HERE="$PWD"
SRC=$(cd "$HERE/../.." && pwd)   # plugins/field of this checkout
MIN=2.1.295
MODEL=${FIELD_LIVE_MODEL:-sonnet}
CASES=${FIELD_LIVE_CASES:-A B C}
PROMPT="Run exactly this shell command and show its output: echo FIELD-LIVE-OK"
native() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf %s "$1"; fi; }
skip() { echo "SKIP  live hook-timeout test"; echo "      reason: $1"; exit 0; }

PY=$(command -v python3 || command -v python) || skip "no Python 3 to read the transcripts"
CLAUDE=$(command -v claude) || skip "claude is not on PATH"

# the child environment: the caller's, minus anything that could carry a credential or redirect claude
SCRUB=()
for name in $(compgen -e); do
  case $name in
    CLAUDE_CONFIG_DIR|CLAUDE_CODE_GIT_BASH_PATH) ;;   # where claude keeps its login; where Git Bash is (Windows)
    CLAUDECODE|CLAUDE_*|ANTHROPIC_*|*_TOKEN|*_TOKEN_*|*_KEY|*_SECRET|*_PASSWORD|STRIPE_*|FLY_*|NETLIFY_*|GH_*|GITHUB_*|FIELD_*|AWS_*)
      SCRUB+=(-u "$name") ;;
  esac
done
GITBASH="not Windows"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*)
  if [ "${FIELD_LIVE_GIT_BASH:-auto}" = off ]; then
    SCRUB+=(-u CLAUDE_CODE_GIT_BASH_PATH); GITBASH="unset (Claude Code's own detection)"
  elif [ -n "${CLAUDE_CODE_GIT_BASH_PATH:-}" ]; then
    GITBASH="$CLAUDE_CODE_GIT_BASH_PATH (caller's CLAUDE_CODE_GIT_BASH_PATH)"
  else
    gb="$(cygpath -m /)bin/bash.exe"; [ -f "$gb" ] || gb=$(cygpath -m "$BASH")
    export CLAUDE_CODE_GIT_BASH_PATH; CLAUDE_CODE_GIT_BASH_PATH=$(cygpath -w "$gb")
    GITBASH="$CLAUDE_CODE_GIT_BASH_PATH (the Git Bash running this script)"
  fi ;;
esac
cl() { env "${SCRUB[@]}" "$CLAUDE" "$@"; }

ver=$(cl --version 2>/dev/null | head -n 1)
v=$(printf %s "$ver" | grep -oE '^[0-9]+\.[0-9]+\.[0-9]+') || skip "cannot read 'claude --version' (got: $ver)"
"$PY" -c 'import sys; a, b = (tuple(map(int, x.split("."))) for x in sys.argv[1:3]); sys.exit(0 if a >= b else 1)' "$v" "$MIN" \
  || skip "claude $v is older than $MIN, the first build with onFailure (not tested on older builds)"
auth=$(cl auth status 2>/dev/null | "$PY" -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: d = {}
print("yes" if d.get("loggedIn") is True else "no", d.get("authMethod"))')
case $auth in yes*) ;; *) skip "claude auth status: not logged in ($auth)";; esac

base=${TMPDIR:-${TMP:-/tmp}}
WORK=$(mktemp -d "$base/field-live.XXXXXX")
OUT=${FIELD_LIVE_OUT:-$WORK/out}; mkdir -p "$OUT"
echo "claude $v ($(printf %s "$auth" | cut -d' ' -f2)), model $MODEL; Git Bash for hooks: $GITBASH; transcripts: $(native "$OUT")"

# plugin <name> -> a copy of plugins/field whose gate launcher is a stub that never answers inside the timeout
plugin() {
  local d="$WORK/$1"
  cp -R "$SRC" "$d" && rm -rf "$d/hooks/test"
  cat > "$d/hooks/field-gate.sh" <<'STUB'
#!/bin/sh
# live-test stub: records that it started, then outlasts the 10 s hook timeout
echo "start $(date +%s.%N)" >> "$(dirname "$0")/stub-calls.log"
cat > /dev/null
sleep 20
echo "end $(date +%s.%N)" >> "$(dirname "$0")/stub-calls.log"
exit 0
STUB
  printf %s "$d"
}

fail=0
# run <case> <plugin dir> -> transcript at $OUT/<case>.jsonl, prints the elapsed time
run() {
  local c=$1 dir; dir=$(native "$2")
  local proj; proj=$(mktemp -d "$WORK/project-$c.XXXXXX")
  local t0=$EPOCHREALTIME
  ( cd "$proj" && timeout 300 env "${SCRUB[@]}" "$CLAUDE" -p "$PROMPT" --plugin-dir "$dir" --model "$MODEL" \
      --allowedTools "Bash(echo:*)" "PowerShell(echo:*)" --max-turns 2 --output-format stream-json --verbose --include-hook-events \
      --no-session-persistence --permission-prompts none 2> "$OUT/$c.stderr.txt" ) \
    | while IFS= read -r line || [ -n "$line" ]; do printf '%s\t%s\n' "$EPOCHREALTIME" "$line"; done > "$OUT/$c.jsonl"
  local t1=$EPOCHREALTIME
  echo "case $c: claude -p finished in $("$PY" -c 'import sys; print("%.1f" % (float(sys.argv[2].replace(",", ".")) - float(sys.argv[1].replace(",", "."))))' "$t0" "$t1") s"
  grep -q '"type":"result"' "$OUT/$c.jsonl" || echo "      $c: no result event in the transcript; stderr: $(head -c 300 "$OUT/$c.stderr.txt" | tr '\n' ' ')"
}

# check <case> <transcript> <stub marker or -> : prints the assertion lines; exit 1 on a FAIL
check() {
  "$PY" - "$1" "$(native "$2")" "$3" <<'PYEOF'
import json, re, sys
case, path, marker = sys.argv[1:4]
SHELL_TOOLS = ("Bash", "PowerShell")
uses, results, hooks, final, no_git_bash = {}, [], [], None, False
for raw in open(path, encoding="utf-8", errors="replace"):
    ts, _, line = raw.rstrip("\n").partition("\t")
    try:
        ev, ts = json.loads(line), float(ts.replace(",", "."))
    except ValueError:
        continue
    t = ev.get("type")
    if t == "assistant":
        for b in ev.get("message", {}).get("content") or []:
            if b.get("type") == "tool_use":
                uses[b.get("id")] = (b.get("name"), ts, json.dumps(b.get("input"))[:120])
    elif t == "user":
        content = ev.get("message", {}).get("content")
        for b in content if isinstance(content, list) else []:
            if b.get("type") == "tool_result":
                c = b.get("content")
                text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                results.append((b.get("tool_use_id"), bool(b.get("is_error")), text, ts))
    elif t == "result":
        final = ev
    if "hook" in str(ev.get("subtype", "")):
        hooks.append(ev)
    if t == "system" and "Git Bash wasn't found" in str(ev.get("content", "")):
        no_git_bash = True
shell = [(uid, err, text, ts) for uid, err, text, ts in results if uses.get(uid, ("",))[0] in SHELL_TOOLS]
ran = [r for r in shell if any(l.strip() == "FIELD-LIVE-OK" for l in r[2].splitlines())]
starts = []
if marker != "-":
    try:
        for l in open(marker):
            m = re.match(r"start ([0-9]+(?:[.,][0-9]+)?)", l)  # date without %N (macOS) still gives whole seconds
            if m:
                starts.append(float(m.group(1).replace(",", ".")))
    except OSError:
        pass
fail = 0
def line(ok, label):
    global fail
    print(("PASS  " if ok else "FAIL  ") + "%s: %s" % (case, label))
    fail |= not ok
def short(s):
    return re.sub(r"\s+", " ", s).strip()[:220]
print("      %s: hook shell: %s" % (case, "PowerShell (Claude Code: Git Bash wasn't found)" if no_git_bash else "Git Bash (no 'Git Bash wasn't found' notice)"))
for uid, err, text, ts in shell:
    t_use = uses[uid][1]
    stub = [s for s in starts if t_use - 1 <= s <= ts]
    extra = ("; stub started +%.1f s after the tool_use, the result came %.1f s after the stub started" % (stub[0] - t_use, ts - stub[0])) if stub else ""
    print("      %s: %s call wall time %.1f s (tool_use line to tool_result line), is_error=%s%s" % (case, uses[uid][0], ts - t_use, err, extra))
if marker != "-":
    line(len(starts) >= 1, "the stub gate hook ran (%d start line(s) in its marker)" % len(starts))
if case == "A":
    line(len(shell) >= 1, "the model made a shell call (%d)" % len(shell))
    line(bool(shell) and all(err for _, err, _, _ in shell), "every shell tool_result is an error (blocked)")
    named = [text for _, err, text, _ in shell if err and re.search(r"hook|time(d)? ?out|PreToolUse", text, re.I)]
    line(bool(named), "the error names the hook or the timeout: %r" % (short(named[0]) if named else short(shell[0][2]) if shell else ""))
    line(not ran, "no tool_result contains the line FIELD-LIVE-OK (the command did not run)")
elif case == "B":
    line(bool(ran) and not ran[0][1], "a shell tool_result contains FIELD-LIVE-OK (a timed-out hook without onFailure lets the call through)")
    if not ran and shell:
        print("      B: the call was refused: %r" % short(shell[0][2]))
elif case == "C":
    line(bool(ran) and not ran[0][1], "a shell tool_result contains FIELD-LIVE-OK (the real gate, no manifest, allows)")
    line(bool(final) and final.get("subtype") == "success" and not final.get("is_error"),
         "the run completes (result subtype %r)" % (final or {}).get("subtype"))
with open(path[: -len(".jsonl")] + ".hooks.txt", "w", encoding="utf-8") as fh:  # for the record, not printed
    for ev in hooks:
        fh.write(json.dumps({k: ev.get(k) for k in ev if k not in ("session_id", "uuid")})[:600] + "\n")
sys.exit(1 if fail else 0)
PYEOF
}

A=$(plugin plugA)
B=$(plugin plugB)
"$PY" - "$(native "$B/hooks/hooks.json")" <<'PYEOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
for group in d["hooks"]["PreToolUse"]:
    for h in group["hooks"]:
        h.pop("onFailure", None)
json.dump(d, open(p, "w", encoding="utf-8"), indent=2)
PYEOF
cmp -s "$SRC/hooks/hooks.json" "$A/hooks/hooks.json" || { echo "FAIL  A: hooks.json is not the branch's file verbatim"; fail=1; }
grep -q onFailure "$B/hooks/hooks.json" && { echo "FAIL  B: onFailure still present in the control copy"; fail=1; }

for c in $CASES; do
  case $c in
    A) run A "$A"; check A "$OUT/A.jsonl" "$(native "$A/hooks/stub-calls.log")" || fail=1 ;;
    B) run B "$B"; check B "$OUT/B.jsonl" "$(native "$B/hooks/stub-calls.log")" || fail=1 ;;
    C) run C "$SRC"; check C "$OUT/C.jsonl" - || fail=1 ;;
    *) echo "FAIL  unknown case $c in FIELD_LIVE_CASES"; fail=1 ;;
  esac
done
cp "$A/hooks/stub-calls.log" "$OUT/A.stub-calls.log" 2>/dev/null; cp "$B/hooks/stub-calls.log" "$OUT/B.stub-calls.log" 2>/dev/null

# a stub that Claude Code abandoned may still be sleeping: wait (at most 21 s after its last start) so none outlives this script
last=$(cat "$A/hooks/stub-calls.log" "$B/hooks/stub-calls.log" 2>/dev/null | awk '$1 == "start" { if ($2 > m) m = $2 } END { print int(m) }')
while [ "${last:-0}" -gt 0 ] && [ "$(date +%s)" -le $((last + 21)) ]; do sleep 1; done
rm -rf "$WORK/plugA" "$WORK/plugB" "$WORK"/project-*

[ "$fail" = 0 ] && echo "ALL LIVE ASSERTIONS PASSED" || { echo "LIVE ASSERTIONS FAILED"; exit 1; }
