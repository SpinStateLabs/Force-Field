#!/usr/bin/env bash
# Shell-form tests (PR 15, after the third review of PR 14). Run from anywhere:  bash hooks/test/run_shell_forms.sh
#   1. `cmd /c '<payload>'` and `cmd.exe /k ...`: the quoted payload is re-tokenised like `bash -c`, so a write to a
#      governance file inside it is an E2 deny (exit 0 before the fix).
#   2. PowerShell colon-bound parameters: -Path:x, -LiteralPath:x, -Destination:x bind the value to the flag with a
#      colon; the value is resolved like any path.
#   3. A word of a single letter, a colon and more colons (a:b:c) is not a drive-relative path unless that drive
#      exists: no E0 false deny. A real drive-relative word on an existing drive still denies (run_links.sh).
#   4. Bare words that name a link: a name that starts with '-' or holds ? * " < > | (POSIX), and a glob (led? led*
#      l[e]d) that matches a link of the project root, are resolved like paths.
# Prints PASS/FAIL per case and exits non-zero if any case fails.
set -u
cd "$(dirname "$0")"
HERE="$PWD"
fail=0
is_windows() { case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0;; *) return 1;; esac; }
if is_windows; then export MSYS2_ARG_CONV_EXCL='*'; fi
abspath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf %s "$1"; fi; }
G=$(abspath "$HERE/..")/field-gate.py
T=$(mktemp -d); ERRF="$T/gate.err"
trap 'rm -rf "$T"' EXIT
P="$T/p"; mkdir -p "$P/.claude/state" "$P/other"
cp field-manifest.yaml "$P/field-manifest.yaml"
export CLAUDE_PROJECT_DIR="$P"
call() { # session tool json-input -> exit code (an exit 2 counts as a deny only when the gate said so)
  printf '{"session_id":"%s","tool_name":"%s","tool_input":%s}' "$1" "$2" "$3" | python3 "$G" >/dev/null 2>"$ERRF"; local rc=$?
  if [ "$rc" = 2 ] && ! grep -q '^FIELD DENY \[' "$ERRF"; then rc=99; fi
  echo "$rc"
}
expect() { # label expected actual [rule]: a deny must come from the named rule
  local ok=0
  if [ "$2" = "$3" ]; then ok=1; if [ "$2" = 2 ] && [ -n "${4:-}" ]; then grep -q "^FIELD DENY \[$4\]" "$ERRF" || ok=0; fi; fi
  if [ "$ok" = 1 ]; then echo "PASS  $1"; else echo "FAIL  $1 (expected $2, got $3)"; echo "      gate said: $(head -c 300 "$ERRF" | tr '\n' ' ')"; fail=1; fi
}
bj() { python3 -c 'import json,sys;print(json.dumps({"command":sys.argv[1]}))' "$1"; }
BS=$(printf '\\')
bash_() { call s1 Bash "$(bj "$1")"; }
ps_() { call s2 PowerShell "$(bj "$1")"; }

