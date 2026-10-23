#!/usr/bin/env bash
# Link and Windows path-alias tests (ADR-0080). Run from anywhere:  bash hooks/test/run_links.sh
# A symlink or a Windows junction must not hide a governance path (E2) or a session-written file (E5) from the
# gate. On Windows the gate also has to see through the other spellings Win32 treats as the same file: a
# \\?\ prefix, an NTFS stream (file::$DATA), a trailing dot or space, and an 8.3 short name.
#   junction: created with `mklink /J` (no privilege needed). symlink: `mklink /D` on Windows, `ln -s` on POSIX.
#   If the OS refuses to create a symlink, the symlink cases print an explicit SKIP with the reason (never silent);
#   the SKIP allowlist in the CI driver (run_all.sh) decides whether that is acceptable.
#   "N/A" lines are cases that do not exist on this platform (not a skip: nothing to test here).
# Prints PASS/FAIL per case and exits non-zero if any case fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"
fail=0
is_windows() { case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0;; *) return 1;; esac; }
if is_windows; then export MSYS2_ARG_CONV_EXCL='*'; fi   # keep \\?\ and C:\ arguments to python and cmd as typed
abspath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf %s "$1"; fi; }
G=$(abspath "$HERE/..")/field-gate.py   # a native path: with MSYS2_ARG_CONV_EXCL a /c/... path would reach python unconverted
call() { # session tool json-input -> prints exit code
  printf '{"session_id":"%s","tool_name":"%s","tool_input":%s}' "$1" "$2" "$3" | python3 "$G" >/dev/null 2>"$ERRF"; local rc=$?
  # exit 2 only counts as a deny when the gate itself said so (a python start failure also exits 2)
  if [ "$rc" = 2 ] && ! grep -q '^FIELD DENY \[' "$ERRF"; then rc=99; fi
  echo "$rc"
}
expect() { # label expected actual; a deny must also come from the rule the label names (E2 or E5); a FAIL shows the gate's reason
  local rule; rule=${1%% *}; local ok=0
  if [ "$2" = "$3" ]; then
    ok=1
    if [ "$2" = 2 ]; then case "$rule" in E2|E5) grep -q "^FIELD DENY \[$rule\]" "$ERRF" || ok=0;; esac; fi
  fi
  if [ "$ok" = 1 ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; echo "      gate said: $(head -c 300 "$ERRF" | tr '\n' ' ')"; fail=1; fi
}
jt() { python3 -c 'import json,sys;print(json.dumps({sys.argv[1]:sys.argv[2]}))' "$1" "$2"; }   # {"<key>": "<value>"}
bj() { python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }
wr() { call "$1" Write "$(jt file_path "$2" | sed 's/}$/,"content":"x"}/')"; }                 # session path -> exit code

T=$(mktemp -d); ERRF="$T/gate.err"
LINKS=()
LINK_ERR=""
rmlink() { # never rm -rf a junction: Git Bash can follow it into the target
  if is_windows; then cmd /c "rmdir $(cygpath -w "$1")" >/dev/null 2>&1; else rm -f "$1"; fi
}
cleanup() {
  for l in "${LINKS[@]+"${LINKS[@]}"}"; do rmlink "$l"; done
  [ -n "$T" ] && rm -rf "$T"
}
trap cleanup EXIT
mklink() { # kind(junction|symlink) link target -> 0 made, 1 refused (reason in LINK_ERR)
  if is_windows; then
    local sw="/D"; [ "$1" = junction ] && sw="/J"
    case "$2$3" in *" "*) LINK_ERR="path contains a space (mklink arguments are passed unquoted): $2 -> $3"; return 1;; esac
    LINK_ERR=$(cmd /c "mklink $sw $(cygpath -w "$2") $(cygpath -w "$3")" 2>&1) || return 1
  else
    LINK_ERR=$(ln -s "$3" "$2" 2>&1) || return 1
  fi
  LINKS+=("$2")
  [ -e "$2" ] || { LINK_ERR="link created but not visible: $2"; return 1; }
}

# fixture
rm -rf .claude; mkdir -p .claude/state "$T/exdir" "$T/okdir" "$T/plain"
echo keep > "$T/exdir/sentinel"; echo keep > "$T/okdir/sentinel"; echo keep > .claude/state/sentinel
export CLAUDE_PROJECT_DIR="$HERE"
H=$(abspath "$HERE"); TA=$(abspath "$T")

