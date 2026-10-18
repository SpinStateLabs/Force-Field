#!/usr/bin/env bash
# Host check: does the Enforcement Gate enforce on THIS machine? Run from anywhere:  bash hooks/test/check_host.sh
# Run it on every OS you support (Windows: from Git Bash, the shell Claude Code uses for hooks there).
# Prints which interpreters resolve (flags the Windows Store alias stub), runs the launcher on the real PATH
# against the fixture manifest, then runs the launcher test suite. Exits non-zero unless the gate enforces.
set -u
cd "$(dirname "$0")"
HERE="$PWD"; L="$HERE/../field-gate.sh"
echo "host: $(uname -srm)   sh: $(command -v sh)"
for py in python3 py python; do
  p=$(command -v "$py" 2>/dev/null) || { echo "  $py: not on PATH"; continue; }
  case $p in *WindowsApps*) note=" (Windows Store alias)";; *) note="";; esac
  args=; [ "$py" = py ] && args=-3
  out=$("$py" $args -c 'import sys; import yaml; print(sys.version.split()[0], "PyYAML", yaml.__version__)' </dev/null 2>&1); rc=$?
  echo "  $py: $p$note -> exit $rc: $(printf %s "$out" | head -n 1)"
done
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cp "$HERE/field-manifest.yaml" "$T/"
gate() { printf '{"session_id":"h1","tool_name":"Bash","tool_input":{"command":"%s"}}' "$1" \
  | CLAUDE_PROJECT_DIR="$T" sh "$L" 2>&1 >/dev/null; echo "exit=$?"; }
a=$(gate 'ls -la'); d=$(gate 'rm -rf build')
echo "launcher on the real PATH: allow case -> ${a##*exit=}, deny case -> ${d##*exit=} ($(printf %s "$d" | head -n 1))"
case "${a##*exit=}/${d##*exit=}" in
  0/2) verdict="ENFORCED (a Python ran the gate)" ;;
  2/2) case $a in *'[E0]'*) verdict="ENFORCED by E0 only (no Python ran the gate: every call in a governed project is denied)";;
         *) verdict="UNEXPECTED (the allow case was denied: $(printf %s "$a" | head -n 1))";; esac ;;
  *) verdict="NOT ENFORCED" ;;
esac
echo "verdict: $verdict"
echo "--- launcher suite"
bash "$HERE/run_launcher.sh"; s=$?
case $verdict in ENFORCED*) [ $s -eq 0 ] ;; *) false ;; esac