# 1. cmd /c
expect "E2 deny: cmd /c 'echo {} > .claude\\settings.local.json'"  2 "$(bash_ "cmd /c 'echo {} > .claude${BS}settings.local.json'")" E2
expect "E2 deny: cmd /c 'echo x > .claude/state/secret.txt'"       2 "$(bash_ "cmd /c 'echo x > .claude/state/secret.txt'")" E2
expect "E2 deny: cmd /c 'type nul > field-manifest.yaml'"          2 "$(bash_ "cmd /c 'type nul > field-manifest.yaml'")" E2
expect "E2 deny: cmd.exe /C \"del field-manifest.yaml\""            2 "$(bash_ 'cmd.exe /C "del field-manifest.yaml"')" E2
expect "E2 deny: cmd /k 'echo x > .claude/state/x'"                2 "$(bash_ "cmd /k 'echo x > .claude/state/x'")" E2
expect "E2 deny: sudo cmd /c 'echo x > field-manifest.yaml'"       2 "$(bash_ "sudo cmd /c 'echo x > field-manifest.yaml'")" E2
# 1b. review 3 of PR 15: Git Bash's //c, switch case and combined switches, cmd's ^ escape, del/erase and globs
expect "E2 deny: cmd //c 'echo x > field-manifest.yaml' (MSYS spelling of /c)"  2 "$(bash_ "cmd //c 'echo x > field-manifest.yaml'")" E2
expect "E2 deny: cmd.exe //C 'echo x > field-manifest.yaml'"                     2 "$(bash_ "cmd.exe //C 'echo x > field-manifest.yaml'")" E2
expect "E2 deny: cmd //c 'echo x > .claude\state\f'"                           2 "$(bash_ "cmd //c 'echo x > .claude${BS}state${BS}f'")" E2
expect "E2 deny: cmd /d /s /v:on /c 'echo x > field-manifest.yaml' (combined)"   2 "$(bash_ "cmd /d /s /v:on /c 'echo x > field-manifest.yaml'")" E2
expect "E2 deny: cmd /K 'echo x > field-manifest.yaml' (upper case)"             2 "$(bash_ "cmd /K 'echo x > field-manifest.yaml'")" E2
expect "E2 deny: cmd /r 'echo x > field-manifest.yaml'"                          2 "$(bash_ "cmd /r 'echo x > field-manifest.yaml'")" E2
expect "E2 deny: cmd /c 'echo x > field-manifest.ya^ml' (caret escape)"          2 "$(bash_ "cmd /c 'echo x > field-manifest.ya^ml'")" E2
expect "E2 deny: cmd /c 'echo x > field-m^anifest.yaml'"                         2 "$(bash_ "cmd /c 'echo x > field-m^anifest.yaml'")" E2
expect "E2 deny: cmd /c 'echo x > .claude\sta^te\a'"                           2 "$(bash_ "cmd /c 'echo x > .claude${BS}sta^te${BS}a'")" E2
expect "E2 deny: cmd /c 'del field-manifest.yam^l'"                              2 "$(bash_ "cmd /c 'del field-manifest.yam^l'")" E2
expect "E2 deny: cmd /c 'del field-manifest.*' (glob, aligned with rm)"          2 "$(bash_ "cmd /c 'del field-manifest.*'")" E2
expect "E2 deny: cmd /c 'del /q /f field-manifest.yaml'"                         2 "$(bash_ "cmd /c 'del /q /f field-manifest.yaml'")" E2
expect "E2 deny: cmd /c 'echo a & move other\x field-manifest.yaml'"              2 "$(bash_ "cmd /c 'echo a & move other${BS}x field-manifest.yaml'")" E2
expect "E2 deny (PowerShell): cmd /c \"echo x > field-manifest.ya^ml\""          2 "$(ps_ 'cmd /c "echo x > field-manifest.ya^ml"')" E2
# 1c. second review of PR 15: glued switches, rd /s, cmd as a pipe sink, escaped quotes, each cmd file command
expect "E2 deny: cmd /c\"echo x > field-manifest.yaml\" (switch glued to the quote)"  2 "$(bash_ 'cmd /c"echo x > field-manifest.yaml"')" E2
expect "E2 deny: cmd \"/c echo x > field-manifest.yaml\" (switch inside the first arg)" 2 "$(bash_ 'cmd "/c echo x > field-manifest.yaml"')" E2
expect "E2 deny: cmd /d //c\"echo x > field-manifest.yaml\""                          2 "$(bash_ 'cmd /d //c"echo x > field-manifest.yaml"')" E2
expect "E2 deny: cmd /c del field-manifest.yaml (unquoted: every word after /c)"       2 "$(bash_ 'cmd /c del field-manifest.yaml')" E2
expect "E2 deny: cmd /c \"del\\\"field-manifest.yaml\\\"\" (escaped quotes)"            2 "$(bash_ 'cmd /c "del\"field-manifest.yaml\""')" E2
expect "E2 deny: cmd /c \"rd /s /q .claude\" (recursive removal of .claude)"           2 "$(bash_ 'cmd /c "rd /s /q .claude"')" E2
expect "E2 deny: cmd /c \"rmdir /s /q .claude\""                                       2 "$(bash_ 'cmd /c "rmdir /s /q .claude"')" E2
expect "E2 deny: cmd /c \"rd /s /q .\" (the project directory)"                        2 "$(bash_ 'cmd /c "rd /s /q ."')" E2
expect "E2 deny: cmd /c rd /s /q .claude (unquoted)"                                    2 "$(bash_ 'cmd /c rd /s /q .claude')" E2
expect "E2 deny (PowerShell): cmd /c \"rd /s /q .claude\""                             2 "$(ps_ 'cmd /c "rd /s /q .claude"')" E2
expect "E2 deny (PowerShell): cmd.exe /d /c \"rd /s /q .\""                            2 "$(ps_ 'cmd.exe /d /c "rd /s /q ."')" E2
expect "E2 allow: cmd /c \"rd /s /q other\" (control)"                                 0 "$(bash_ 'cmd /c "rd /s /q other"')"
expect "E2 allow (PowerShell): cmd /c \"rd /s /q other\" (control)"                    0 "$(ps_ 'cmd /c "rd /s /q other"')"
expect "E2 deny: echo \"echo x > field-manifest.yaml\" | cmd (cmd reads stdin)"         2 "$(bash_ 'echo "echo x > field-manifest.yaml" | cmd')" E2
expect "E2 deny: echo \"del field-manifest.*\" | cmd.exe"                              2 "$(bash_ 'echo "del field-manifest.*" | cmd.exe')" E2
expect "E2 allow: echo \"echo hi > notes.txt\" | cmd (control)"                        0 "$(bash_ 'echo "echo hi > notes.txt" | cmd')"
# each cmd file command is read as its Bash twin (a glob is judged only for the marked words of a known command)
for c in "del field-manifest.*" "erase field-manifest.*" "rd field-manifest.*" "rmdir field-manifest.*"          "ren field-manifest.* x" "rename field-manifest.* x" "copy other${BS}a field-manifest.*" "xcopy other${BS}a field-manifest.*"; do
  expect "E2 deny: cmd /c '$c' (file command with a glob)"                               2 "$(bash_ "cmd /c '$c'")" E2
