"""n8n reference enforcement tests. Run by run_n8n.sh; prints PASS/FAIL/SKIP lines.

1. decide() cases (E1, E3 incl. policy verdicts and the (?i) translation, E4, E0 fail-closed).
2. Differential: on commands inside the implemented subset the JS verdict equals the Python gate's
   (field-gate.py run as the hook, on a temp project with the same manifest).
3. Known gaps are asserted as gaps (the Python gate denies, this reference does not), so closing one is a test change.
4. The JS ledger verifies under hooks/verify-ledger.py and each record is byte-identical to Python's json.dumps.
5. The generated workflow is in sync with field-gate-core.js and the Code nodes execute (stubbed n8n globals).
"""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
N8N = HERE.parent
HOOKS = N8N.parent / "hooks"
fail = 0


def report(ok, label, detail=""):
    global fail
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f" ({detail})"))
    fail |= not ok


def js(manifest, inputs, state=None):
    req = {"manifest": manifest, "inputs": inputs}
    if state:
        req["state"] = state
    p = subprocess.run(["node", str(HERE / "js_decide.js")], input=json.dumps(req), capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


def bash(cmd, sid="s", mode=None, tool="Bash"):
    d = {"session_id": sid, "tool_name": tool, "tool_input": {"command": cmd}, "tool_use_id": "t-" + str(abs(hash(cmd)) % 10**6)}
    if mode:
        d["permission_mode"] = mode
    return d


def verdict(manifest, inp):
    return js(manifest, [inp])["decisions"][0]


BASE = {"enforcement": {"irreversible_action_policy": "forbid", "rate_limits": [{"action": "tool_call", "max": 3, "period": "session"}],
                        "irreversible_actions": {"deny_patterns": [r"\bgit\s+push\s+.*--force", r"\bgit\s+push\s+\S+\s+(HEAD:)?(main|master)\b",
                                                                   r"\bgh\s+pr\s+merge\b", r"(?i)\bRemove-Item\b.*-Recurse"]}}}


def with_ia(**kw):
    m = json.loads(json.dumps(BASE))
    m["enforcement"]["irreversible_actions"].update(kw)
    return m


# 1. decide() cases
d = verdict(BASE, bash("git push --force origin x"))
report(d["permissionDecision"] == "deny" and d["rule"] == "E3", "E3: force push denied", d)
d = verdict(BASE, bash("git push origin main"))
report(d["permissionDecision"] == "deny" and d["rule"] == "E3", "E3: push to main denied", d)
d = verdict(BASE, bash("git push -u origin ssl-fp-builder-1"))
report(d["permissionDecision"] == "allow", "E3: push of a feature branch allowed", d)
d = verdict(BASE, bash("remove-item x -recurse", tool="PowerShell"))
report(d["permissionDecision"] == "deny" and d["rule"] == "E3", "E3: PowerShell is case-insensitive; (?i) translated", d)
d = verdict(BASE, bash("remove-item x -recurse", tool="Bash"))
report(d["permissionDecision"] == "deny", "E3: (?i) pattern also matches case-insensitively under Bash (inline flag honoured)", d)
d = verdict(BASE, {"session_id": "s", "tool_name": "Edit", "tool_input": {"file_path": "x"}})
report(d["permissionDecision"] == "allow", "non-shell tool: allowed (E2 is not implemented here)", d)
d = verdict(BASE, {"session_id": "s", "tool_name": "Read", "tool_input": {"file_path": "x"}})
report(d["permissionDecision"] == "allow", "ungated tool allowed", d)

pol = with_ia(deny_patterns_verdict="policy")
for policy, mode, want, rule in [("forbid", "default", "deny", "E3"), ("require_human_approval", "default", "ask", "E3-policy"),
                                 ("require_human_approval", None, "deny", "E3"), ("require_human_approval", "plan", "deny", "E3"),
                                 ("allow_with_ledger", None, "allow", "E3-allowed"), ("bogus", "default", "deny", "E0")]:
    m = json.loads(json.dumps(pol))
    m["enforcement"]["irreversible_action_policy"] = policy
    d = verdict(m, bash("gh pr merge 1", mode=mode))
    report(d["permissionDecision"] == want and (d["rule"] == rule), f"policy verdict {policy}/{mode} -> {want} {rule}", d)

for label, m in [("invalid verdict mode", with_ia(deny_patterns_verdict="maybe")),
                 ("unsupported inline flag (?s)", with_ia(deny_patterns=[r"(?s)rm.*"])),
                 ("deny_patterns not a list", with_ia(deny_patterns="rm")),
                 ("broken regex", with_ia(deny_patterns=["("]))]:
    d = verdict(m, bash("ls"))
    report(d["permissionDecision"] == "deny" and d["rule"] == "E0", f"fail-closed E0: {label}", d)
for label, m, inp in [("no manifest", None, bash("ls")), ("manifest without enforcement", {"agent": {}}, bash("ls")),
                      ("input without tool_name", BASE, {"session_id": "s"}), ("input not an object", BASE, "ls")]:
    d = verdict(m, inp)
    report(d["permissionDecision"] == "deny" and d["rule"] == "E0", f"fail-closed E0: {label}", d)
d = verdict(BASE, bash("x" * (64 * 1024 + 1)))
report(d["permissionDecision"] == "deny" and d["rule"] == "E0", "fail-closed E0: oversize command", d)

# E1 kill: holds for every tool including ungated; resume restores
r = js(BASE, [{"operate": "kill"}, bash("ls"), {"session_id": "s", "tool_name": "Read", "tool_input": {}}, {"operate": "resume"}, bash("ls")])["decisions"]
report([x.get("permissionDecision") for x in r[1:3]] == ["deny", "deny"] and r[1]["rule"] == "E1" and r[4]["permissionDecision"] == "allow",
       "E1: kill denies all tools incl. Read; resume restores", r)

# E4 budget: per session, denied-by-E3 calls do not count (as in the Python gate)
seq = [bash("ls", "a"), bash("git push --force o x", "a"), bash("ls", "a"), bash("ls", "a"), bash("ls", "a"), bash("ls", "b")]
r = [x["permissionDecision"] + (x["rule"] or "") for x in js(BASE, seq)["decisions"]]
report(r == ["allow", "denyE3", "allow", "allow", "denyE4", "allow"], "E4: budget 3 per session; E3 denials uncounted; other session independent", r)

# 2. Differential vs the Python gate (inside the implemented subset)
def python_gate(manifest_yaml, inp):
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d, "field-manifest.yaml").write_text(manifest_yaml)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=d)
        env.pop("FIELD_MANIFEST", None)
        p = subprocess.run(["sh", str(HOOKS / "field-gate.sh")], input=json.dumps(dict(inp, cwd=d)), capture_output=True, text=True, env=env)
        out = p.stdout.strip()
        if p.returncode == 2:
            return "deny"
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"


