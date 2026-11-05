#!/bin/sh
# FIELD x FORCE composition launcher (SessionStart). Fails OPEN like field-post.sh: it only adds context,
# always exits 0, and prints only what field-compose.py prints. No Python: nothing is injected.
trap '' PIPE
here=$(dirname "$0")
script=$here/field-compose.py
input=$(cat)
if [ -f "$script" ]; then
  for py in python3 py python; do
    command -v "$py" >/dev/null 2>&1 || continue
    if [ "$py" = py ]; then
      out=$(printf '%s' "$input" | py -3 "$script")
    else
      out=$(printf '%s' "$input" | "$py" "$script")
    fi
    [ $? -eq 0 ] && { [ -n "$out" ] && printf '%s\n' "$out"; break; }
  done
fi
exit 0
