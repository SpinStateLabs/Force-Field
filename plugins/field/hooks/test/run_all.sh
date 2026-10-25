#!/usr/bin/env bash
# Runs every FIELD Enforcement Gate suite and fails on anything unexplained (ADR-0080).
#   bash hooks/test/run_all.sh
# - each suite must exit 0, print no FAIL line, and (except run.sh) print at least one PASS line;
# - run.sh must also report "LEDGER INTACT";
# - every line a suite prints that starts with SKIP is printed here with its reason, and the sorted list of them
#   must equal the allowlist for this platform (skip-allowlist-windows.txt, or skip-allowlist-posix.txt when that
#   file exists; a missing file means no SKIP is allowed). A SKIP that is not listed fails, and so does a listed
#   SKIP that no longer appears (a stale allowlist hides a test that came back or went away);
# - the launcher and the post hook, field-gate.sh and field-post.sh, must contain no carriage return: a CRLF
#   checkout is a syntax error under sh, exit 2, which blocks every gated call.
# Lines starting "N/A" are cases that do not exist on the platform; they are listed too, for the record.
set -u
cd "$(dirname "$0")"
HERE="$PWD"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) plat=windows;; *) plat=posix;; esac
SUITES=${SUITES:-"run.sh run_e5.sh run_launcher.sh run_e3_policy.sh run_estate_kill.sh run_post_hook.sh run_links.sh run_shell_forms.sh"}   # SUITES=... narrows a trial run
OUT=$(mktemp -d); trap 'rm -rf "$OUT"' EXIT
fail=0
echo "platform: $plat   bash: ${BASH_VERSION}   python3: $(python3 --version 2>&1)   PyYAML: $(python3 -c 'import yaml;print(yaml.__version__)' 2>&1)"
: > "$OUT/skips"; : > "$OUT/nas"
printf '%-22s %5s %6s %6s %6s\n' suite exit PASS FAIL SKIP
for s in $SUITES; do
  bash "./$s" > "$OUT/$s.txt" 2>&1; rc=$?
  p=$(grep -c '^PASS' "$OUT/$s.txt"); f=$(grep -c '^FAIL' "$OUT/$s.txt"); k=$(grep -c '^SKIP' "$OUT/$s.txt")   # FAIL is counted only at a line start: that is how the suites report a failed case
  printf '%-22s %5s %6s %6s %6s\n' "$s" "$rc" "$p" "$f" "$k"
  why=""
  [ "$rc" != 0 ] && why="$why exit $rc;"
  [ "$f" != 0 ] && why="$why $f FAIL line(s);"
  if [ "$s" = run.sh ]; then grep -q 'LEDGER INTACT' "$OUT/$s.txt" || why="$why no 'LEDGER INTACT';"
  else [ "$p" = 0 ] && why="$why no PASS line;"; fi
  if [ -n "$why" ]; then fail=1; echo "  SUITE FAILED ($s):$why last lines:"; { grep -A1 "^FAIL" "$OUT/$s.txt"; tail -n 15 "$OUT/$s.txt"; } | sed "s/^/    | /"; fi
  # a SKIP with its reason line (a following line that starts with whitespace and "reason:")
  awk -v s="$s" '{ if ($0 ~ /^SKIP/) print s ": " $0; else if ($0 ~ /^[ 	]+reason:/ && prev ~ /^SKIP/) print "      " $0; prev = $0 }' "$OUT/$s.txt" >> "$OUT/skips.full"
  grep '^SKIP' "$OUT/$s.txt" | sed "s/^/$s: /" >> "$OUT/skips"
  grep '^N/A' "$OUT/$s.txt" | sed "s/^/$s: /" >> "$OUT/nas"
done
echo
echo "--- SKIPs printed by the suites (with reasons) ---"
[ -s "$OUT/skips.full" ] && cat "$OUT/skips.full" || echo "(none)"
echo "--- N/A cases (do not exist on $plat) ---"
[ -s "$OUT/nas" ] && cat "$OUT/nas" || echo "(none)"

allow="skip-allowlist-$plat.txt"
if [ -f "$allow" ]; then grep -v '^[[:space:]]*\(#\|$\)' "$allow" | tr -d '\r' | sort > "$OUT/allow"; else : > "$OUT/allow"; fi
tr -d '\r' < "$OUT/skips" | sort > "$OUT/actual"
echo "--- SKIP allowlist ($allow): $(wc -l < "$OUT/allow" | tr -d ' ') entries; SKIPs seen: $(wc -l < "$OUT/actual" | tr -d ' ') ---"
if diff "$OUT/allow" "$OUT/actual" > "$OUT/skipdiff"; then echo "SKIP list equals the allowlist"
else
  fail=1; echo "SKIP list differs from the allowlist ('<' only in the allowlist, '>' unexplained SKIP):"; sed 's/^/    /' "$OUT/skipdiff"
fi

echo "--- line endings ---"
for f in ../field-gate.sh ../field-post.sh; do
  # tr, not grep: grep on Git Bash for Windows reads CRLF as LF and would never see the CR
  n=$(tr -cd '\r' < "$f" | wc -c | tr -d ' ')
  if [ "$n" != 0 ]; then fail=1; echo "FAIL  $f contains $n carriage return(s) (CRLF checkout)"; else echo "PASS  $f has no carriage return"; fi
done
echo "git core.autocrlf: $(git config --show-origin core.autocrlf 2>/dev/null || echo unset)"

[ "$fail" = 0 ] && echo "ALL GATE SUITES PASSED" || { echo "GATE SUITES FAILED"; exit 1; }
