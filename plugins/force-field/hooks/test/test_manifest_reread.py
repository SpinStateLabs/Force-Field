"""Manifest re-read tests. Run by run_manifest_reread.sh; prints PASS/FAIL lines.

The gate decides every gated call under the manifest that is on disk at that call. It is a new process per call
(hooks.json starts field-gate.sh, which starts Python) and nothing it writes holds a copy of the manifest, so a
change to the manifest takes effect on the next gated call. A cache kept between calls would break that, and
would let a ledger record describe rules that were no longer the ones on disk.

  1. A cache has to key on something. Between calls this test rewrites the manifest IN PLACE: the same file, the
     same byte length, the modification time put back to the nanosecond. A cache keyed on the file's identity,
     size or time would answer from the old manifest. Two independent parts of the manifest change (an E3 deny
     pattern and an E2 protected path); then the manifest is made unparsable (E0) and restored. Every decision
     must follow the bytes on disk.
  2. The check itself: the same calls must go wrong against a mutant gate whose load_manifest answers from a
     file keyed on size and modification time. A check that passes the mutant is a FAIL.

Read-only tools (UNGATED in field-gate.py) never reach the manifest and are not part of this test.
State goes in a temporary directory, the governed registry included; nothing is written under ~/.claude.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "..", "field-gate.py")
FIXTURE = os.path.join(HERE, "field-manifest.yaml")
PATTERN_ANCHOR = "    deny_patterns:\n"
PATHS_ANCHOR = "  protected_paths: []"
RULES = ("E0", "E1", "E2", "E3", "E4", "E5")
fail = 0


def report(ok, label, detail=""):
    global fail
    if ok:
        print("PASS  " + label)
    else:
        print("FAIL  " + label + (" (" + detail + ")" if detail else ""))
        fail = 1


def manifests():
    """(A, B, G): three manifests of one byte length, or None when the fixture no longer has the two anchors.
    A denies the token REREADA and protects reread-a.txt; B denies REREADB and protects reread-b.txt (the ones
    the calls below use); G is not parsable YAML."""
    with open(FIXTURE, encoding="utf-8") as fh:  # universal newlines: a CRLF checkout reads the same
        base = fh.read()
    if base.count(PATTERN_ANCHOR) != 1 or base.count(PATHS_ANCHOR) != 1:
        return None

    def variant(x):
        text = base.replace(PATTERN_ANCHOR, PATTERN_ANCHOR + r"      - '\bREREAD%s\b'" % x.upper() + "\n")
        return text.replace(PATHS_ANCHOR, r"  protected_paths: ['reread-%s\.txt$']" % x).encode("utf-8")

    a, b = variant("a"), variant("b")
    return a, b, b"{" + b"x" * (len(a) - 1)


def call(gate, proj, env, tool, tool_input, n):
    """One gated call in a new process, as the launcher starts it. 'allow', 'deny <rule>' or 'no verdict (...)'."""
    inp = {"session_id": "reread", "tool_name": tool, "tool_input": tool_input, "cwd": proj,
           "hook_event_name": "PreToolUse", "permission_mode": "default", "tool_use_id": "toolu_%d" % n}
    r = subprocess.run([sys.executable, gate], input=json.dumps(inp).encode("utf-8"), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env, cwd=proj, timeout=120)
    if r.returncode == 0:
        return "allow"
    text = (r.stdout + r.stderr).decode("utf-8", "replace")
    for rule in RULES:
        if "[%s]" % rule in text:
            return "deny " + rule
    # a deny always names its rule: anything else is the gate not running (a wrong path, a crash)
    return "no verdict (exit %d: %s)" % (r.returncode, " ".join(text.split())[-160:])


def swap(path, content):
    """Rewrite the file in place and put its times back. True when its identity, size and modification time are
    all unchanged, which is what makes the next call a test of caching."""
    before = os.stat(path)
    with open(path, "r+b") as fh:
        fh.write(content)
        fh.truncate()
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = os.stat(path)
    return ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns))


def sequence(gate, work, name, a, b, g, extra_env=None):
    """The calls, against `gate`, in a fresh governed project. Returns ([(label, want, got)], kept): kept is
    False when a swap changed the file's identity, size or modification time."""
    proj = os.path.join(work, name, "project")
    os.makedirs(proj)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = proj
    env["FIELD_GOVERNED_DIR"] = os.path.join(work, name, "governed-registry")
    for k in ("FIELD_MANIFEST", "FIELD_ANCHOR_DIR"):
        env.pop(k, None)
    env.update(extra_env or {})
    mf = os.path.join(proj, "field-manifest.yaml")
    with open(mf, "wb") as fh:
        fh.write(a)
    bash = ("Bash", {"command": "echo REREADB"})
    edit = ("Edit", {"file_path": os.path.join(proj, "reread-b.txt"), "old_string": "a", "new_string": "b"})
    plan = [
        ("manifest A", None, [(bash, "allow"), (edit, "allow")]),
        ("manifest B swapped in", b, [(bash, "deny E3"), (edit, "deny E2")]),
        ("manifest A swapped back", a, [(bash, "allow"), (edit, "allow")]),
        ("unparsable manifest swapped in", g, [(bash, "deny E0")]),
        ("manifest A swapped back again", a, [(bash, "allow")]),
    ]
    results, kept, n = [], True, 0
    for state, content, calls in plan:
        if content is not None:
            kept = swap(mf, content) and kept
        for (tool, tool_input), want in calls:
            n += 1
            results.append(("%s: %s" % (state, tool), want, call(gate, proj, env, tool, tool_input, n)))
    return results, kept


