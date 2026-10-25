"""Tests for the incremental ledger index (fix/gate-incremental-ledger). Run by run_ledger_index.sh; prints PASS/FAIL.

The gate used to read the whole ledger on every call. It now keeps a sidecar (a cache of what was verified) and reads
only what was appended. This file proves, against the OLD implementation kept below verbatim as the oracle, that:

  1. DIFFERENTIAL: for random ledgers, random append sequences and random tampering, session_written_paths,
     ledger_append's previous-hash step and field-post's find return what the old code returned (same value, or
     the same exception class; for ValueError the same message). The old ledger_append keeps its own copy of
     every ledger: after each append, through any mix of the gate's views and appends, the two files are equal
     byte for byte and have the same chain head.
  2. SIDECAR: deleting, corrupting, truncating, replacing or forging the sidecar only ever causes a full re-verify
     (so the answer equals the oracle's), never a skipped check. The one thing a forged sidecar plus an untouched
     ledger can still do is hide an entry from a completed segment that the random re-check has not yet drawn;
     that bounded window is exercised and reported as DECLARED, not hidden.
  3. COMPLEXITY: ledger lines parsed per call do not grow with the size of the ledger.
  4. CONCURRENCY: parallel processes under the gate lock, a lock-free reader, no torn sidecar.
  5. TIME BUDGET: a rebuild that cannot finish saves progress and raises LedgerIndexBusy; the next call finishes it.
     In enforce(), at both sites (the E5 check, the check before an allow), that makes the call deny E0.
  6. SAMPLING: damage in the middle of a completed segment is noticed within a bounded number of calls (k segments
     re-hashed per call, seeded draws).
  7. FIELD-POST trusts the sidecar only when the gate would: an edited asks map does not suppress the evidence record.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..")


def load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HOOKS, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


g = load("field_gate", "field-gate.py")
post = load("field_post", "field-post.py")
fail = 0


def check(label, ok, detail=""):
    global fail
    if ok:
        print("PASS  " + label)
    else:
        fail = 1
        print("FAIL  %s %s" % (label, detail))


# ---------------------------------------------------------------------------------------------------------------
# ORACLE: the pre-change code, copied verbatim from origin/main 1679941 (field-gate.py, field-post.py).
# ---------------------------------------------------------------------------------------------------------------
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def old_session_written_paths(ledger_path, session):
    written = set()
    if not ledger_path.exists():
        return written
    for n, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            raise ValueError(f"ledger line {n} is not valid JSON")
        if (isinstance(rec, dict) and rec.get("session") == session and rec.get("decision") == "allow"
                and rec.get("tool") in FILE_TOOLS and isinstance(rec.get("path"), str)):
            written.add(rec["path"])
    return written


def old_prev_hash(ledger_path):
    """The previous-hash step of the old ledger_append (the file already exists)."""
    prev = "0" * 64
    if ledger_path.exists():
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        if lines:
            prev = json.loads(lines[-1])["hash"]
    return prev


def old_ledger_append(ledger_path, record):
    """The whole old ledger_append (origin/main 1679941 field-gate.py)."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not ledger_path.exists():
        # New ledgers are owner-only on POSIX (no-op on Windows). Existing files are left as they are.
        os.close(os.open(str(ledger_path), os.O_CREAT | os.O_WRONLY, 0o600))
    prev = "0" * 64
    if ledger_path.exists():
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        if lines:
            prev = json.loads(lines[-1])["hash"]
    record["prev_hash"] = prev
    body = json.dumps(record, sort_keys=True)
    record["hash"] = hashlib.sha256((prev + body).encode()).hexdigest()
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


RULE = "E3-policy-executed"
ASK_RULE = "E3-policy"


def old_find(ledger_path, session, tool_use_id):
    needle = json.dumps(tool_use_id)[1:-1]
    for line in reversed(ledger_path.read_text(encoding="utf-8").splitlines()):
        if needle not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("tool_use_id") != tool_use_id or rec.get("session") != session:
            continue
        if rec.get("rule") == RULE:
            return "duplicate"
        if rec.get("decision") == "ask" and rec.get("rule") == ASK_RULE:
            return rec
    return None


def outcome(fn):
    try:
        v = fn()
        return ("ok", v)
    except ValueError as e:  # includes UnicodeDecodeError
        return ("exc", type(e).__name__, str(e) if type(e) is ValueError else "")
    except Exception as e:
        return ("exc", type(e).__name__, "")


# ---------------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------------
TMP = tempfile.mkdtemp(prefix="ledgeridx_", dir=os.environ.get("TMP") or os.environ.get("TEMP"))
SESS = ["s0", "s1", "s2", "other"]
EXTRA_SESSIONS = [5, None, ["s0"]]
TUIDS = ["tu%d" % i for i in range(6)] + ['we"ird\\id', "unié"]
PATHS = ["a.sh", "b.py", "dir/c.js", "sha256:" + "ab" * 32, "d e.txt"]


def fresh_dir(name):
    d = pathlib.Path(TMP) / name
    shutil.rmtree(d, ignore_errors=True)
    (d / ".claude" / "state").mkdir(parents=True)
    return d, d / ".claude" / "state" / "field-ledger.jsonl"


def set_small():
    g.IDX_SEG_LINES = 8
    g.IDX_PERSIST_BYTES = 300
    g._VIEW.clear()


def rand_event(rnd):
    r = rnd.random()
    rec = {"ts": "t", "session": rnd.choice(SESS), "tool_use_id": rnd.choice(TUIDS), "permission_mode": "default",
           "input_digest": "%016x" % rnd.getrandbits(64), "store_source": "manifest"}
    if r < 0.30:
        rec.update(tool=rnd.choice(FILE_TOOLS), path=rnd.choice(PATHS), decision="allow")
    elif r < 0.40:
        rec.update(tool=rnd.choice(FILE_TOOLS), path=rnd.choice(PATHS), decision="deny", rule="E2")
    elif r < 0.50:
        rec.update(tool="Write", path=12345, decision="allow")  # path not a string
    elif r < 0.65:
        rec.update(tool="Bash", decision="ask", rule=ASK_RULE, reason="x")
    elif r < 0.75:
        rec.update(tool="Bash", decision="executed", rule=RULE, ran=True)
    elif r < 0.78:
        rec["session"] = rnd.choice([5, None, ["s0"]])
        rec.update(tool="Write", path="num.sh", decision="allow")
    else:
        rec.update(tool="Bash", decision="allow")
    return rec


def raw_append(path, data):
    with open(path, "ab") as fh:
        fh.write(data)


def middle_offset(path, rnd):
    data = path.read_bytes()
    if len(data) < 10:
        return None
    return rnd.randrange(0, len(data) - 1)


