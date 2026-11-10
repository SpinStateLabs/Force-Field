"""Ledger record provenance (gate 1.6.0): manifest_sha256, gate_version, phase, one key set for every decision,
and a ledger record for the two E0 denies that had none (oversize hook input, hook input that is not JSON).
The gate is run as the hook runs it: a subprocess fed the hook input on stdin."""
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HOOKS = HERE.parent
GATE = HOOKS / "field-gate.py"
FIXTURE = HERE / "field-manifest.yaml"
fails = 0


def report(ok, name, detail=""):
    global fails
    if ok:
        print(f"PASS  {name}")
    else:
        fails += 1
        print(f"FAIL  {name}\n      {detail}")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = load("field_gate_prov", GATE)
post = load("field_post_prov", HOOKS / "field-post.py")


class Project:
    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="ffprov"))
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self.manifest = self.root / "field-manifest.yaml"
        shutil.copyfile(FIXTURE, self.manifest)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("FIELD_MANIFEST", "FIELD_ANCHOR_DIR", "CLAUDE_PROJECT_DIR")}
        self.env.update(CLAUDE_PROJECT_DIR=str(self.root), FIELD_GOVERNED_DIR=str(self.tmp / "governed"),
                        PYTHONUTF8="1")
        self.n = 0

    def raw(self, data):
        return subprocess.run([sys.executable, str(GATE)], input=data, capture_output=True, env=self.env,
                              cwd=str(self.root))

    def call(self, tool, tool_input):
        self.n += 1
        inp = {"session_id": "prov", "tool_name": tool, "tool_input": tool_input, "tool_use_id": f"t{self.n}",
               "permission_mode": "default", "cwd": str(self.root)}
        return self.raw(json.dumps(inp).encode())

    def ledger(self):
        m = g.load_manifest(self.manifest)
        path = g.resolve_store(m if isinstance(m, dict) else None, self.root)[0]
        if not path.exists():
            return path, []
        return path, [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    def digest(self):
        return hashlib.sha256(self.manifest.read_bytes()).hexdigest()

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def verify(path):
    p = subprocess.run([sys.executable, str(HOOKS / "verify-ledger.py"), str(path)], capture_output=True, text=True)
    return p.returncode == 0 and "LEDGER INTACT" in p.stdout, p.stdout + p.stderr


PROV = {"manifest_sha256", "gate_version", "phase"}

# 1. allow and deny records: provenance present, same keys
P = Project()
try:
    a = P.call("Bash", {"command": "ls"})
    d = P.call("Write", {"file_path": str(P.manifest), "content": "x"})
    path, recs = P.ledger()
    report(a.returncode == 0 and d.returncode == 2 and len(recs) == 2, "an allow and a deny are each ledgered once",
           f"rc {a.returncode} {d.returncode}, {len(recs)} records, {a.stderr!r} {d.stderr!r}")
    if len(recs) == 2:
        allow, deny = recs
        report(allow["decision"] == "allow" and deny["decision"] == "deny" and deny["rule"] == "E2",
               "decisions are allow, then deny E2", recs)
        report(all(r.get("manifest_sha256") == P.digest() for r in recs),
               "manifest_sha256 is the sha-256 of the manifest file's bytes", [r.get("manifest_sha256") for r in recs])
        report(all(r.get("gate_version") == g.GATE_VERSION and r.get("phase") == "pre" for r in recs),
               "gate_version and phase 'pre' on both records", recs)
        report("rule" in allow and allow["rule"] is None and "reason" in allow and allow["reason"] is None,
               "the allow record carries rule and reason as null", allow)
        report(set(allow) | {"path"} == set(deny), "allow and deny records have the same keys (deny of a file tool adds path)",
               sorted(set(allow) ^ set(deny)))
        report(len(allow["manifest_sha256"]) == 64, "the digest is the full 64 hex characters", allow["manifest_sha256"])

    # 2. the digest follows the manifest, and only the manifest
    before = P.digest()
    P.call("Bash", {"command": "ls"})
    with P.manifest.open("ab") as fh:  # a human edits the manifest outside the session
        fh.write(b"\n# reviewed\n")
    P.call("Bash", {"command": "ls"})
    path, recs = P.ledger()
    report(recs[2]["manifest_sha256"] == before and recs[0]["manifest_sha256"] == before,
           "the digest is the same on every call while the manifest is unchanged", [r["manifest_sha256"] for r in recs])
    report(recs[3]["manifest_sha256"] == P.digest() != before,
           "an edit to the manifest changes the digest of the next record", [r["manifest_sha256"] for r in recs])

    # 3. CRLF manifest: the digest is over the bytes on disk, and the manifest still parses
    P.manifest.write_bytes(FIXTURE.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    r = P.call("Bash", {"command": "ls"})
    path, recs = P.ledger()
    report(r.returncode == 0 and recs[-1].get("manifest_sha256") == P.digest() and recs[-1]["decision"] == "allow",
           "a CRLF manifest parses and is digested as stored", (r.returncode, r.stderr))

    # 4. a manifest that does not parse: denied E0, and the record names the bytes that were refused
    P.manifest.write_bytes(b"enforcement: [unclosed\n")
    r = P.call("Bash", {"command": "ls"})
    path, recs = P.ledger()
    report(r.returncode == 2 and recs[-1]["rule"] == "E0" and recs[-1].get("manifest_sha256") == P.digest(),
           "an unparseable manifest denies E0 and its digest is recorded", (r.returncode, recs[-1]))
    P.manifest.write_bytes(b"\xff\xfe not utf-8\n")
    r = P.call("Bash", {"command": "ls"})
    path, recs = P.ledger()
    report(r.returncode == 2 and recs[-1]["rule"] == "E0" and recs[-1].get("manifest_sha256") == P.digest(),
           "a manifest that is not UTF-8 denies E0 and its digest is recorded", (r.returncode, recs[-1]))
    shutil.copyfile(FIXTURE, P.manifest)

    # 5. the two E0 denies that had no record
    n0 = len(P.ledger()[1])
    marker = b"SECRET-MARKER-7f3a"
    big = b'{"session_id": "prov", "tool_name": "Bash", "tool_input": {"command": "' + marker + b"A" * (g.MAX_INPUT_BYTES + 16) + b'"}}'
    r = P.raw(big)
    path, recs = P.ledger()
    report(r.returncode == 2 and len(recs) == n0 + 1 and recs[-1]["rule"] == "E0" and "exceeds" in recs[-1]["reason"],
           "oversize hook input: denied E0 and ledgered", (r.returncode, len(recs) - n0, r.stderr[:200]))
    report(recs[-1]["tool"] == "unknown" and recs[-1].get("manifest_sha256") == P.digest() and recs[-1].get("phase") == "pre",
           "the oversize record names no tool and carries provenance", recs[-1])
    r = P.raw(b"this is not json " + marker)
    path, recs = P.ledger()
    report(r.returncode == 2 and len(recs) == n0 + 2 and recs[-1]["rule"] == "E0" and "not a JSON object" in recs[-1]["reason"],
           "hook input that is not JSON: denied E0 and ledgered", (r.returncode, len(recs) - n0, r.stderr[:200]))
    r = P.raw(json.dumps({"session_id": "prov", "tool_name": [marker.decode()], "tool_input": {}}).encode())
    path, recs = P.ledger()
    report(r.returncode == 2 and len(recs) == n0 + 3 and recs[-1]["tool"] == "unknown",
           "a tool_name that is not a string: denied, ledgered, and not copied into the record", recs[-1])
    report(marker not in path.read_bytes(), "nothing of a refused hook input reaches the ledger")

    # 6. the chain verifies, with records from before 1.6.0 and after it in one ledger
    ok, out = verify(path)
    report(ok, "the ledger verifies INTACT", out)
finally:
    P.close()

P = Project()
try:
    path = P.root / ".claude" / "state" / "field-ledger.jsonl"
    g.ledger_append(path, {"ts": "t", "session": "old", "tool": "Bash", "tool_use_id": "o1", "permission_mode": "default",
                           "input_digest": "0" * 16, "store_source": "default", "decision": "allow"})  # the 1.5.2 shape
    r = P.call("Bash", {"command": "ls"})
    _p, recs = P.ledger()
    ok, out = verify(path)
    report(r.returncode == 0 and len(recs) == 2 and "manifest_sha256" not in recs[0] and "manifest_sha256" in recs[1] and ok,
           "a 1.5.2 record followed by a 1.6.0 record: one chain, verifies INTACT", out)
finally:
    P.close()

# 7. no manifest read in this process: the digest is null, never a stale value
g.load_manifest(pathlib.Path(tempfile.gettempdir()) / "no-such-dir-ffprov" / "field-manifest.yaml")
report(g.provenance() == {"manifest_sha256": None, "gate_version": g.GATE_VERSION},
       "provenance() after a missing manifest: digest null", g.provenance())
g.load_manifest(FIXTURE)
report(g.provenance()["manifest_sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
       "provenance() after load_manifest: the digest of that file", g.provenance())
report(set(g.provenance()) == {"manifest_sha256", "gate_version"}, "provenance() holds a digest and a version, nothing else")

# 8. the post hook's record
ask = {"tool": "Bash", "input_digest": "ab" * 8, "hash": "h" * 64}
rec = post.record(ask, "s", "t1", "default", "default", g.provenance())
report(rec["phase"] == "post" and rec["gate_version"] == g.GATE_VERSION and rec["manifest_sha256"] == g.provenance()["manifest_sha256"],
       "field-post.py record: phase 'post' with provenance", rec)
rec = post.record(ask, "s", "t1", "default", "default")
report(rec["phase"] == "post" and "manifest_sha256" not in rec, "field-post.py record() without provenance still builds", rec)

print(f"\n{'ALL PASS' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
