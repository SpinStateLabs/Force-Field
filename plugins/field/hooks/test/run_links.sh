#!/usr/bin/env bash
# Link and Windows path-alias tests (ADR-0080). Run from anywhere:  bash hooks/test/run_links.sh
# A symlink or a Windows junction must not hide a governance path (E2) or a session-written file (E5) from the
# gate. On Windows the gate also has to see through the other spellings Win32 treats as the same file: a
# \\?\ prefix, an NTFS stream (file::$DATA), a trailing dot or space, and an 8.3 short name.
#   junction: created with `mklink /J` (no privilege needed). symlink: `mklink /D` on Windows, `ln -s` on POSIX.
#   A case that cannot run (the OS refuses to create a link, the volume has no 8.3 names, a volume or device path cannot be
#   read) is a FAIL, never a SKIP: an unexamined alias is an unproven control. The CI SKIP allowlist (skip-allowlist-windows.txt,
#   checked by run_all.sh) holds only the ledger mode check in run_e5.sh.
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
expect() { # label expected actual; a deny must also come from the rule the label names (E0, E2 or E5); a FAIL shows the gate's reason
  local rule; rule=${1%% *}; local ok=0
  if [ "$2" = "$3" ]; then
    ok=1
    if [ "$2" = 2 ]; then case "$rule" in E0|E2|E5) grep -q "^FIELD DENY \[$rule\]" "$ERRF" || ok=0;; esac; fi
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
  if is_windows; then cmd /c "rmdir $(cygpath -w "$1")" >/dev/null 2>&1 || cmd /c "del $(cygpath -w "$1")" >/dev/null 2>&1; else rm -f "$1"; fi
}
cleanup() {
  for l in "${LINKS[@]+"${LINKS[@]}"}"; do rmlink "$l"; done
  [ -n "$T" ] && rm -rf "$T"
}
trap cleanup EXIT
mklinkf() { # link target: a FILE symlink, target may not exist (dangling). 0 made, 1 refused
  if is_windows; then
    LINK_ERR=$(cmd /c "mklink $(cygpath -w "$1") $(cygpath -w "$2")" 2>&1) || return 1
  else
    LINK_ERR=$(ln -s "$2" "$1" 2>&1) || return 1
  fi
  LINKS+=("$1")
}
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
# a second governed project with a manifest rule anchored at its root (protected_paths ^secrets/)
P2="$T/proj2"; P2A=$(abspath "$P2"); mkdir -p "$P2/.claude/state" "$P2/secrets" "$P2/other"
sed "s|protected_paths: \[\]|protected_paths: ['^secrets/']|" field-manifest.yaml > "$P2/field-manifest.yaml"
grep -q "secrets/" "$P2/field-manifest.yaml" || { echo "FAIL  fixture: protected_paths rule not written"; fail=1; }