if is_windows; then KINDS="junction symlink"; else KINDS="symlink"; echo "N/A  junction cases: junctions exist on Windows only"; fi
for K in $KINDS; do
  if ! mklink "$K" "$HERE/lk_$K" "$HERE/.claude/state"; then
    echo "SKIP  Windows $K cases: OS refused to create a $K"; echo "      reason: $(echo "$LINK_ERR" | head -n 1)"; continue
  fi
  mklink "$K" "$HERE/up_$K" "$HERE"
  mklink "$K" "$HERE/ex_$K" "$T/exdir"
  mklink "$K" "$HERE/ok_$K" "$T/okdir"
  mklink "$K" "$T/out_$K" "$HERE/.claude/state"
  mklink "$K" "$T/root_$K" "$HERE"
  mklink "$K" "$T/plainlk_$K" "$T/plain"

  # A. a link inside the project to the state directory (the case run_e5.sh used to skip on Windows)
  expect "E2 deny ($K): Write lk_$K/field-ledger.jsonl (link to the state dir)"        2 "$(wr a1 "lk_$K/field-ledger.jsonl")"
  expect "E2 deny ($K): Write <abs>/lk_$K/field-ledger.jsonl"                           2 "$(wr a1 "$H/lk_$K/field-ledger.jsonl")"
  expect "E2 deny ($K): Edit lk_$K/x through the link"                                  2 "$(call a1 Edit "$(jt file_path "lk_$K/x" | sed 's/}$/,"old_string":"a","new_string":"b"}/')")"
  expect "E2 deny ($K): MCP write via lk_$K"                                            2 "$(call a1 mcp__fs__write_file "$(jt path "lk_$K/field-ledger.jsonl")")"
  expect "E2 deny ($K): Bash echo x > lk_$K/field-ledger.jsonl"                         2 "$(call a1 Bash "$(bj "echo x > lk_$K/field-ledger.jsonl")")"
  expect "E2 allow ($K): control, link to a harmless dir outside the project"           0 "$(wr a1 "ok_$K/notes.txt")"
  # B. a link to the project root
  expect "E2 deny ($K): Write up_$K/field-manifest.yaml (link to the root)"             2 "$(wr b1 "up_$K/field-manifest.yaml")"
  expect "E2 deny ($K): Write up_$K/up_$K/.claude/state/x (link inside link)"           2 "$(wr b1 "up_$K/up_$K/.claude/state/x")"
  expect "E2 allow ($K): control, Write up_$K/README.md"                                0 "$(wr b1 "up_$K/README.md")"
  # C. a link OUTSIDE the project that points into it
  expect "E2 deny ($K): Write <outside>/out_$K/field-ledger.jsonl"                      2 "$(wr c1 "$TA/out_$K/field-ledger.jsonl")"
  expect "E2 allow ($K): control, Write <outside>/plainlk_$K/n.txt (link to a plain dir)" 0 "$(wr c1 "$TA/plainlk_$K/n.txt")"
  # D. a link inside the project to a directory outside it: the written file and the real path are one file (E5)
  expect "E5 write via ex_$K/x.sh allowed"                                              0 "$(wr d1 "ex_$K/x.sh")"
  expect "E5 deny ($K): bash <outside real path>/x.sh after writing it via the link"    2 "$(call d1 Bash "$(bj "bash $TA/exdir/x.sh")")"
  expect "E5 deny ($K): bash ex_$K/x.sh"                                                2 "$(call d1 Bash "$(bj "bash ex_$K/x.sh")")"
  expect "E5 write <outside real path>/y.sh allowed"                                    0 "$(wr d1 "$TA/exdir/y.sh")"
  expect "E5 deny ($K): bash ex_$K/y.sh after writing y.sh by its real path"            2 "$(call d1 Bash "$(bj "bash ex_$K/y.sh")")"
  expect "E5 allow ($K): control, another session runs <outside real path>/x.sh"       0 "$(call d2 Bash "$(bj "bash $TA/exdir/x.sh")")"
  # E. the project root itself reached through a link (what run_e5.sh:64 tests: a symlinked project root)
  expect "E5 write x.sh with the root behind a $K"                                      0 "$(CLAUDE_PROJECT_DIR=$TA/root_$K wr e1 x.sh)"
  expect "E5 deny ($K): bash <link to root>/x.sh"                                       2 "$(CLAUDE_PROJECT_DIR=$H call e1 Bash "$(bj "bash $TA/root_$K/x.sh")")"
  expect "E5 deny ($K): bash <real root>/x.sh with CLAUDE_PROJECT_DIR the link"         2 "$(CLAUDE_PROJECT_DIR=$TA/root_$K call e1 Bash "$(bj "bash $H/x.sh")")"
  expect "E2 deny ($K): root behind a link, Write .claude/state/field-ledger.jsonl"     2 "$(CLAUDE_PROJECT_DIR=$TA/root_$K wr e2 .claude/state/field-ledger.jsonl)"
  expect "E2 deny ($K): root behind a link, Write <real root>/field-manifest.yaml"      2 "$(CLAUDE_PROJECT_DIR=$TA/root_$K wr e2 "$H/field-manifest.yaml")"
  expect "E2 deny ($K): root behind a link, Write field-manifest.yaml"                  2 "$(CLAUDE_PROJECT_DIR=$TA/root_$K wr e2 field-manifest.yaml)"
done