# Appended to a copy of the gate, before its `if __name__ == "__main__":` block, so main() calls this one.
MAIN_MARK = '\nif __name__ == "__main__":\n'
MUTANT = '''
# ---- MUTANT (test_manifest_reread.py): load_manifest answers from a file keyed on size and mtime ----
_real_load_manifest = load_manifest


def load_manifest(path):
    try:
        st = path.stat()
        key = [st.st_size, st.st_mtime_ns]
    except OSError:
        key = None
    cache = os.environ["REREAD_MUTANT_CACHE"]
    try:
        with open(cache, encoding="utf-8") as fh:
            saved = json.load(fh)
        if saved["key"] == key:
            return saved["manifest"]
    except (OSError, ValueError, KeyError):
        pass
    manifest = _real_load_manifest(path)
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"key": key, "manifest": manifest}, fh, default=str)
    return manifest

'''


def build_mutant(work):
    """Path of the mutant gate, or None when the gate no longer has exactly one __main__ block to hook before."""
    with open(GATE, encoding="utf-8") as fh:
        src = fh.read()
    if src.count(MAIN_MARK) != 1:
        return None
    d = os.path.join(work, "mutant-gate")
    os.makedirs(d)
    path = os.path.join(d, "field-gate.py")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src.replace(MAIN_MARK, MUTANT + MAIN_MARK))
    return path


def main():
    made = manifests()
    report(made is not None, "fixture has the two anchors the manifests are built from",
           "field-manifest.yaml changed: update PATTERN_ANCHOR / PATHS_ANCHOR")
    if made is None:
        return
    a, b, g = made
    report(len(a) == len(b) == len(g) and a != b, "manifests A, B and the unparsable one have one byte length",
           "%d %d %d" % (len(a), len(b), len(g)))
    work = tempfile.mkdtemp(prefix="field-reread-")
    try:
        # 1. the gate as shipped
        results, kept = sequence(GATE, work, "gate", a, b, g)
        for label, want, got in results:
            report(got == want, "%s -> %s" % (label, want), "got " + got)
        report(kept, "every swap kept the manifest's file identity, size and modification time",
               "a swap changed one of them: the calls after it did not test caching")

        # 2. the check itself: a gate that caches the manifest by size and mtime must be caught
        mutant = build_mutant(work)
        report(mutant is not None, "mutant gate built (load_manifest wrapped with a size and mtime cache)",
               "field-gate.py no longer has exactly one __main__ block: update MAIN_MARK")
        if mutant is not None:
            m_results, m_kept = sequence(mutant, work, "mutant", a, b, g,
                                         {"REREAD_MUTANT_CACHE": os.path.join(work, "mutant-cache.json")})
            wrong = [(label, want, got) for label, want, got in m_results if got != want]
            stale = [w for w in wrong if w[2] == "allow"]
            # the three calls that must be denied are answered "allow" from the cached manifest A, and nothing else
            report(m_kept and len(wrong) == 3 and len(stale) == 3,
                   "the check rejects the mutant: its 3 deny calls were answered from the old manifest",
                   "wrong answers: %s" % (wrong or "none: the mutant passed, so this test would not see a cache"))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
    sys.exit(fail)