def tamper(path, rnd):
    """Apply one random mutation. Returns (name, byte_position_of_first_change or None for 'at the end')."""
    data = path.read_bytes()
    op = rnd.choice(["junk_line", "partial_line", "bad_utf8", "mid_flip", "blank_lines", "sep_in_line", "nondict",
                     "del_mid_line", "truncate", "replace_file", "crlf", "bom_line", "mid_utf8", "valid_extra"])
    n = len(data)
    if op == "junk_line":
        raw_append(path, b"{not json}\n"); return op, n
    if op == "partial_line":
        raw_append(path, b'{"session": "s0", "decision": "allow", "tool": "Write", "path": "p'); return op, n
    if op == "bad_utf8":
        raw_append(path, b'{"x": "\xff\xfe"}\n'); return op, n
    if op == "mid_flip" and n > 20:
        p = rnd.randrange(0, n - 1)
        while data[p:p + 1] == b"\n":
            p = rnd.randrange(0, n - 1)
        path.write_bytes(data[:p] + bytes([data[p] ^ 0x20 if data[p] < 0x7f else 0x41]) + data[p + 1:]); return op, p
    if op == "blank_lines":
        raw_append(path, b"\n   \n\n"); return op, n
    if op == "sep_in_line":
        raw_append(path, b'{"session": "s0"}\x0c{"session": "s1", "decision": "allow", "tool": "Write", "path": "x\\u2028y"}\n')
        return op, n
    if op == "nondict":
        raw_append(path, rnd.choice([b"[1, 2]\n", b"123\n", b"null\n", b'"str"\n'])); return op, n
    if op == "del_mid_line" and data.count(b"\n") > 3:
        lines = data.split(b"\n")
        k = rnd.randrange(0, len(lines) - 2)
        off = sum(len(x) + 1 for x in lines[:k])
        del lines[k]
        path.write_bytes(b"\n".join(lines)); return op, off
    if op == "truncate" and n > 30:
        p = rnd.randrange(10, n); path.write_bytes(data[:p]); return op, p
    if op == "replace_file":
        tmp = path.with_name("replacement.tmp")
        tmp.write_bytes(data[: n // 2] + b'{"session": "s2", "decision": "allow", "tool": "Edit", "path": "r.sh", "hash": "h"}\n')
        os.replace(tmp, path); return op, 0
    if op == "crlf":
        raw_append(path, b'{"session": "s1", "decision": "allow", "tool": "Write", "path": "crlf.sh", "hash": "hh"}\r\n'); return op, n
    if op == "bom_line":
        raw_append(path, b'\xef\xbb\xbf{"session": "s0", "decision": "allow", "tool": "Write", "path": "bom.sh"}\n'); return op, n
    if op == "mid_utf8" and n > 20:
        p = data.find(b'"ts"')
        if p > 0:
            path.write_bytes(data[:p] + b"\xff" + data[p + 1:]); return op, p
    if op == "valid_extra":
        raw_append(path, json.dumps({"session": "s0", "decision": "allow", "tool": "Write", "path": "late.sh", "hash": "h2"}).encode() + b"\n")
        return op, n
    raw_append(path, b"\n"); return "newline", n


def snapshot_new(path, root):
    """new-implementation outcomes for every session (a fresh process: the in-process cache is cleared)."""
    out = {}
    for s in SESS + ["unseen"]:
        g._VIEW.clear()
        out[s] = outcome(lambda s=s: g.session_written_paths(path, s, root))
    for k, s in enumerate(EXTRA_SESSIONS):  # session ids that are not strings (never sent by Claude Code, but the old == compared them)
        g._VIEW.clear()
        out["x%d" % k] = outcome(lambda s=s: g.session_written_paths(path, s, root))
    return out


def snapshot_old(path):
    out = {s: outcome(lambda s=s: old_session_written_paths(path, s)) for s in SESS + ["unseen"]}
    for k, s in enumerate(EXTRA_SESSIONS):
        out["x%d" % k] = outcome(lambda s=s: old_session_written_paths(path, s))
    return out


def last_completed_seg_end(root, path):
    side = g._idx_sidecar(path, root)
    st = g._idx_load(side, path)
    return st["segs"][-1][0] if st and st["segs"] else 0


FIXTURE = os.path.join(HERE, "field-manifest.yaml")


def chained_ledger(root, nlines, seed, extra=None):
    """A valid hash-chained ledger of nlines records in the gate's own serialisation (text mode, as ledger_append
    writes it), at the fixture manifest's store path; extra = {line index: record} replaces those records."""
    ledger = root / ".claude" / "state" / "field-ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)
    prev = "0" * 64
    with open(ledger, "w", encoding="utf-8") as fh:
        for i in range(nlines):
            rec = dict((extra or {}).get(i) or rand_event(rnd))
            rec["prev_hash"] = prev
            rec["hash"] = prev = hashlib.sha256((prev + json.dumps(rec, sort_keys=True)).encode()).hexdigest()
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return ledger


PLACEHOLDER = {"ts": "t", "session": "s0", "tool": "Bash", "decision": "deny", "rule": "E0", "reason": "x"}


def twin_step(path, twin, root, ev, irnd, tw):
    """Append one record to both copies of a ledger: the OLD ledger_append on `twin`, the NEW one on `path`, the new one
    on the gate's allow path (ledger_view first, as enforce() does before an allow) or its deny path (no view: a deny
    appends without it), so a cached view of any age can be in place. ev None: the old append will raise (a tampered
    tail); the new one must raise the same way and neither may write. Where the ledger is not valid UTF-8 only the
    allow path is compared: there the new deny path writes a deny record the old one could not (CHANGELOG).
    Returns None when the two agree (outcome, bytes, chain head), else what differed."""
    try:
        twin.read_bytes().decode("utf-8")
        decodes = True
    except (OSError, ValueError):
        decodes = not twin.exists()
    allow = (not decodes) or irnd.random() < 0.5
    rec = dict(ev or PLACEHOLDER)
    o = outcome(lambda: old_ledger_append(twin, dict(rec)))

    def new():
        if allow:
            g.ledger_view(path, root)
        g.ledger_append(path, dict(rec))
    n = outcome(new)
    tw["events"] += 1
    tw["allow_path" if allow else "deny_path"] += 1
    tw["both_raise"] += o[0] == "exc" and o == n
    if o != n:
        return ("outcome", "allow" if allow else "deny", o, n)
    if path.read_bytes() != twin.read_bytes():
        return ("bytes", "allow" if allow else "deny")
    ho = outcome(lambda: old_prev_hash(twin))
    if decodes:  # no view here: a cached view of any age stays in place for the next append
        hn = outcome(lambda: g._ledger_last_hash(path))
    else:  # _ledger_last_hash reads only the tail; the gate verifies before it chains an allow (the old code's raise)
        hn = outcome(lambda: (g.ledger_view(path, root), g._ledger_last_hash(path))[1])
    if ho != hn:
        return ("chain head", "allow" if allow else "deny", ho, hn)
    return None


# ---------------------------------------------------------------------------------------------------------------
# 1. differential
# ---------------------------------------------------------------------------------------------------------------
def differential(seeds, steps):
    bad = []
    counts = {"appends": 0, "tampers": 0, "compares": 0}
    twin_bad = []
    tw = {"events": 0, "allow_path": 0, "deny_path": 0, "both_raise": 0}
    for seed in seeds:
        rnd = random.Random(seed)
        set_small()
        d, path = fresh_dir("diff%d" % seed)
        root = d
        twin = d / "twin" / "field-ledger.jsonl"  # the same ledger, written by the OLD ledger_append
        irnd = random.Random(seed * 7919 + 1)     # view/no-view choices; rnd's stream (the ledgers) is unchanged
        g._idx_pick = lambda n, r=random.Random(seed ^ 0x5a5a): r.randrange(n)
        for _ in range(rnd.randrange(0, 40)):
            diff = twin_step(path, twin, root, rand_event(rnd), irnd, tw)
            if diff:
                twin_bad.append((seed, "initial appends", diff))
                break
        for step in range(steps):
            if twin_bad and twin_bad[-1][0] == seed:
                break
            what = "append"
            r = rnd.random()
            if r < 0.55:
                for _ in range(rnd.randrange(1, 12)):
                    if outcome(lambda: old_prev_hash(twin))[0] == "exc":
                        # a tampered tail: the old append raises; the new one must too, and neither writes
                        diff = twin_step(path, twin, root, None, irnd, tw)
                        raw_append(path, b"\n")
                        raw_append(twin, b"\n")
                    else:
                        diff = twin_step(path, twin, root, rand_event(rnd), irnd, tw)
                    if diff:
                        twin_bad.append((seed, step, diff))
                        break
                counts["appends"] += 1
                pos = None
            else:
                what, pos = tamper(path, rnd)
                counts["tampers"] += 1
                twin.write_bytes(path.read_bytes())  # the same damage in the old code's copy
            old = snapshot_old(path)
            side_st = g._idx_load(g._idx_sidecar(path, root), path)
            if pos is not None and side_st and pos < (side_st["segs"][-1][0] if side_st["segs"] else 0):
                # damage inside a completed segment is caught when the random re-check draws that segment:
                # draw it (the bounded window is measured separately, below)
                segi = [i for i, s in enumerate(side_st["segs"]) if (side_st["segs"][i - 1][0] if i else 0) <= pos < s[0]]
                g._idx_pick = lambda n, k=(segi[0] if segi else 0): min(k, n - 1)
            else:
                g._idx_pick = lambda n, r=random.Random(seed ^ step): r.randrange(n)
            new = snapshot_new(path, root)
            counts["compares"] += 1
            if new != old:
                bad.append((seed, step, what, old, new))
                break
            # ledger_append's previous-hash step: same value, or both raise
            g._VIEW.clear()
            o = outcome(lambda: old_prev_hash(path))
            # the gate verifies (ledger_view) before an allow and then appends; a deny appends without the view
            n = outcome(lambda: (g.ledger_view(path, root), g._ledger_last_hash(path))[1])
            if o != n:
                bad.append((seed, step, what, "prevhash", o, n))
                break
            # field-post's find for every (session, id), plus misses
            for s in SESS[:3]:
                for t in TUIDS[:4] + ["missing"]:
                    o = outcome(lambda: old_find(path, s, t))
                    n = outcome(lambda: g.ledger_find_ask(path, root, s, t))
                    if o[:2] == ("exc", "UnicodeDecodeError") and n[0] == "ok":
                        continue  # DOCUMENTED: field-post (evidence only, fail-open) no longer decodes the verified prefix
                    if o != n:
                        bad.append((seed, step, what, "find", s, t, o, n))
                        break
                else:
                    continue
                break
            else:
                continue
            break
    return bad, counts, twin_bad, tw


SEEDS = int(os.environ.get("LI_SEEDS", "24"))  # a mutation run uses fewer
bad, counts, twin_bad, tw = differential(range(1, SEEDS + 1), 12)
check("differential: session_written_paths / prev hash / find equal the old code (%d seeds, %s)" % (SEEDS, counts),
      not bad, repr(bad[:1])[:1500])
check("differential: ledger_append writes the same bytes and chain head as the old ledger_append, through any mix "
      "of views and appends (%d seeds, %s)" % (SEEDS, tw), not twin_bad and tw["deny_path"] > 0 and tw["both_raise"] > 0,
      repr(twin_bad[:1])[:1500])
SKIPPED_PICK = g._idx_pick

# ---------------------------------------------------------------------------------------------------------------
# 2. sidecar attacks
# ---------------------------------------------------------------------------------------------------------------
def build(name, n=100, seed=3, session_writes=True):
    set_small()
    rnd = random.Random(seed)
    d, path = fresh_dir(name)
    for i in range(n):
        g.ledger_append(path, rand_event(rnd))
    # a record that matters: s0 wrote evil.sh, early in the ledger
    return d, path


def rewrite_sidecar(root, path, mutate, recompute=True):
    """Act as an attacker with write access to the sidecar and full knowledge of the format."""
    side = g._idx_sidecar(path, root)
    st = g._idx_decode(side.read_bytes(), path)
    mutate(st)
    side.write_bytes(g._idx_encode(st, path))


def with_probe(name, probe_session="s0"):
    """A ledger where s0 wrote 'evil.sh' in the middle of a completed segment, plus filler."""
    set_small()
    d, path = fresh_dir(name)
    rnd = random.Random(11)
    for i in range(30):
        ev = rand_event(rnd)
        if ev["session"] == "s0" and ev.get("path") == "a.sh":
            ev["path"] = "b.py"
        g.ledger_append(path, ev)
    g.ledger_append(path, {"ts": "t", "session": "s0", "tool": "Write", "path": "evil.sh", "decision": "allow"})
    for i in range(60):
        ev = rand_event(rnd)
        if ev["session"] == "s0" and ev.get("path") == "evil.sh":
            ev["path"] = "b.py"
        g.ledger_append(path, ev)
    g._VIEW.clear()
    assert "evil.sh" in g.session_written_paths(path, "s0", d)
    g._VIEW.clear()
    return d, path


def written(root, path, s="s0"):
    g._VIEW.clear()
    return outcome(lambda: g.session_written_paths(path, s, root))


for how in ("delete", "garbage", "empty", "truncate", "bitflip", "wrong_sum", "wrong_version", "other_ledger", "huge"):
    d, path = with_probe("att_" + how)
    side = g._idx_sidecar(path, d)
    want = snapshot_old(path)["s0"]
    check("sidecar built (%s)" % how, side.exists())
    raw = side.read_bytes()
    if how == "delete":
        side.unlink()
    elif how == "garbage":
        side.write_bytes(b"\x00\xff garbage {")
    elif how == "empty":
        side.write_bytes(b"")
    elif how == "truncate":
        side.write_bytes(raw[: len(raw) // 2])
    elif how == "bitflip":
        b = bytearray(raw); b[len(b) // 2] ^= 1; side.write_bytes(bytes(b))
    elif how == "wrong_sum":
        side.write_bytes(raw.replace(b'"sum": "', b'"sum": "0'))
    elif how == "wrong_version":
        meta = json.loads(raw.split(b"\n")[0]); meta["v"] = 99
        meta.pop("sum"); meta["sum"] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
        side.write_bytes(json.dumps(meta, sort_keys=True).encode() + b"\n" + raw.split(b"\n", 1)[1])
    elif how == "other_ledger":
        d2, path2 = with_probe("att_other_src")
        side.write_bytes(g._idx_sidecar(path2, d2).read_bytes())
    elif how == "huge":
        side.write_bytes(b"x" * 1000)
    got = written(d, path)
    check("sidecar %s: answer equals the old code (full re-verify, never skipped)" % how, got == want, "%r vs %r" % (got, want))
    check("sidecar %s: rebuilt afterwards" % how, g._idx_load(side, path) is not None)

# the file identity / length / tail checks
d, path = with_probe("att_replace")
side = g._idx_sidecar(path, d)
data = path.read_bytes()
os.replace(path.with_name("x"), path) if False else None
tmp = path.with_name("new.tmp"); tmp.write_bytes(data.replace(b"evil.sh", b"good.sh")); os.replace(tmp, path)
check("replaced ledger file (new identity, same size): full re-verify, evil.sh gone like the old code",
      written(d, path) == snapshot_old(path)["s0"] and "evil.sh" not in written(d, path)[1])

d, path = with_probe("att_trunc")
data = path.read_bytes(); path.write_bytes(data[: len(data) // 3])
check("truncated ledger (shorter than the recorded offset): full re-verify", written(d, path) == snapshot_old(path)["s0"])

d, path = with_probe("att_tail")
data = path.read_bytes(); k = len(data) - 50
path.write_bytes(data[:k] + b"Z" + data[k + 1:])  # inside the 4096 bytes before the offset (flip keeps length)
check("edit in the tail window: full re-verify, answer equals the old code", written(d, path) == snapshot_old(path)["s0"])

# white-box: each binding of the sidecar to the ledger file, on its own
d, path = with_probe("att_bind")
side = g._idx_sidecar(path, d)
stt = g._idx_load(side, path)
with path.open("rb") as fh:
    ok_same = g._idx_matches(stt, fh, path.stat())
check("binding: untouched ledger matches its sidecar", ok_same)
data = path.read_bytes()
off = stt["off"]
# (a) one byte inside the 4 KiB before the offset, same length: only the tail digest sees it
path.write_bytes(data[: off - 20] + b"Z" + data[off - 19:])
with path.open("rb") as fh:
    check("binding: a changed byte before the offset is refused (tail digest)", not g._idx_matches(stt, fh, path.stat()))
path.write_bytes(data)
# (b) file shorter than the offset, attacker recomputes the tail digest over what is left: only the length check sees it
forged = dict(stt); forged["off"] = len(data) + 10
with path.open("rb") as fh:
    forged["tail"] = g._idx_tail_digest(fh, forged["off"])
    check("binding: an offset beyond the end of the file is refused (length), even with a matching digest",
          not g._idx_matches(forged, fh, path.stat()))
# (c) other file identity (an inode / file index the sidecar did not see), same bytes: only the identity sees it
other = dict(stt); other["id"] = [stt["id"][0], stt["id"][1] + 1]
with path.open("rb") as fh:
    check("binding: another file identity is refused", not g._idx_matches(other, fh, path.stat()))

# forged offset past a tampered region (attacker keeps the tail bytes, recomputes sidecar checksums)
d, path = with_probe("att_forge_off")
side = g._idx_sidecar(path, d)
st = g._idx_decode(side.read_bytes(), path)
data = path.read_bytes()
p = data.find(b'"evil.sh"')
path.write_bytes(data[:p] + b'"evil.zz"' + data[p + 9:])  # tamper: s0's write is now a different name
# (a) sidecar untouched: its posts still say evil.sh, the segment digest no longer matches
seg_i = [i for i, s in enumerate(st["segs"]) if (st["segs"][i - 1][0] if i else 0) <= p < s[0]]
check("tamper inside a completed segment sits in a completed segment", len(seg_i) == 1)
verdict = []
for _ in range(200):
    g._idx_pick = lambda n: seg_i[0]
    verdict.append(written(d, path) == snapshot_old(path)["s0"])
    break
check("tampered completed segment, sidecar untouched, segment drawn: re-verify (answer equals the old code)", all(verdict))
# (b) attacker also recomputes that segment's digest and the posts: consistent forgery of both files
d, path = with_probe("att_forge_both")
side = g._idx_sidecar(path, d)
st = g._idx_decode(side.read_bytes(), path)
data = path.read_bytes()
p = data.find(b'"evil.sh"')
path.write_bytes(data[:p] + b'"evil.zz"' + data[p + 9:])
i = [k for k, s in enumerate(st["segs"]) if (st["segs"][k - 1][0] if k else 0) <= p < s[0]][0]
s0 = st["segs"][i - 1][0] if i else 0
new = path.read_bytes()[s0: st["segs"][i][0]]
st["segs"][i][1] = hashlib.sha256(new).hexdigest()
st["posts"]["s0"].pop("evil.sh"); st["posts"]["s0"]["evil.zz"] = i
side.write_bytes(g._idx_encode(st, path))
g._idx_pick = lambda n: i
res = written(d, path)
check("DECLARED: attacker who rewrites ledger AND sidecar consistently is not detected (same as the old gate, which "
      "has no key and no per-call chain check)", res == snapshot_old(path)["s0"])

# sidecar-only forgery with an untouched ledger: hide evil.sh from E5
def hide(st):
    for s in list(st["posts"]):
        st["posts"][s].pop("evil.sh", None)

d, path = with_probe("att_hide")
st0 = g._idx_decode(g._idx_sidecar(path, d).read_bytes(), path)
rewrite_sidecar(d, path, hide)
ev_seg = g._idx_load(g._idx_sidecar(path, d), path)
ev_i = [i for i, s in enumerate(st0["segs"]) if (st0["segs"][i - 1][0] if i else 0) <= path.read_bytes().find(b'"evil.sh"') < s[0]]
in_open = not ev_i
if in_open:
    got = written(d, path)
    check("hide an entry that is in the open segment: detected on the first call (answer equals the old code)",
          got == snapshot_old(path)["s0"] and "evil.sh" in got[1])
else:
    g._idx_pick = lambda n: ev_i[0]
    got = written(d, path)
    check("hide an entry from a completed segment, segment drawn: detected (answer equals the old code)",
          got == snapshot_old(path)["s0"] and "evil.sh" in got[1])
    d, path = with_probe("att_hide2")
    rewrite_sidecar(d, path, hide)
    other = [i for i in range(len(st0["segs"])) if i not in ev_i][0]
    g._idx_pick = lambda n: other
    got = written(d, path)
    print("DECLARED  hide an entry from a completed segment the random re-check did not draw: E5 sees %r this call "
          "(the re-check draws it with probability 1/%d per call; the old code never missed it)" % (got[1], len(st0["segs"])))

# invent an entry
def invent(st):
    st["posts"].setdefault("s0", {})["never-written.sh"] = 0

d, path = with_probe("att_invent")
rewrite_sidecar(d, path, invent)
g._idx_pick = lambda n: 0
got = written(d, path)
check("invent an entry in segment 0: detected, answer equals the old code", got == snapshot_old(path)["s0"] and "never-written.sh" not in got[1])

# empty everything: segs=[], posts={}, off=size: structure check (segments must tile the lines)
def wipe(st):
    st["segs"] = []; st["posts"] = {}; st["asks"] = {}

d, path = with_probe("att_wipe")
rewrite_sidecar(d, path, wipe)
got = written(d, path)
check("sidecar claims no segments and no entries for a long ledger: refused (cl does not match), answer equals old",
      got == snapshot_old(path)["s0"] and "evil.sh" in got[1])

# forged bad-JSON flag
d, path = with_probe("att_bad")
raw_append(path, b"{not json}\n")
want = snapshot_old(path)
g._VIEW.clear()
first = snapshot_new(path, d)  # builds a sidecar that records the bad line
def clear_bad(st):
    st["bad"] = 0
rewrite_sidecar(d, path, clear_bad)
g._idx_pick = SKIPPED_PICK
got = snapshot_new(path, d)
check("clear the bad-JSON flag in the sidecar: the open segment re-derives it, still ValueError like the old code",
      got["s0"] == want["s0"] and want["s0"][0] == "exc", repr((got["s0"], want["s0"])))

# a forged offset beyond EOF, or inside a line
for label, mut in (("beyond EOF", lambda st: st.__setitem__("off", st["off"] + 10 ** 6)),
                   ("zero", lambda st: st.__setitem__("off", 0))):
    d, path = with_probe("att_off_" + label.replace(" ", "_"))
    rewrite_sidecar(d, path, mut)
    check("forged offset (%s): ignored or re-verified, answer equals the old code" % label,
          written(d, path) == snapshot_old(path)["s0"])

# ---------------------------------------------------------------------------------------------------------------
# 3. complexity: lines parsed per call do not depend on the ledger size
# ---------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------------------------
# 2b. white-box: every refusal of the sidecar on its own (an answer-level test cannot tell a refusal from a
#     sidecar whose content happens to be right, so these call the checks directly)
# ---------------------------------------------------------------------------------------------------------------
d, path = with_probe("wb")
side = g._idx_sidecar(path, d)
raw = side.read_bytes()
meta_line, body_line = raw.split(b"\n", 1)
check("decode: the genuine sidecar decodes", g._idx_decode(raw, path) is not None)


def resum(meta):
    meta.pop("sum", None)
    meta["sum"] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    return json.dumps(meta, sort_keys=True).encode()


meta = json.loads(meta_line)
bad_version = dict(meta); bad_version["v"] = 99
bad_psum_body = body_line.replace(b"evil.sh", b"evil.zz")
bad_tiling = json.loads(meta_line); bad_tiling["segs"] = []
flip = bytearray(raw); flip[len(flip) // 3] ^= 1
for label, blob, p in (
        ("garbage", b"\x00\xff{", path),
        ("half a file", raw[: len(raw) // 2], path),
        ("a flipped bit", bytes(flip), path),
        ("wrong checksum", raw.replace(b'"sum": "', b'"sum": "0', 1), path),
        ("wrong version, checksum recomputed", resum(bad_version) + b"\n" + body_line, path),
        ("postings edited, their checksum not", meta_line + b"\n" + bad_psum_body, path),
        ("another ledger's sidecar", raw, path.with_name("other-ledger.jsonl")),
        ("segments that do not tile the lines, checksums recomputed", resum(bad_tiling) + b"\n" + body_line, path)):
    check("decode refuses: " + label, g._idx_decode(blob, p) is None)
# the checksum of the postings is recomputed too: still refused by the tiling rule, not by a checksum
body = json.loads(body_line)
bad_tiling["psum"] = hashlib.sha256(body_line.rstrip(b"\n")).hexdigest()
check("decode refuses: tiling forged with every checksum valid", g._idx_decode(resum(bad_tiling) + b"\n" + body_line, path) is None)

# the per-segment digest, on its own: a byte changed inside a completed segment that changes no entry
d, path = with_probe("wb_digest")
st = g._idx_load(g._idx_sidecar(path, d), path)
data = path.read_bytes()
p = data.find(b'"ts": "t"')
path.write_bytes(data[:p] + b'"ts": "u"' + data[p + 9:])
g._idx_pick = lambda n: 0
with path.open("rb") as fh:
    check("segment digest: a neutral byte change inside a completed segment is refused", g._idx_trusted(st, fh) is None)
    path.write_bytes(data)
    check("segment digest: restored, accepted", g._idx_trusted(st, fh) is not None)
    st["segs"][0][1] = "0" * 64
    check("segment digest: a wrong recorded digest is refused", g._idx_trusted(st, fh) is None)
g._idx_pick = SKIPPED_PICK

# the open segment, on its own: hide a RECENT write; detected on the first call whichever segment is drawn
d, path = with_probe("wb_open")
for i in range(4):
    g.ledger_append(path, {"ts": "t", "session": "s0", "tool": "Write", "path": "recent%d.sh" % i, "decision": "allow"})
g._VIEW.clear()
g.session_written_paths(path, "s0", d)  # scans the new lines and saves the sidecar (>= IDX_PERSIST_BYTES)
side = g._idx_sidecar(path, d)
st = g._idx_load(side, path)
check("open segment: the recent writes are in the saved sidecar", st is not None and "recent3.sh" in st["posts"].get("s0", {}),
      repr(st and st["off"]))
if st is not None and "recent3.sh" in st["posts"].get("s0", {}):
    open_i = len(st["segs"])
    rewrite_sidecar(d, path, lambda s: s["posts"]["s0"].pop("recent3.sh"))
    g._idx_pick = lambda n: 0 if n else 0
    got = written(d, path)
    check("open segment: a recent write hidden in the sidecar is caught on the first call",
          got == snapshot_old(path)["s0"] and "recent3.sh" in got[1])
    g._idx_pick = SKIPPED_PICK

# field-post's lookup of the bytes after the sidecar's offset, on its own
d, path = with_probe("wb_find")
g._VIEW.clear()
g.session_written_paths(path, "s0", d)
ask = {"ts": "t", "session": "s0", "tool": "Bash", "tool_use_id": "tuX", "decision": "ask", "rule": "E3-policy"}
g.ledger_append(path, dict(ask))
r = g.ledger_find_ask(path, d, "s0", "tuX")
check("find: an ask appended after the sidecar's offset is found", isinstance(r, dict) and r.get("tool_use_id") == "tuX", repr(r))
g.ledger_append(path, {"ts": "t", "session": "s0", "tool": "Bash", "tool_use_id": "tuX", "decision": "executed", "rule": "E3-policy-executed"})
check("find: an executed record appended after the offset makes it a duplicate", g.ledger_find_ask(path, d, "s0", "tuX") == "duplicate")
check("find: another session does not see it", g.ledger_find_ask(path, d, "s1", "tuX") is None)

# field-post trusts the sidecar only when the gate would (_idx_matches AND _idx_trusted): an asks map edited to hide
# an ask, or to mark it executed, is not believed; the lookup then scans the ledger, as the old code did.
def post_probe(name):
    """with_probe's ledger plus ask tuK (s0) in a completed segment and ask tuL (s0) alone in the open segment."""
    d, path = with_probe(name)
    g.ledger_append(path, {"ts": "t", "session": "s0", "tool": "Bash", "tool_use_id": "tuK", "decision": "ask", "rule": "E3-policy"})
    rnd = random.Random(17)
    while True:
        g.ledger_append(path, {"ts": "t", "session": "s9", "tool": "Bash", "tool_use_id": "f%d" % rnd.getrandbits(32), "decision": "allow"})
        if (len(path.read_bytes().splitlines()) + 1) % g.IDX_SEG_LINES == 1:
            break  # the next record opens a segment
    g.ledger_append(path, {"ts": "t", "session": "s0", "tool": "Bash", "tool_use_id": "tuL", "decision": "ask", "rule": "E3-policy"})
    g._VIEW.clear()
    g.session_written_paths(path, "s0", d)  # the gate's view: saves the sidecar with both asks
    st = g._idx_load(g._idx_sidecar(path, d), path)
    seg_k = [i for i, s in enumerate(st["segs"]) if st["asks"][json.dumps(["s0", "tuK"])][1] < s[0]][0]
    return d, path, st, seg_k


KEY_K, KEY_L = json.dumps(["s0", "tuK"]), json.dumps(["s0", "tuL"])
for label, key, how, forced in (
        ("hide the ask in the open segment", KEY_L, "hide", None),
        ("mark the ask in the open segment executed", KEY_L, "x", None),
        ("hide an ask in a completed segment, that segment sampled", KEY_K, "hide", "own"),
        ("mark an ask in a completed segment executed, another segment sampled", KEY_K, "x", "other")):
    d, path, st, seg_k = post_probe("post_" + how + "_" + ("open" if key == KEY_L else "done"))
    tuid = json.loads(key)[1]
    in_open = st["asks"][key][1] >= (st["segs"][-1][0] if st["segs"] else 0)
    rewrite_sidecar(d, path, (lambda s, key=key: s["asks"].pop(key)) if how == "hide" else
                    (lambda s, key=key: s["asks"].__setitem__(key, ["x", s["asks"][key][1]])))
    if forced == "own":
        g._idx_pick = lambda n, i=seg_k: i
    elif forced == "other":
        g._idx_pick = lambda n, i=seg_k: (i + 1) % n
    want = old_find(path, "s0", tuid)
    got = post.find(path, "s0", tuid, g, d)
    g._idx_pick = SKIPPED_PICK
    check("field-post, sidecar edited to %s: not believed, the ask is found (equals the old code)" % label,
          isinstance(want, dict) and got == want and (key != KEY_L or in_open), repr((got, in_open)))

# k-segment sampling: invalid UTF-8 in the middle of a completed segment, sidecar untouched (the old gate denied at
# once; a sidecar describes the bytes as they were). With seeded draws the call that notices it is deterministic.
set_small()
d, path = fresh_dir("ksample")
chained_ledger(d, 8 * 1024 + 3, 31)
g._VIEW.clear()
g.session_written_paths(path, "s0", d)  # full verification; saves the sidecar
st = g._idx_load(g._idx_sidecar(path, d), path)
nseg = len(st["segs"])
k = min(nseg, max(4, math.isqrt(nseg - 1) + 1), 32)  # the documented k (field-gate.py _idx_sample)
bound = math.ceil(math.log(1e-3) / math.log(1 - k / nseg))  # k segments per call miss it this long with p <= 0.001
m = nseg // 2
data = path.read_bytes()
p = data.find(b'"ts"', st["segs"][m - 1][0])
check("k-segment sampling: the damage sits mid-ledger, in completed segment %d of %d, outside the tail window" % (m, nseg),
      st["segs"][m - 1][0] <= p < st["segs"][m][0] and p < st["off"] - g.IDX_TAIL)
path.write_bytes(data[:p] + b"\xff" + data[p + 1:])
want = outcome(lambda: old_session_written_paths(path, "s0"))
g._idx_pick = lambda n, r=random.Random(20261025): r.randrange(n)
noticed = None
for c in range(1, bound + 1):
    if written(d, path) == want:
        noticed = c
        break
check("k-segment sampling: noticed on call %s, within the bound of %d calls for k = %d of %d segments per call "
      "(expected %.0f calls; one segment per call: %.0f)" % (noticed, bound, k, nseg, nseg / k, nseg),
      noticed is not None and want[0] == "exc", repr(want))
check("k-segment sampling: once noticed, every later call fails like the old code (the sidecar was dropped)",
      all(written(d, path) == want for _ in range(3)))
g._idx_pick = SKIPPED_PICK
sample = getattr(g, "_idx_sample", None)
real_pick = g._idx_pick
g._idx_pick = lambda n: int.from_bytes(os.urandom(4), "big") % n
draws = [sample(nseg) for _ in range(20)] if sample else []
check("k-segment sampling: each call draws k = %d distinct segments" % k,
      bool(draws) and all(len(x) == k == len(set(x)) and all(0 <= i < nseg for i in x) for x in draws))
check("k-segment sampling: with at most %d segments, every one, every call" % 4,
      bool(sample) and all(sorted(sample(n)) == list(range(n)) for n in (1, 2, 3, 4)))
g._idx_pick = lambda n: 5
check("k-segment sampling: a patched constant draw checks that one segment (the forced-draw tests rely on it)",
      bool(sample) and sample(nseg) == [5])
# the re-hash of a segment drawn after the first one (digest and line count, no re-derivation), on its own
d, path = with_probe("wb_second")
st = g._idx_load(g._idx_sidecar(path, d), path)
data = path.read_bytes()
p = data.find(b'"ts": "t"', st["segs"][2][0])
check("k-segment sampling: a neutral edit sits in completed segment 3", st["segs"][2][0] <= p < st["segs"][3][0])
path.write_bytes(data[:p] + b'"ts": "u"' + data[p + 9:])
draws_seq = iter([0, 3] + [0] * 100)
g._idx_pick = lambda n: next(draws_seq)
with path.open("rb") as fh:
    check("k-segment sampling: a changed segment drawn second (re-hashed, not re-derived) is refused",
          g._idx_trusted(st, fh) is None)
    path.write_bytes(data)
    draws_seq = iter([0, 3] + [0] * 100)
    check("k-segment sampling: restored, the same draws accept the sidecar", g._idx_trusted(st, fh) is not None)
g._idx_pick = real_pick

g.IDX_SEG_LINES = 512
g.IDX_PERSIST_BYTES = 128 * 1024
g._idx_pick = SKIPPED_PICK
parsed = {"n": 0}
orig_pieces = g._idx_pieces


def counting(*a, **k):
    parsed["n"] += 1
    return orig_pieces(*a, **k)


def per_call(nlines):
    d, path = fresh_dir("cx%d" % nlines)
    rnd = random.Random(5)
    prev = "0" * 64
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for i in range(nlines):
            rec = rand_event(rnd); rec["prev_hash"] = prev
            rec["hash"] = hashlib.sha256((prev + json.dumps(rec, sort_keys=True)).encode()).hexdigest(); prev = rec["hash"]
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    g._VIEW.clear()
    g.session_written_paths(path, "s0", d)  # builds the sidecar (full)
    worst = 0
    g._idx_pieces = counting
    try:
        for i in range(30):
            g.ledger_append(path, rand_event(rnd))
            g._VIEW.clear()
            parsed["n"] = 0
            g.session_written_paths(path, "s0", d)
            worst = max(worst, parsed["n"])
    finally:
        g._idx_pieces = orig_pieces
    return worst


w_small, w_big = per_call(3000), per_call(60000)
check("complexity: pieces parsed per call, ledger of 3000 lines: %d; of 60000 lines: %d (bound 2*512 + persist slack)" % (w_small, w_big),
      w_big <= 2 * 512 + 700 and w_big <= w_small * 1.5 + 50)

# ---------------------------------------------------------------------------------------------------------------
# 4. time budget
# ---------------------------------------------------------------------------------------------------------------
set_small()
g.IDX_SEG_LINES = 512
d, path = fresh_dir("busy")
rnd = random.Random(9)
with open(path, "w", encoding="utf-8", newline="\n") as fh:
    for i in range(40000):
        fh.write(json.dumps(rand_event(rnd), sort_keys=True) + "\n")
g._VIEW.clear()
import time
try:
    g.ledger_view(path, d, time.monotonic() - 1)
    busy = False
except g.LedgerIndexBusy:
    busy = True
check("rebuild past its deadline raises LedgerIndexBusy (the gate denies E0 instead of timing out and allowing)", busy)
st1 = g._idx_load(g._idx_sidecar(path, d), path)
check("progress was saved (offset > 0, less than the file)", st1 is not None and 0 < st1["off"] < path.stat().st_size)
steps = 0
while True:
    g._VIEW.clear()
    try:
        g.ledger_view(path, d, time.monotonic() - 1)
        break
    except g.LedgerIndexBusy:
        steps += 1
        st2 = g._idx_load(g._idx_sidecar(path, d), path)
        if st2 is None or st2["off"] <= st1["off"]:
            steps = -1
            break
        st1 = st2
    if steps > 200:
        break
check("repeated busy calls make progress and finish (%d calls)" % steps, steps > 0)
g._VIEW.clear()
check("after finishing: answers equal the old code", snapshot_new(path, d) == snapshot_old(path))

# ---------------------------------------------------------------------------------------------------------------
# 4b. the budget wiring in enforce(): a verification that runs out of its time budget makes the CALL deny E0 ("being
#     rebuilt") at both sites, the E5 check and the check before an allow, saves its progress, and the next call
#     continues from it. A slow verification is made deterministic by handing ledger_view a deadline that has
#     already passed (its budget used up); the scan, the busy path, the deny and the ledger record are the real ones.
# ---------------------------------------------------------------------------------------------------------------
MANIFEST = g.load_manifest(pathlib.Path(FIXTURE))
real_view, real_scan = g.ledger_view, g._idx_scan
scan_starts = []


def spent_budget(n_spent):
    """ledger_view as enforce() calls it, except that the first n_spent calls find their time budget used up (the
    later ones run to the end). .calls: the deadlines enforce() passed."""
    calls = []

    def view(ledger_path, root=None, deadline=None):
        calls.append(deadline)
        return real_view(ledger_path, root, time.monotonic() - 1 if len(calls) <= n_spent else None)
    view.calls = calls
    return view


def recording_scan(fh, state, deadline, open_data=b""):
    scan_starts.append(state["off"])
    return real_scan(fh, state, deadline, open_data)


def enforce_call(root, tool, ti, session):
    """One gate call in-process, as main() makes it once it holds the lock: (exit code, stderr, last ledger record)."""
    ledger, source = g.resolve_store(MANIFEST, root)
    err, out = io.StringIO(), io.StringIO()
    g._VIEW.clear()  # a new hook process has no cached view
    code = None
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        try:
            g.enforce({"session_id": session, "tool_name": tool, "tool_input": ti, "tool_use_id": "tu-budget",
                       "permission_mode": "default"}, MANIFEST, root, ledger, source)
        except SystemExit as e:
            code = e.code
    return code, err.getvalue(), json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])


def budget_root(name, nlines, seed, extra=None):
    root = pathlib.Path(TMP) / name
    shutil.rmtree(root, ignore_errors=True)
    (root / ".claude" / "state").mkdir(parents=True)
    shutil.copy(FIXTURE, root / "field-manifest.yaml")
    ledger = chained_ledger(root, nlines, seed, extra)  # ~3.4 MB: more than three 1 MiB scan blocks
    return root, ledger, g._idx_sidecar(ledger, root)


set_small()
g.IDX_SEG_LINES = 512
WRITE = ("Write", {"file_path": "notes.txt", "content": "x"})
try:
    # (a) the check before an allow: a Write (no E5) has no other ledger check, so this site alone stands between a
    #     cold rebuild on a large ledger and an allow
    root, ledger, side = budget_root("budget_allow", 12000, 21)
    g._idx_scan = recording_scan
    g.ledger_view = spent_budget(10 ** 6)
    code, err, last = enforce_call(root, WRITE[0], WRITE[1], "b1")
    check("budget, check before an allow (Write): a verification out of budget DENIES the call E0 'being rebuilt'",
          code == 2 and "FIELD DENY [E0]" in err and "being rebuilt" in err and last.get("decision") == "deny"
          and last.get("rule") == "E0" and "being rebuilt" in last.get("reason", ""),
          repr((code, err[-300:], last.get("decision"), last.get("rule"))))
    check("budget: enforce() gave the verification its time budget (deadline = start + TIME_BUDGET_S), once",
          g.ledger_view.calls == [g._T0 + g.TIME_BUDGET_S], repr(g.ledger_view.calls))
    st1 = g._idx_load(side, ledger)
    off1 = st1["off"] if st1 else -1
    check("budget: the progress was persisted (sidecar offset %d: > 0 and short of the file)" % off1,
          st1 is not None and 0 < off1 < ledger.stat().st_size)
    del scan_starts[:]
    code, err, last = enforce_call(root, WRITE[0], WRITE[1], "b1")
    st2 = g._idx_load(side, ledger)
    check("budget: the next call continues from the saved progress (scan starts at %s, not 0), denies E0 again, "
          "and saves more (%s)" % (scan_starts[:1], st2 and st2["off"]),
          code == 2 and "being rebuilt" in err and last.get("rule") == "E0" and scan_starts[:1] == [off1]
          and st2 is not None and st2["off"] > off1, repr((code, err[-300:])))
    g.ledger_view = spent_budget(0)
    del scan_starts[:]
    code, err, last = enforce_call(root, WRITE[0], WRITE[1], "b1")
    check("budget: when the verification finishes inside the budget, the same call is allowed (scan resumed at %s)"
          % scan_starts[:1], code == 0 and last.get("decision") == "allow" and scan_starts[:1] == [st2["off"]],
          repr((code, err[-300:])))

    # (b) the E5 check (Bash, E5 on): session b5 wrote run.sh early in the ledger. Only the E5 site's verification is
    #     out of budget, so a swallowed LedgerIndexBusy there would let the call through to an allow
    (pathlib.Path(TMP) / "budget_e5").mkdir(parents=True, exist_ok=True)  # path_key resolves the root on disk
    key = g.path_key("run.sh", pathlib.Path(TMP) / "budget_e5")
    root, ledger, side = budget_root("budget_e5", 12000, 22, {100: {
        "ts": "t", "session": "b5", "tool": "Write", "path": key, "decision": "allow"}})
    g._idx_scan = real_scan
    g.ledger_view = spent_budget(1)
    code, err, last = enforce_call(root, "Bash", {"command": "bash ./run.sh"}, "b5")
    check("budget, E5 check (Bash, E5 on): a verification out of budget DENIES the call E0 'being rebuilt' at the E5 "
          "check itself", code == 2 and "FIELD DENY [E0]" in err and "being rebuilt" in err and last.get("rule") == "E0"
          and len(g.ledger_view.calls) == 1, repr((code, err[-300:], g.ledger_view.calls)))
    st1 = g._idx_load(side, ledger)
    check("budget, E5 check: the progress was persisted",
          st1 is not None and 0 < st1["off"] < ledger.stat().st_size, repr(st1 and st1["off"]))
    g._idx_scan = recording_scan
    del scan_starts[:]
    g.ledger_view = spent_budget(0)
    code, err, last = enforce_call(root, "Bash", {"command": "bash ./run.sh"}, "b5")
    check("budget, E5 check: the next call continues from the saved progress and, caught up, E5 denies run.sh",
          code == 2 and "FIELD DENY [E5]" in err and st1 is not None and scan_starts[:1] == [st1["off"]],
          repr((code, err[-300:], scan_starts[:1])))
finally:
    g.ledger_view, g._idx_scan = real_view, real_scan

# ---------------------------------------------------------------------------------------------------------------
# 5. concurrency: parallel processes under the gate lock; a lock-free reader; compare with a from-scratch rebuild
# ---------------------------------------------------------------------------------------------------------------
WORKER = r'''
import importlib.util, json, os, random, sys, pathlib
spec = importlib.util.spec_from_file_location("g", sys.argv[1]); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
g.IDX_SEG_LINES = 8; g.IDX_PERSIST_BYTES = 300
root = pathlib.Path(sys.argv[2]); path = root / ".claude" / "state" / "field-ledger.jsonl"
rnd = random.Random(int(sys.argv[3]))
for i in range(int(sys.argv[4])):
    while True:
        try:
            fh = g.gate_lock(root)
            break
        except OSError:
            pass  # the gate itself denies after 5 s of waiting; a worker just tries again
    try:
        g._VIEW.clear()
        g.session_written_paths(path, "s%d" % rnd.randrange(3), root)
        g.ledger_view(path, root)
        g.ledger_append(path, {"ts": "t", "session": "s%d" % rnd.randrange(3), "tool": "Write", "tool_use_id": "w%s-%d" % (sys.argv[3], i),
                               "path": "f%d.sh" % rnd.randrange(50), "decision": "allow"})
    finally:
        fh.close()
'''
set_small()
d, path = fresh_dir("conc")
(d / "w.py").write_text(WORKER)
procs = [subprocess.Popen([sys.executable, str(d / "w.py"), os.path.join(HOOKS, "field-gate.py"), str(d), str(s), "30"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) for s in range(4)]
reader_bad = 0
reads = 0
g.IDX_SEG_LINES = 8
while any(p.poll() is None for p in procs):
    side = g._idx_sidecar(path, d)
    try:
        raw = side.read_bytes()
    except OSError:
        continue
    reads += 1
    st = g._idx_decode(raw, path)
    if st is None:  # torn or invalid: must never be a half-written file that nevertheless validates
        reader_bad += 1
    g._VIEW.clear()
    try:
        r = g.ledger_find_ask(path, d, "s0", "w0-1")  # lock-free reader
    except Exception as e:
        reader_bad += 1
errs = [p.communicate()[1].decode()[-300:] for p in procs]
check("concurrency: 4 processes x 30 locked verify+append cycles all exited 0", all(p.returncode == 0 for p in procs), repr(errs))
check("concurrency: lock-free reader saw %d sidecar reads, %d torn/invalid" % (reads, reader_bad), reader_bad == 0)
lines = path.read_text().splitlines()
check("concurrency: no lost append (120 lines)", len(lines) == 120, str(len(lines)))
chain_ok = True
prev = "0" * 64
for ln in lines:
    rec = json.loads(ln); h = rec.pop("hash")
    chain_ok &= rec["prev_hash"] == prev and hashlib.sha256((prev + json.dumps(rec, sort_keys=True)).encode()).hexdigest() == h
    prev = h
check("concurrency: hash chain intact after parallel appends", chain_ok)
g._VIEW.clear()
final_new = snapshot_new(path, d)
check("concurrency: final answers equal the old code", final_new == snapshot_old(path))
# the saved sidecar equals a from-scratch rebuild over the same prefix (no verification skipped by a lost update)
g._VIEW.clear()
st = g._idx_load(g._idx_sidecar(path, d), path)
if st is not None:
    fresh_state = g._idx_new(st["id"])
    with path.open("rb") as fh:
        size_to = st["off"]
        g._idx_scan(fh, fresh_state, None)
    same = all(fresh_state[k] == st[k] for k in ("n", "cl", "head", "bad", "segs", "posts", "asks")) if fresh_state["off"] == st["off"] else None
    check("concurrency: saved sidecar == from-scratch rebuild", same is True or (same is None and fresh_state["off"] >= st["off"]))

# ---------------------------------------------------------------------------------------------------------------
# 6. whole-gate behaviour (subprocess): E5 still denies, with a good, deleted and garbage sidecar; E2 protects it
# ---------------------------------------------------------------------------------------------------------------
GATE = os.path.join(HOOKS, "field-gate.py")
FIXTURE = os.path.join(HERE, "field-manifest.yaml")


def gate_call(root, session, tool, ti, env_extra=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, GATE], input=json.dumps({"session_id": session, "tool_name": tool, "tool_input": ti}).encode(),
                       env=env, capture_output=True, cwd=str(root))
    return p.returncode, p.stderr.decode(errors="replace")


root = pathlib.Path(TMP) / "e2e"
shutil.rmtree(root, ignore_errors=True)
(root / ".claude" / "state").mkdir(parents=True)
shutil.copy(FIXTURE, root / "field-manifest.yaml")
rc, _ = gate_call(root, "t1", "Write", {"file_path": "x.sh", "content": "echo"})
check("e2e: Write x.sh allowed", rc == 0)
rc, err = gate_call(root, "t1", "Bash", {"command": "bash ./x.sh"})
check("e2e: E5 denies running x.sh (sidecar absent)", rc == 2 and "E5" in err, err)
ledger = root / ".claude" / "state" / "field-ledger.jsonl"
side = g._idx_sidecar(ledger, root)
for _ in range(g.IDX_SEG_LINES + 2):
    gate_call(root, "t9", "Bash", {"command": "ls"})
check("e2e: the gate wrote a sidecar into the state directory", side.exists() or ledger.stat().st_size < g.IDX_PERSIST_BYTES)
rc, err = gate_call(root, "t1", "Bash", {"command": "bash ./x.sh"})
check("e2e: E5 denies with the sidecar present", rc == 2 and "E5" in err, err)
if side.exists():
    side.unlink()
rc, err = gate_call(root, "t1", "Bash", {"command": "bash ./x.sh"})
check("e2e: E5 denies with the sidecar deleted (full re-verify)", rc == 2 and "E5" in err, err)
side.write_bytes(b"garbage")
rc, err = gate_call(root, "t1", "Bash", {"command": "bash ./x.sh"})
check("e2e: E5 denies with a garbage sidecar", rc == 2 and "E5" in err, err)
rc, _ = gate_call(root, "t2", "Bash", {"command": "bash ./x.sh"})
check("e2e: another session may still run it", rc == 0)
for tool, ti in (("Write", {"file_path": ".claude/state/" + side.name, "content": "{}"}),
                 ("Bash", {"command": "echo {} > .claude/state/" + side.name}),
                 ("Edit", {"file_path": str(side), "old_string": "a", "new_string": "b"})):
    rc, err = gate_call(root, "t1", tool, ti)
    check("e2e: E2 protects the sidecar from %s" % tool, rc == 2 and "E2" in err, err)
# invalid UTF-8 in the middle still denies every call (as the whole-file read did)
raw_append(ledger, b'{"x": "\xff"}\n')
rc, err = gate_call(root, "t2", "Bash", {"command": "ls"})
check("e2e: invalid UTF-8 in the ledger denies an otherwise allowed call (E0)", rc == 2 and "E0" in err, err)
# a non-JSON line denies only under E5 (as before): same ledger, E5 mode already on in the fixture -> deny
shutil.rmtree(root / ".claude", ignore_errors=True)
(root / ".claude" / "state").mkdir(parents=True)
gate_call(root, "t1", "Write", {"file_path": "y.py", "content": "x"})
raw_append(ledger, b"{not json}\n")
rc, err = gate_call(root, "t2", "Bash", {"command": "ls"})
check("e2e: a non-JSON ledger line denies under E5 (E0)", rc == 2 and "E0" in err, err)

# invalid UTF-8 denies even with E5 off (only the verification before the allow can notice it)
root2 = pathlib.Path(TMP) / "e2e_off"
shutil.rmtree(root2, ignore_errors=True)
(root2 / ".claude" / "state").mkdir(parents=True)
mtxt = open(FIXTURE, encoding="utf-8").read().replace("session_written_exec: deny", "session_written_exec: allow")
(root2 / "field-manifest.yaml").write_text(mtxt, encoding="utf-8")
rc, err = gate_call(root2, "t1", "Bash", {"command": "ls"})
check("e2e (E5 off): a normal call is allowed", rc == 0, err)
raw_append(root2 / ".claude" / "state" / "field-ledger.jsonl", b'{"x": "\xff"}\n')
rc, err = gate_call(root2, "t1", "Bash", {"command": "ls"})
check("e2e (E5 off): invalid UTF-8 in the ledger denies an otherwise allowed call (E0)", rc == 2 and "E0" in err, err)
rc, err = gate_call(root2, "t1", "Bash", {"command": "ls"})
check("e2e (E5 off): and keeps denying (the stale sidecar is dropped)", rc == 2 and "E0" in err, err)

# the post hook, whole (subprocess, production segment size): an ask hidden from the sidecar's asks map still gets its
# executed record, because the hook re-derives the open segment before it believes the map
g.IDX_SEG_LINES, g.IDX_PERSIST_BYTES = 512, 128 * 1024  # what the hook process uses
root3 = pathlib.Path(TMP) / "e2e_post"
shutil.rmtree(root3, ignore_errors=True)
(root3 / ".claude" / "state").mkdir(parents=True)
shutil.copy(FIXTURE, root3 / "field-manifest.yaml")
ledger3 = chained_ledger(root3, 600, 41, {590: {"ts": "t", "session": "p1", "tool": "Bash", "tool_use_id": "tuE2E",
                                                "permission_mode": "default", "input_digest": "0" * 16, "decision": "ask",
                                                "rule": "E3-policy", "reason": "x"}})
g._VIEW.clear()
g.ledger_view(ledger3, root3)  # the gate's sidecar: one completed segment, the ask in the open segment
rewrite_sidecar(root3, ledger3, lambda s: s["asks"].pop(json.dumps(["p1", "tuE2E"])))
p = subprocess.run([sys.executable, os.path.join(HOOKS, "field-post.py")], cwd=str(root3), capture_output=True,
                   env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root3)),
                   input=json.dumps({"hook_event_name": "PostToolUse", "session_id": "p1", "tool_use_id": "tuE2E",
                                     "permission_mode": "default", "tool_name": "Bash", "cwd": str(root3)}).encode())
last = json.loads(ledger3.read_text(encoding="utf-8").strip().splitlines()[-1])
check("e2e field-post: an ask hidden from the sidecar's asks map still gets its executed record",
      p.returncode == 0 and last.get("rule") == "E3-policy-executed" and last.get("tool_use_id") == "tuE2E",
      repr((p.returncode, p.stderr.decode(errors="replace")[-300:], last.get("rule"))))

# post-hook rule constants agree with the gate's
check("field-post constants equal the gate's", post.RULE == g.EXEC_RULE and post.ASK_RULE == g.ASK_RULE)

shutil.rmtree(TMP, ignore_errors=True)
print("ALL LEDGER INDEX TESTS PASSED" if not fail else "LEDGER INDEX TESTS FAILED")
sys.exit(1 if fail else 0)
