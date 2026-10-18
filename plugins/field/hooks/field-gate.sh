#!/bin/sh
# FIELD Enforcement Gate launcher (field plugin 1.2.4). hooks.json runs this instead of `python3` directly.
#
# Claude Code treats a hook that exits with anything other than 0 or 2 as a non-blocking error and runs the
# tool anyway. A bare `python3` command therefore failed OPEN whenever Python could not start: no python3
# on PATH (exit 127), or the Windows Store alias stub with no Python behind it (exit 9009). This launcher
# tries python3, then the Windows launcher `py -3`, then python, with the hook input replayed to each.
# Once field-gate.py runs it exits 0 or 2 only (its __main__ guard), so:
#   0 or 2        -> the gate's verdict, passed through;
#   1-127 (not 2) -> that interpreter never ran the gate (not found, a stub, Python 2, too old): try the next;
#   128 and up    -> the gate was killed mid-run, maybe after writing state: no retry (it could double-count).
# When no interpreter gives a verdict, the call is denied with E0 if the project has a manifest and allowed
# if it has none (without a manifest the gate does nothing, so a missing Python must not block other projects).
# The manifest is looked up as field-gate.py does, minus the hook input's cwd: $FIELD_MANIFEST (absolute,
# or relative to the root), else field-manifest.yaml, under $CLAUDE_PROJECT_DIR, else the working directory.
trap '' PIPE  # a closed stdout must not turn the final exit 2 into a SIGPIPE death (non-blocking)
here=$(dirname "$0")
gate=$here/field-gate.py
input=$(cat)  # buffered so each attempt gets it; trailing newlines are dropped, which JSON ignores

if [ -f "$gate" ]; then  # a missing gate file makes Python exit 2, which must not pass as a verdict
  for py in python3 py python; do
    command -v "$py" >/dev/null 2>&1 || continue
    if [ "$py" = py ]; then
      printf '%s' "$input" | py -3 "$gate"
    else
      printf '%s' "$input" | "$py" "$gate"
    fi
    rc=$?
    case $rc in
      0|2) exit "$rc" ;;
    esac
    [ "$rc" -ge 128 ] && break
  done
fi

root=${CLAUDE_PROJECT_DIR:-}
[ -n "$root" ] && [ -d "$root" ] || root=$PWD
case ${FIELD_MANIFEST:-} in
  "") manifest=$root/field-manifest.yaml ;;
  /*|\\*|[A-Za-z]:*) manifest=$FIELD_MANIFEST ;;
  *) manifest=$root/$FIELD_MANIFEST ;;
esac
[ -e "$manifest" ] || exit 0

reason="the gate gave no verdict (no Python 3 could run it: tried python3, py -3, python; or it was killed); install Python 3 and PyYAML; fail-closed"
echo "FIELD DENY [E0]: $reason" >&2
printf '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "[E0] %s"}}\n' "$reason"
exit 2