try:
    import yaml
except ImportError:
    yaml = None
if yaml is None:
    print("SKIP  differential tests: PyYAML missing\n      reason: the Python gate needs PyYAML to read the manifest")
else:
    template = (N8N.parent / "skills" / "field" / "templates" / "field-manifest-default.yaml").read_text()
    # a concrete manifest: valid FIELD structure, our enforcement block, no E2/E5 triggers in the corpus
    man = yaml.safe_load(template)
    man["enforcement"].update({"rate_limits": [{"action": "tool_call", "max": 100, "period": "session"}],
                               "irreversible_actions": {"deny_patterns": BASE["enforcement"]["irreversible_actions"]["deny_patterns"]}})
    man["enforcement"]["kill_switch"] = {"endpoint": ".claude/state/KILL", "method": "file", "authorized_operators": ["op"]}
    man["enforcement"]["irreversible_action_policy"] = "forbid"
    my = yaml.safe_dump(man)
    corpus = ["ls -la", "git status", "git push --force origin x", "git push origin main", "git push -u origin feature", "gh pr merge 21",
              "gh pr view 21", "echo hello", "python3 -m pytest -q", "git commit -m 'fix: x'"]
    bad = []
    for c in corpus:
        a, b = verdict(man, bash(c))["permissionDecision"], python_gate(my, bash(c))
        if a != b:
            bad.append((c, a, b))
    report(not bad, f"differential: JS == Python gate on {len(corpus)} in-subset commands", bad)

    # 3. known gaps (documented in README): shell canonicalisation is not implemented
    for c, why in [("git push -f origin x", "short force flag (the pattern says --force)"), ("git push origin +feature:main", "+refspec force push")]:
        js_v, py_v = verdict(man, bash(c))["permissionDecision"], python_gate(my, bash(c))
        report(js_v == "allow" and py_v == "deny", f"KNOWN GAP asserted: {c!r} -> JS allow, Python deny ({why})", (js_v, py_v))

