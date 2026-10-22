#!/bin/sh
# FIELD post-call evidence hook launcher (field plugin 1.5). hooks.json runs this for PostToolUse.
# Separate from field-gate.sh on purpose: the gate's launcher retries only when the gate provably never
# started and fails closed; this one is evidence only and fails open. It ALWAYS exits 0 and prints nothing
# to stdout, so Claude Code cannot read a decision from it. It tries python3, `py -3`, python and stops at
# the first that exits 0 (field-post.py exits 0 once it runs, so any other status means it never ran; a
# repeat is harmless anyway: the record is written once per tool_use_id). No Python: nothing is recorded.
trap '' PIPE
here=$(dirname "$0")
post=$here/field-post.py
input=$(cat)
if [ -f "$post" ]; then
  for py in python3 py python; do
    command -v "$py" >/dev/null 2>&1 || continue
    if [ "$py" = py ]; then
      printf '%s' "$input" | py -3 "$post" >/dev/null
    else
      printf '%s' "$input" | "$py" "$post" >/dev/null
    fi
    [ $? -eq 0 ] && break
  done
fi
exit 0
