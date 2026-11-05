"""Data-driven gate cases (PR 15, second and third review): every line of the corpus files is run through the gate in
a scratch project with the suite's manifest. Format: `D|A @@ Tool @@ command` (D = must be denied, A = must stay
allowed; {NL} {TAB} {NBSP} are placeholders); lines without ' @@ ' are comments. Prints one FAIL line per mismatch
and a PASS line per file; exits 1 on any mismatch. Usage: cmd_corpus.py <field-gate.py> <corpus>..."""
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

gate, files = sys.argv[1], sys.argv[2:]
here = os.path.dirname(os.path.abspath(__file__))
proj = tempfile.mkdtemp(prefix="corpus_")
os.makedirs(os.path.join(proj, ".claude", "state"))
os.makedirs(os.path.join(proj, "other"))
shutil.copy(os.path.join(here, "field-manifest.yaml"), os.path.join(proj, "field-manifest.yaml"))
counter = itertools.count()
env = dict(os.environ, CLAUDE_PROJECT_DIR=proj)


def run(row):
    tool, cmd = row[1], row[2]
    payload = {"session_id": "corpus%d" % next(counter), "tool_name": tool, "tool_input": {"command": cmd}}
    proc = subprocess.run([sys.executable, gate], input=json.dumps(payload), capture_output=True, text=True, env=env)
    return row, proc.returncode


bad = 0
for f in files:
    rows = []
    for line in open(os.path.join(here, f), encoding="utf-8"):
        line = line.rstrip("\n")
        if line.count(" @@ ") >= 2:
            exp, tool, cmd = line.split(" @@ ", 2)
            if exp == "DW":  # Windows name rules (case, trailing dot, streams): a different file elsewhere
                if os.name != "nt":
                    continue
                exp = "D"
            rows.append((exp, tool, cmd.replace("{TAB}", "\t").replace("{NBSP}", "\u00a0").replace("{NL}", "\n")))
    mism = 0
    with ThreadPoolExecutor(4) as ex:
        for row, rc in ex.map(run, rows):
            if (rc == 2) != (row[0] == "D"):
                mism += 1
                print("FAIL  %s: expected %s, got exit %s: %s %r" % (f, "deny" if row[0] == "D" else "allow", rc, row[1], row[2][:100]))
    bad += mism
    if not mism:
        print("PASS  %s: all %d cases as expected" % (f, len(rows)))
shutil.rmtree(proj, ignore_errors=True)
sys.exit(1 if bad else 0)