# F. Windows spellings of one file (ADR-0080 / proposal 02 item M1). Not reachable on POSIX, where they are different names.
if is_windows; then
  W=$(cygpath -w "$HERE")                       # C:\...\test
  M="field-manifest.yaml"; L=".claude/state/field-ledger.jsonl"
  expect "E2 deny (ADS): Write $M::\$DATA"                       2 "$(wr f1 "$H/$M::\$DATA")"
  expect "E2 deny (ADS): Write $L:ads"                           2 "$(wr f1 "$H/$L:ads")"
  expect "E2 deny (ADS): Write relative $M::\$DATA"              2 "$(wr f1 "$M::\$DATA")"
  expect "E2 deny (ADS): Write .claude/state::\$INDEX_ALLOCATION/x" 2 "$(wr f1 "$H/.claude/state::\$INDEX_ALLOCATION/x")"
  expect "E2 deny (trailing dot): Write $M."                     2 "$(wr f2 "$H/$M.")"
  expect "E2 deny (trailing space): Write '$M '"                 2 "$(wr f2 "$H/$M ")"
  expect "E2 deny (trailing dot in a directory): Write .claude./state/x" 2 "$(wr f2 "$H/.claude./state/x")"
  expect "E2 deny (backslashes): Write $W\\.claude\\state\\x"    2 "$(wr f3 "$W\\.claude\\state\\x")"
  expect "E2 deny (\\\\?\\ prefix): Write \\\\?\\$W\\.claude\\state\\x" 2 "$(wr f3 "\\\\?\\$W\\.claude\\state\\x")"
  expect "E2 deny (\\\\?\\ prefix): Write \\\\?\\$W\\$M"          2 "$(wr f3 "\\\\?\\$W\\$M")"
  expect "E2 deny (//?/ prefix): Write //?/$H/$M"                2 "$(wr f3 "//?/$H/$M")"
  expect "E2 allow: control, Write notes.txt::\$DATA"            0 "$(wr f4 "$H/notes.txt::\$DATA")"
  expect "E2 allow: control, Write notes.txt:ads"                0 "$(wr f4 "$H/notes.txt:ads")"
  expect "E2 allow: control, Write \\\\?\\$W\\notes.txt"         0 "$(wr f4 "\\\\?\\$W\\notes.txt")"
  # 8.3 short names. The fixture is a second project under the temp directory, created now, so the case does not depend
  # on whether the volume holding the checkout generates 8.3 names (the hosted runner's D: does not). GetShortPathNameW
  # (python) reports the alias; if the temp volume has none either, the case prints an explicit SKIP.
  P="$T/long project directory"; PA=$(abspath "$P"); mkdir -p "$P/.claude/state"; cp field-manifest.yaml "$P/"
  W=$(cygpath -w "$P")
  SHORT=$(python3 - "$W" <<'PYEOF'
import ctypes, os, sys
w = sys.argv[1]
def short(p):
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(p, buf, 1024)
    return buf.value if n else ""
print(short(os.path.join(w, ".claude")) or "-")
print(short(os.path.join(w, "field-manifest.yaml")) or "-")
PYEOF
)
  SD=$(echo "$SHORT" | sed -n 1p | tr -d '\r'); SM=$(echo "$SHORT" | sed -n 2p | tr -d '\r')
  if [ "$SD" != "-" ] && [ "$(basename "$(cygpath -u "$SD")")" != ".claude" ]; then
    expect "E2 deny (8.3): Write $(basename "$(cygpath -u "$SD")")/state/field-ledger.jsonl" 2 "$(CLAUDE_PROJECT_DIR=$PA wr g1 "$(cygpath -m "$SD")/state/field-ledger.jsonl")"
  else
    echo "SKIP  8.3 short name of .claude: volume has 8.3 name generation off"; echo "      reason: GetShortPathNameW returned no alias for $W\\.claude"
  fi
  if [ "$SM" != "-" ] && [ "$(basename "$(cygpath -u "$SM")")" != "field-manifest.yaml" ]; then
    expect "E2 deny (8.3): Write $(basename "$(cygpath -u "$SM")")" 2 "$(CLAUDE_PROJECT_DIR=$PA wr g1 "$(cygpath -m "$SM")")"
  else
    echo "SKIP  8.3 short name of field-manifest.yaml: volume has 8.3 name generation off"; echo "      reason: GetShortPathNameW returned no alias for $W\\field-manifest.yaml"
  fi
else
  echo "N/A  Windows path aliases (::\$DATA streams, \\\\?\\ prefix, trailing dot/space, 8.3 names): they are ordinary names on POSIX"
fi

# H. cleanup must not have followed a link into its target (tests the rmlink helper too)
for l in "${LINKS[@]+"${LINKS[@]}"}"; do rmlink "$l"; done; LINKS=()
[ -f "$T/exdir/sentinel" ] && [ -f "$T/okdir/sentinel" ] && [ -f "$HERE/.claude/state/sentinel" ] && [ -f "$HERE/field-manifest.yaml" ] \
  && echo "PASS  removing the test links left every link target intact" || { echo "FAIL  a link target lost files when links were removed"; fail=1; }
rm -rf .claude
[ "$fail" = 0 ] && echo "ALL LINK TESTS PASSED" || { echo "LINK TESTS FAILED"; exit 1; }