# 4. Ledger parity
seq = [bash("ls éü\U0001F600 \"q\" \\ \t", "s1"), bash("git push --force o x", "s1"), {"operate": "kill"}, bash("ls", "s1")]
res = js(BASE, seq)
with tempfile.TemporaryDirectory() as d:
    lp = pathlib.Path(d, "ledger.jsonl")
    lp.write_text("\n".join(res["ledger"]) + "\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(HOOKS / "verify-ledger.py"), str(lp)], capture_output=True, text=True)
    report(p.returncode == 0 and "INTACT" in p.stdout, "ledger: JS chain verifies under hooks/verify-ledger.py", p.stdout + p.stderr)
    same = all(json.dumps(json.loads(l), sort_keys=True) == l for l in res["ledger"])
    report(same, "ledger: every record is byte-identical to Python json.dumps(sort_keys=True)")
    # record provenance (1.6.0): same keys on every decision, a digest of the manifest object, the phase
    recs = [json.loads(l) for l in res["ledger"]]
    decided = [r for r in recs if r.get("tool") != "operator"]
    want = hashlib.sha256(json.dumps(BASE, sort_keys=True).encode()).hexdigest()
    report(len(decided) == 3 and all(r.get("manifest_json_sha256") == want and r.get("gate_version") == "n8n-1.6.0"
                                     and r.get("phase") == "pre" for r in decided),
           "provenance: every decision carries manifest_json_sha256 (canonical JSON), gate_version and phase", decided)
    report(len({frozenset(r) for r in decided}) == 1 and decided[0]["decision"] == "allow" and decided[0]["rule"] is None
           and decided[0]["reason"] is None and decided[1]["rule"] == "E3",
           "provenance: allow and deny records have the same keys; allow has rule and reason null", [sorted(r) for r in decided])
    report(all("manifest_sha256" not in r for r in recs),
           "provenance: the n8n digest is not written under the Python gate's field name", recs)
    other = json.loads(json.dumps(BASE)); other.setdefault("enforcement", {})["protected_paths"] = ["changed"]
    report(json.loads(js(other, [bash("ls")])["ledger"][0])["manifest_json_sha256"] != want,
           "provenance: a changed manifest changes the digest")
    bad = js({"enforcement": {"x": 1.5}}, [bash("ls")])
    report(bad["decisions"][0]["permissionDecision"] in ("allow", "deny") and "manifest_json_sha256" in json.loads(bad["ledger"][0]),
           "provenance: a manifest value the digest cannot write gives a null digest, not a crash", bad)
    lines = lp.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["decision"] = "allow"
    lines[1] = json.dumps(rec, sort_keys=True)
    lp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(HOOKS / "verify-ledger.py"), str(lp)], capture_output=True, text=True)
    report(p.returncode == 1, "ledger: an edited record is detected (TAMPERED)", p.stdout + p.stderr)

# 5. Workflow in sync + Code nodes execute with stubbed n8n globals
sys.path.insert(0, str(N8N))
import build_workflow  # noqa: E402

mine = json.loads(json.dumps(build_workflow.build(build_workflow.convert(build_workflow.DEFAULT_MANIFEST.read_text())), sort_keys=True))
shipped = json.loads((N8N / "field-enforcement.workflow.json").read_text())
report(mine == shipped, "workflow: field-enforcement.workflow.json equals build_workflow.py output (regenerate if this fails)")
names = {n["name"]: n for n in shipped["nodes"]}
conn_ok = all(t["node"] in names for v in shipped["connections"].values() for branch in v["main"] for t in branch) and set(shipped["connections"]) <= set(names)
report(conn_ok and len(names) == 6, "workflow: 6 nodes, every connection resolves")
report(all(names[n]["parameters"]["authentication"] == "headerAuth" for n in ("Gate Webhook", "Operate Webhook")),
       "workflow: both webhooks require header auth")

runner = r"""
const vm = require('vm');
const wf = JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8'));
const sd = {};
const mk = (name) => (items) => {
  const code = wf.nodes.find((n) => n.name === name).parameters.jsCode;
  const fn = new Function('$input', '$getWorkflowStaticData', 'require', 'Buffer', code);
  return fn({ all: () => items }, () => sd, require, Buffer);
};
const gate = mk('Field Gate'), operate = mk('Field Operate');
const call = (cmd) => gate([{ json: { body: { session_id: 's', tool_name: 'Bash', tool_input: { command: cmd } } } }])[0].json;
const out = [call('ls'), call('git push --force origin x'), operate([{ json: { body: { op: 'kill' } } }])[0].json, call('ls'), operate([{ json: { body: { op: 'resume' } } }])[0].json, call('ls')];
console.log(JSON.stringify({ out, ledger: sd.field.ledger.length }));
"""
p = subprocess.run(["node", "-e", runner, str(N8N / "field-enforcement.workflow.json")], capture_output=True, text=True)
try:
    r = json.loads(p.stdout)
    o = r["out"]
    ok = [o[0]["permissionDecision"], o[1]["rule"], o[3]["rule"], o[5]["permissionDecision"], r["ledger"]] == ["allow", "E3", "E1", "allow", 6] and o[2]["killed"] is True and o[4]["killed"] is False
    report(ok, "workflow Code nodes execute (stubbed n8n globals): allow, E3 deny, kill -> E1, resume -> allow, 6 ledger records", r)
except Exception:
    report(False, "workflow Code nodes execute (stubbed n8n globals)", p.stdout + p.stderr)

print("ALL N8N TESTS PASSED" if not fail else "N8N TESTS FAILED")
sys.exit(1 if fail else 0)