done
for c in "echo a & del field-manifest.*" "echo a | del field-manifest.*" "echo a ; del field-manifest.*" "(del field-manifest.*)"; do
  expect "E2 deny: cmd /c '$c' (command position)"                                       2 "$(bash_ "cmd /c '$c'")" E2
done
expect "E2 allow: cmd /c 'del notes.*' (control)"                                0 "$(bash_ "cmd /c 'del notes.*'")"
expect "E2 allow: cmd //c 'echo hi > no^tes.txt' (control)"                      0 "$(bash_ "cmd //c 'echo hi > no^tes.txt'")"
expect "E2 allow: cmd /c 'echo hi > notes.txt' (control)"          0 "$(bash_ "cmd /c 'echo hi > notes.txt'")"
expect "E2 allow: cmd /c dir (control)"                            0 "$(bash_ "cmd /c dir")"

# 2. PowerShell colon-bound parameters
expect "E2 deny (PowerShell): Set-Content -Path:.claude\\state\\x -Value x"  2 "$(ps_ "Set-Content -Path:.claude${BS}state${BS}x -Value x")" E2
expect "E2 deny (PowerShell): Set-Content -LiteralPath:.claude/state/x"      2 "$(ps_ "Set-Content -LiteralPath:.claude/state/x -Value x")" E2
expect "E2 deny (PowerShell): Copy-Item a -Destination:field-manifest.yaml"  2 "$(ps_ "Copy-Item other/a -Destination:field-manifest.yaml")" E2
expect "E2 deny (PowerShell): Set-Content -Path:'field-manifest.yaml' (quoted)" 2 "$(ps_ "Set-Content -Path:'field-manifest.yaml' -Value x")" E2
expect "E2 deny (PowerShell): Set-Content -Dest:field-manifest.yaml (abbreviated parameter)" 2 "$(ps_ "Set-Content -Dest:.claude${BS}state${BS}x -Value x")" E2
expect "allow (PowerShell): Get-Date -Format:H:mm (data, not a path)"           0 "$(ps_ "Get-Date -Format:H:mm")"
expect "allow (PowerShell): Select-String -Path:*.md -Pattern:a:b"              0 "$(ps_ "Select-String -Path:*.md -Pattern:a:b")"
expect "allow (PowerShell): Set-Content -Path:other${BS}n.txt -Value:x:y"       0 "$(ps_ "Set-Content -Path:other${BS}n.txt -Value:x:y")"
expect "E2 allow (PowerShell): Set-Content -Path:other/notes.txt (control)"   0 "$(ps_ "Set-Content -Path:other/notes.txt -Value x")"