if is_windows; then KINDS="junction symlink"; else KINDS="symlink"; echo "N/A  junction cases: junctions exist on Windows only"; fi
for K in $KINDS; do
  if ! mklink "$K" "$HERE/lk_$K" "$HERE/.claude/state"; then
    echo "FAIL  $K cases cannot run: OS refused to create a $K (Windows: run elevated or enable Developer Mode)"; echo "      reason: $(echo "$LINK_ERR" | head -n 1)"; fail=1; continue
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
  # E2'. a manifest rule anchored at the project root, reached by its real path while the root is given as a link:
  # only a resolved root makes <real root>/secrets/x root-relative, so this case turns red when root resolution is dropped.
  mklink "$K" "$T/rp_$K" "$P2"
  expect "E2 deny ($K): custom protected path ^secrets/ via <real root>/secrets/x, root given as a link" 2 "$(CLAUDE_PROJECT_DIR=$TA/rp_$K wr h1 "$P2A/secrets/x")"
  expect "E2 deny ($K): custom protected path ^secrets/ via <link>/secrets/x"            2 "$(CLAUDE_PROJECT_DIR=$TA/rp_$K wr h1 "$TA/rp_$K/secrets/x")"
  expect "E2 allow ($K): control, <real root>/other/x with the same root link"          0 "$(CLAUDE_PROJECT_DIR=$TA/rp_$K wr h1 "$P2A/other/x")"
  # N1. dangling links to a protected place that does not exist yet (the strict open fails with "not found" on them)
  if [ "$K" = junction ]; then
    mkdir -p "$HERE/.claude/state/newd"
    mklink junction "$HERE/dj" "$HERE/.claude/state/newd"; rmdir "$HERE/.claude/state/newd"
    expect "E2 deny (dangling junction): Write dj/x, target .claude/state/newd was removed"   2 "$(wr n1 "dj/x")"
    expect "E2 deny (dangling junction): Bash echo x > dj/x"                                  2 "$(call n1 Bash "$(bj "echo x > dj/x")")"
    mkdir -p "$P2/secrets/newd"; mklink junction "$P2/dd" "$P2/secrets/newd"; rmdir "$P2/secrets/newd"
    expect "E2 deny (dangling junction): manifest rule ^secrets/ via dd/x"                    2 "$(CLAUDE_PROJECT_DIR=$P2A wr n2 "dd/x")"
  else
    if mklinkf "$HERE/dl_state" "$HERE/.claude/state/newf" && mklinkf "$HERE/dl_set" "$HERE/.claude/settings.json"; then
      expect "E2 deny (dangling symlink): Write dl_state, target .claude/state/newf does not exist" 2 "$(wr n1 "dl_state")"
      expect "E2 deny (dangling symlink): Write <abs>/dl_state"                                2 "$(wr n1 "$H/dl_state")"
      expect "E2 deny (dangling symlink): Write dl_set -> .claude/settings.json"               2 "$(wr n1 "dl_set")"
      expect "E2 deny (dangling symlink): Edit dl_set"                                         2 "$(call n1 Edit "$(jt file_path dl_set | sed 's/}$/,"old_string":"a","new_string":"b"}/')")"
      if is_windows; then   # POSIX: bare words are not link-resolved (unchanged); see the README register
        expect "E2 deny (dangling symlink): Bash echo x >> dl_state (bare name)"                 2 "$(call n1 Bash "$(bj "echo x >> dl_state")")"
        expect "E2 deny (dangling symlink): Bash tee -a dl_state (bare name)"                    2 "$(call n1 Bash "$(bj "echo x | tee -a dl_state")")"
        expect "E2 deny (dangling symlink): PowerShell Set-Content -Path dl_state"               2 "$(call n1 PowerShell "$(bj "Set-Content -Path dl_state -Value x")")"
      fi
    else
      echo "FAIL  dangling file symlinks cannot be made: $(echo "$LINK_ERR" | head -n 1)"; fail=1
    fi
    mklink symlink "$P2/lnk_dd" "$P2/secrets/newd" >/dev/null 2>&1
    expect "E2 deny (dangling dir symlink): manifest rule ^secrets/ via lnk_dd/x"             2 "$(CLAUDE_PROJECT_DIR=$P2A wr n2 "lnk_dd/x")"
  fi
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
  # (python) reports the alias; if the temp volume has none either the case FAILs (it cannot be examined).
  P="$T/long project directory"; PA=$(abspath "$P"); mkdir -p "$P/.claude/state" "$P/secrets"; sed "s|protected_paths: \[\]|protected_paths: ['^secrets/']|" field-manifest.yaml > "$P/field-manifest.yaml"
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
    echo "FAIL  8.3 short name of .claude cannot be examined: the volume has 8.3 name generation off"; echo "      reason: GetShortPathNameW returned no alias for $W\\.claude"; fail=1
  fi
  if [ "$SM" != "-" ] && [ "$(basename "$(cygpath -u "$SM")")" != "field-manifest.yaml" ]; then
    expect "E2 deny (8.3): Write $(basename "$(cygpath -u "$SM")")" 2 "$(CLAUDE_PROJECT_DIR=$PA wr g1 "$(cygpath -m "$SM")")"
  else
    echo "FAIL  8.3 short name of field-manifest.yaml cannot be examined: the volume has 8.3 name generation off"; echo "      reason: GetShortPathNameW returned no alias for $W\\field-manifest.yaml"; fail=1
  fi
  W0=$(cygpath -w "$HERE")

  # F2. NON-EXISTING targets: Python's realpath cleans a stream, a trailing dot or space only on a path that exists, so these
  # fail when _win_clean is dropped. .claude/settings.json is a built-in E2 name ($-anchored) and does not exist here.
  S=".claude/settings.json"
  expect "E2 deny (non-existing, ADS): Write $S::\$DATA"                2 "$(wr i1 "$H/$S::\$DATA")"
  expect "E2 deny (non-existing, ADS): Write .claude/settings.local.json:ads" 2 "$(wr i1 "$H/.claude/settings.local.json:ads")"
  expect "E2 deny (non-existing, trailing dot): Write $S."              2 "$(wr i1 "$H/$S.")"
  expect "E2 deny (non-existing, trailing space): Write '$S '"          2 "$(wr i1 "$H/$S ")"
  expect "E2 deny (non-existing, //?/ prefix): Write //?/$H/$S"         2 "$(wr i1 "//?/$H/$S")"
  expect "E2 deny (non-existing, \\\\?\\ prefix): Write \\\\?\\$W0\\.claude\\settings.json" 2 "$(wr i1 "\\\\?\\$W0\\.claude\\settings.json")"
  expect "E2 deny (non-existing, .claude. directory): Write .claude./settings.json" 2 "$(wr i1 "$H/.claude./settings.json")"
  expect "E2 allow: control, '.claude/.../settings.json' (three dots is a real, different name)" 0 "$(wr i2 "$H/.claude/.../settings.json")"
  expect "E2 allow: control, shell token http://host:80/a is not mangled" 0 "$(call i2 Bash "$(bj "echo http://host:80/a")")"
  expect "E2 allow: control, shell token PATH=/a:/b is not mangled"      0 "$(call i2 Bash "$(bj "echo PATH=/a:/b")")"

  # G. spellings of the same place that the gate cannot map to a drive-letter path: it must refuse them (E0), not allow.
  # The volume GUID and the GLOBALROOT device path are read from the OS for the checkout's own volume, and each is first shown to
  # be live (it opens the manifest); if the OS cannot give them, that is a FAIL, not a skip.
  R0=${W0#?:}                                           # \Users\...\test  (no drive)
  DRV=${W0%%:*}
  ALIAS=$(python3 - "$W0" <<'PYEOF'
import ctypes, os, sys
w = sys.argv[1]
drive = w[:2]
buf = ctypes.create_unicode_buffer(1024)
guid = buf.value if ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(drive + "\\", buf, 1024) else ""
dev = ctypes.create_unicode_buffer(1024)
dev = dev.value if ctypes.windll.kernel32.QueryDosDeviceW(drive, dev, 1024) else ""
rest = w[2:]
ok = lambda p: os.path.exists(p + "\\field-manifest.yaml")
g = guid.rstrip("\\") + rest if guid else ""
d1 = "\\\\?\\GLOBALROOT" + dev + rest if dev else ""
d2 = "\\\\.\\GLOBALROOT" + dev + rest if dev else ""
for name, p in (("guid", g), ("globalroot", d1), ("globalroot_dot", d2)):
    print(name + "=" + (p if p and ok(p) else "-"))
PYEOF
)
  for nm in guid globalroot globalroot_dot; do
    v=$(echo "$ALIAS" | tr -d '\r' | sed -n "s/^$nm=//p")
    if [ -z "$v" ] || [ "$v" = "-" ]; then echo "FAIL  $nm alias of the checkout cannot be examined: the OS did not give a path that opens field-manifest.yaml"; fail=1; continue; fi
    expect "E0 deny ($nm): Write $v\\.claude\\state\\x" 2 "$(wr j1 "$v\\.claude\\state\\x")"
    F=$(echo "$v" | tr '\\' '/')   # Bash reads backslashes as escapes: its form is //?/Volume{..}/...
    expect "E0 deny ($nm): Write $v\\field-manifest.yaml" 2 "$(wr j1 "$v\\field-manifest.yaml")"
    expect "E0 deny ($nm): Bash echo x > $F/.claude/state/x" 2 "$(call j1 Bash "$(bj "echo x > $F/.claude/state/x")")"
    expect "E0 deny ($nm): E5 exec of x.sh through the alias (after writing it by its real path)" 2 "$(wr j2 "$H/ax.sh" >/dev/null; call j2 Bash "$(bj "bash $F/ax.sh")")"
  done
  U1="\\\\localhost\\$DRV\$$R0"; U2="\\\\127.0.0.1\\$DRV\$$R0"; U3="\\\\?\\UNC\\localhost\\$DRV\$$R0"; U4="//localhost/$DRV\$$(echo "$R0" | tr '\\' '/')"
  for u in "$U1" "$U2" "$U3" "$U4"; do
    expect "E0 deny (UNC admin share): Write $u\\.claude\\state\\x" 2 "$(wr k1 "$u\\.claude\\state\\x")"
    expect "E0 deny (UNC admin share): Write $u/field-manifest.yaml" 2 "$(wr k1 "$u/field-manifest.yaml")"
  done
  expect "E0 deny (UNC, Bash): echo x > //localhost/C\\\$/.../.claude/state/x" 2 "$(call k2 Bash "$(bj "echo x > $U4/.claude/state/x")")"
  expect "E0 deny (UNC, PowerShell): Set-Content \\\\localhost\\C\$\\...\\.claude\\state\\x" 2 "$(call k2 PowerShell "$(bj "Set-Content -Path $U1\\.claude\\state\\x -Value x")")"
  expect "E0 deny (UNC, E5): bash <UNC>/ax.sh after writing ax.sh by its real path" 2 "$(wr k3 "$H/ax.sh" >/dev/null; call k3 Bash "$(bj "bash $U4/ax.sh")")"
  expect "E0 deny (drive-relative): Write C:.claude\\state\\x"           2 "$(wr l1 "$DRV:.claude\\state\\x")"
  expect "E0 deny (drive-relative): Write C:.claude/state/x"             2 "$(wr l1 "$DRV:.claude/state/x")"
  expect "E0 deny (drive-relative, PowerShell): Set-Content C:.claude\\state\\x" 2 "$(call l1 PowerShell "$(bj "Set-Content -Path $DRV:.claude\\state\\x -Value x")")"

  # K. directory attribute names, the NT prefix, doubled UNC separators, a link spelled in another case, a bare-drive root
  expect "E2 deny (:\$I30): Write .claude/state:\$I30/newfile"                         2 "$(wr o1 "$H/.claude/state:\$I30/newfile")"
  expect "E2 deny (:\$I30): Write relative .claude/state:\$I30/newfile"                2 "$(wr o1 ".claude/state:\$I30/newfile")"
  expect "E2 deny (:\$I30:\$INDEX_ALLOCATION): Write .claude/state:\$I30:\$INDEX_ALLOCATION/newfile" 2 "$(wr o1 "$H/.claude/state:\$I30:\$INDEX_ALLOCATION/newfile")"
  expect "E2 deny (:\$I30, Bash): echo x > .claude/state:\$I30/newfile"                 2 "$(call o1 Bash "$(bj "echo x > .claude/state:\$I30/newfile")")"
  expect "E2 deny (:\$I30, PowerShell): Set-Content .claude\\state:\$I30\\newfile"       2 "$(call o1 PowerShell "$(bj "Set-Content -Path .claude\\state:\$I30\\newfile -Value x")")"
  expect "E2 deny (:\$I30): manifest rule ^secrets/ via secrets:\$I30/newfile"           2 "$(CLAUDE_PROJECT_DIR=$P2A wr o2 "secrets:\$I30/newfile")"
  expect "E2 deny (:\$I30): manifest rule ^secrets/ via <abs>/secrets:\$I30:\$INDEX_ALLOCATION/newfile" 2 "$(CLAUDE_PROJECT_DIR=$P2A wr o2 "$P2A/secrets:\$I30:\$INDEX_ALLOCATION/newfile")"
  expect "E2 allow: control, manifest rule ^secrets/ does not cover other/x:\$I30"      0 "$(CLAUDE_PROJECT_DIR=$P2A wr o2 "other:\$I30/x")"
  expect "E2 deny (NT prefix): Write \\??\\$W0\\.claude\\state\\x"                      2 "$(wr p1 "\\??\\$W0\\.claude\\state\\x")"
  expect "E2 deny (NT prefix, Bash): echo x > /??/$H/.claude/state/x"                    2 "$(call p1 Bash "$(bj "echo x > /??/$H/.claude/state/x")")"
  expect "E2 deny (NT prefix, PowerShell): Set-Content \\??\\$W0\\.claude\\state\\x"    2 "$(call p1 PowerShell "$(bj "Set-Content -Path \\??\\$W0\\.claude\\state\\x -Value x")")"
  expect "E2 allow: control, Write \\??\\$W0\\notes.txt"                                 0 "$(wr p2 "\\??\\$W0\\notes.txt")"
  expect "E0 deny (NT prefix, volume): Write \\??\\Volume{00000000-0000-0000-0000-000000000000}\\x" 2 "$(wr p1 "\\??\\Volume{00000000-0000-0000-0000-000000000000}\\x")"
  expect "E0 deny (NT prefix, UNC): Write \\??\\UNC\\localhost\\$DRV\$$R0\\.claude\\state\\x" 2 "$(wr p1 "\\??\\UNC\\localhost\\$DRV\$$R0\\.claude\\state\\x")"
  expect "E0 deny (doubled separator): Write \\\\localhost\\\\$DRV\$$R0\\.claude\\state\\x" 2 "$(wr p3 "\\\\localhost\\\\$DRV\$$R0\\.claude\\state\\x")"
  expect "E0 deny (doubled separator): Write //localhost//$DRV\$/.../.claude/state/x"   2 "$(wr p3 "//localhost//$DRV\$$(echo "$R0" | tr '\\' '/')/.claude/state/x")"
  expect "E0 deny (doubled separator, Bash): echo x > //localhost//$DRV\$/..."          2 "$(call p3 Bash "$(bj "echo x > //localhost//$DRV\$$(echo "$R0" | tr '\\' '/')/.claude/state/x")")"
  mklink junction "$HERE/lkc" "$HERE/.claude/state"
  expect "E2 deny (case): Write LKC/field-ledger.jsonl, junction made as lkc"           2 "$(wr q1 "LKC/field-ledger.jsonl")"
  expect "E2 deny (case): Bash echo x > Lkc/x"                                          2 "$(call q1 Bash "$(bj "echo x > Lkc/x")")"
  expect "E2 deny (bare drive root): CLAUDE_PROJECT_DIR=$DRV: Write field-manifest.yaml" 2 "$(cd "$HERE"; CLAUDE_PROJECT_DIR="$DRV:" wr q2 "field-manifest.yaml")"
  expect "E2 allow (bare drive root): control, Write notes.txt"                          0 "$(cd "$HERE"; CLAUDE_PROJECT_DIR="$DRV:" wr q2 "notes.txt")"

  # 8.3: a dangling junction whose target is under a rule, the project root given in long form and the path in short form, and the
  # reverse. Lenient realpath leaves 8.3 names in the missing tail, so the target must be resolved again.
  PS=$(python3 -c 'import ctypes,sys;b=ctypes.create_unicode_buffer(1024);ctypes.windll.kernel32.GetShortPathNameW(sys.argv[1],b,1024);print(b.value)' "$W" | tr -d '\r')
  if [ -n "$PS" ] && [ "$(basename "$(cygpath -u "$PS")")" != "long project directory" ]; then
    PSM=$(cygpath -m "$PS")
    mkdir -p "$P/secrets/newd"; mklink junction "$PSM/dj" "$PSM/secrets/newd" || { echo "FAIL  could not make the 8.3 dangling junction: $LINK_ERR"; fail=1; }; rmdir "$P/secrets/newd"
    expect "E2 deny (8.3 + dangling junction): root long, path via short name"  2 "$(CLAUDE_PROJECT_DIR=$PA wr r1 "$PSM/dj/x")"
    expect "E2 deny (8.3 + dangling junction): root short, path via long name"  2 "$(CLAUDE_PROJECT_DIR=$PSM wr r1 "$PA/dj/x")"
    expect "E2 deny (8.3 root): rule ^secrets/ with the root given as a short name" 2 "$(CLAUDE_PROJECT_DIR=$PSM wr r1 "$PA/secrets/x")"
  else
    echo "FAIL  8.3 short name of the fixture project cannot be examined"; fail=1
  fi

  # J. a symlink or junction loop: Python's lenient realpath returns the path unresolved for it (a gate that relied on it would
  # allow); the gate resolves strictly and must deny. Junction loop: A -> S, B -> A, drop A, A -> B.
  mkdir -p "$T/loopS"
  cmd /c "mklink /J $(cygpath -w "$T/loopA") $(cygpath -w "$T/loopS")" >/dev/null && cmd /c "mklink /J $(cygpath -w "$T/loopB") $(cygpath -w "$T/loopA")" >/dev/null \
    && cmd /c "rmdir $(cygpath -w "$T/loopA")" >/dev/null && cmd /c "mklink /J $(cygpath -w "$T/loopA") $(cygpath -w "$T/loopB")" >/dev/null \
    && LINKS+=("$T/loopA" "$T/loopB") && echo "PASS  junction loop built (loopA -> loopB -> loopA)" || { echo "FAIL  could not build a junction loop"; fail=1; }
  expect "E0 deny (junction loop): Write <outside>/loopA/x"              2 "$(wr m1 "$TA/loopA/x")"
  cmd /c "mklink /D $(cygpath -w "$T/symA") $(cygpath -w "$T/symB")" >/dev/null 2>&1 && cmd /c "mklink /D $(cygpath -w "$T/symB") $(cygpath -w "$T/symA")" >/dev/null 2>&1 \
    && LINKS+=("$T/symA" "$T/symB") && echo "PASS  symlink loop built (symA -> symB -> symA)" || { echo "FAIL  could not build a symlink loop (symlinks need Developer Mode or elevation)"; fail=1; }
  expect "E0 deny (symlink loop): Write <outside>/symA/x"                2 "$(wr m1 "$TA/symA/x")"

else
  echo "N/A  Windows path aliases (::\$DATA streams, \\\\?\\ prefix, trailing dot/space, 8.3 names): they are ordinary names on POSIX"
fi

# I. unit tests of the path canonicalisation (_win_clean table, fail-closed forms, POSIX byte-identity)
python3 "$(abspath "$HERE")/test_path_canon.py" || fail=1

# H. cleanup must not have followed a link into its target (tests the rmlink helper too)
for l in "${LINKS[@]+"${LINKS[@]}"}"; do rmlink "$l"; done; LINKS=()
[ -f "$T/exdir/sentinel" ] && [ -f "$T/okdir/sentinel" ] && [ -f "$HERE/.claude/state/sentinel" ] && [ -f "$HERE/field-manifest.yaml" ] \
  && echo "PASS  removing the test links left every link target intact" || { echo "FAIL  a link target lost files when links were removed"; fail=1; }
rm -rf .claude
[ "$fail" = 0 ] && echo "ALL LINK TESTS PASSED" || { echo "LINK TESTS FAILED"; exit 1; }