# 2b. a rule anchored at the project root (^secrets/): only the split value can match it (the whole token starts with -X:)
P2="$T/p2"; mkdir -p "$P2/.claude/state" "$P2/secrets"
sed "s|protected_paths: \[\]|protected_paths: ['^secrets/']|" field-manifest.yaml > "$P2/field-manifest.yaml"
grep -q "secrets/" "$P2/field-manifest.yaml" || { echo "FAIL  fixture: protected_paths rule not written"; fail=1; }
for prm in Path LiteralPath PSPath Destination FilePath OutFile Name NewName Target OutputPath Dest Lit; do
  expect "E2 deny (PowerShell): -$prm:secrets/x is a path (rule ^secrets/)"             2 "$(CLAUDE_PROJECT_DIR="$P2" ps_ "Set-Content -$prm:secrets/x -Value v")" E2
done
expect "E2 allow (PowerShell): -Value:secrets/x is data (control)"                      0 "$(CLAUDE_PROJECT_DIR="$P2" ps_ "Set-Content other/n -Value:secrets/x")"
expect "E2 allow (PowerShell): -P:secrets/x (one letter is no unique prefix)"           0 "$(CLAUDE_PROJECT_DIR="$P2" ps_ "Set-Content -P:secrets/x -Value v")"

# 3. a:b:c is not a drive path
FREE1=""; FREE2=""
for L in q r s t u v w x y z; do
  if ! python3 -c 'import os,sys;sys.exit(0 if os.path.isdir(sys.argv[1]+":/") else 1)' "$L"; then
    if [ -z "$FREE1" ]; then FREE1=$L; elif [ -z "$FREE2" ]; then FREE2=$L; fi
  fi
done
[ -n "$FREE2" ] || { echo "FAIL  fixture: no two unused drive letters"; fail=1; }
expect "allow: echo $FREE1:b:c (no such drive: not E0)"             0 "$(bash_ "echo $FREE1:b:c")"
expect "allow (PowerShell): Write-Output $FREE1:b:c"               0 "$(ps_ "Write-Output $FREE1:b:c")"
expect "allow: echo $FREE2:y:z"                                    0 "$(bash_ "echo $FREE2:y:z")"

# 4. link names with '-' or glob characters (POSIX; on Windows a glob is matched against the root's links)
mk_link() { # name target-relative-to-the-project; a real file symlink (mklink on Windows: ln -s in Git Bash copies)
  if is_windows; then
    cmd /c "mklink $(cygpath -w "$P/$1") $(cygpath -w "$P/$2")" >"$T/lnk.err" 2>&1
  else
    ln -s "$P/$2" "$P/$1" 2>"$T/lnk.err"
  fi
}
if mk_link -dl ".claude/state/newf" && mk_link ledger_l ".claude/state/ledger" && mk_link other_l "other/x"; then
  is_windows || {
    expect "E2 deny: echo x >> -dl (link named with a leading dash)"        2 "$(bash_ 'echo x >> -dl')" E2
    expect "E2 deny: echo x | tee -a -- -dl"                               2 "$(bash_ 'echo x | tee -a -- -dl')" E2
  }
  expect "E2 deny: echo x >> ledger_?   (glob matching a link)"            2 "$(bash_ 'echo x >> ledger_?')" E2
  expect "E2 deny: echo x >> ledger*    (glob matching a link)"            2 "$(bash_ 'echo x >> ledger*')" E2
  expect "E2 deny: echo x >> ledger_[l] (char class matching a link)"      2 "$(bash_ 'echo x >> ledger_[l]')" E2
  expect "E2 allow: echo x >> other_l (link to a harmless place, control)" 0 "$(bash_ 'echo x >> other_l')"
  expect "E2 allow: echo x >> nomatch* (glob matching nothing, control)"   0 "$(bash_ 'echo x >> nomatch*')"
  expect "E2 allow: echo x >> -v (dash word that names nothing, control)"  0 "$(bash_ 'echo x >> -v')"
  # a directory link (a junction on Windows) and globs with a slash after the glob component
  mk_dirlink() { # name target
    if is_windows; then cmd /c "mklink /J $(cygpath -w "$P/$1") $(cygpath -w "$P/$2")" >"$T/lnk.err" 2>&1
    else ln -s "$P/$2" "$P/$1" 2>"$T/lnk.err"; fi
  }
  if mk_dirlink dirl ".claude/state"; then
    expect "E2 deny: echo x >> dirl*/f   (glob, then a slash)"                  2 "$(bash_ 'echo x >> dirl*/f')" E2
    expect "E2 deny: echo x >> dir?/f"                                         2 "$(bash_ 'echo x >> dir?/f')" E2
    expect "E2 deny: echo x >> d[i]rl/f"                                        2 "$(bash_ 'echo x >> d[i]rl/f')" E2
    expect "E2 deny: echo x >> ./dir*/f"                                        2 "$(bash_ 'echo x >> ./dir*/f')" E2
    expect "E2 deny: echo x >> dir*  (junction/dir link, bare glob)"            2 "$(bash_ 'echo x >> dir*')" E2
    if mk_dirlink rootl ""; then
      expect "E2 deny: echo x >> rootl*/field-manifest.yaml (the tail after the glob matters)" 2 "$(bash_ 'echo x >> rootl*/field-manifest.yaml')" E2
    else
      echo "FAIL  fixture: could not create a directory link to the root: $(head -n 1 "$T/lnk.err")"; fail=1
    fi
    # the tail after the glob only matters to a rule anchored at the root (^secrets/): the bare token never matches it
    if is_windows; then cmd /c "mklink /J $(cygpath -w "$P2/rootl2") $(cygpath -w "$P2")" >"$T/lnk.err" 2>&1; else ln -s "$P2" "$P2/rootl2" 2>"$T/lnk.err"; fi
    expect "E2 deny: echo x >> rootl*/secrets/x (rule ^secrets/ reached through a glob and its tail)" 2 "$(CLAUDE_PROJECT_DIR="$P2" bash_ 'echo x >> rootl*/secrets/x')" E2
    expect "E2 allow: echo x >> rootl*/other/x (control)"                         0 "$(CLAUDE_PROJECT_DIR="$P2" bash_ 'echo x >> rootl*/other/x')"
    expect "E2 allow: echo x >> nomatch*/f (control)"                           0 "$(bash_ 'echo x >> nomatch*/f')"
    expect "E2 allow: echo x >> oth*/f (glob matching a plain dir, control)"    0 "$(bash_ 'echo x >> oth*/f')"
  else
    echo "FAIL  fixture: could not create a directory link: $(head -n 1 "$T/lnk.err")"; fail=1
  fi
  is_windows || if mk_dirlink -dd ".claude/state"; then
    expect "E2 deny: echo x >> -d*/f   (dash-named dir link, glob, slash)"      2 "$(bash_ 'echo x >> -d*/f')" E2
  fi
else
  echo "FAIL  fixture: the OS refused to create a symlink: $(head -n 1 "$T/lnk.err")"; fail=1
fi

[ "$fail" = 0 ] && echo "ALL SHELL-FORM TESTS PASSED" || { echo "SHELL-FORM TESTS FAILED"; exit 1; }
