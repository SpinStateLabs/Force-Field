"""Unit tests for the gate's path canonicalisation (ADR-0080). Run by run_links.sh; prints PASS/FAIL lines.

  1. _win_clean on a table of inputs (a pure function: runs the same on every platform).
  2. Fail-closed forms: with os.name patched to "nt" and a drive-letter root, UNC, volume-GUID, GLOBALROOT,
     device and drive-relative spellings must raise UnresolvablePath before any file system call.
  3. POSIX byte-identity: with os.name patched to "posix", _root_norm and _abs_norm must return exactly what
     the code before ADR-0080 returned (the reference below is that code, copied verbatim), for a table of
     raw paths and roots, including Windows-looking ones.
"""
import importlib.util
import os
import posixpath
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("field_gate", os.path.join(HERE, "..", "field-gate.py"))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
fail = 0


def check(label, expected, actual):
    global fail
    if expected == actual:
        print("PASS  " + label)
    else:
        fail = 1
        print("FAIL  %s (expected %r, got %r)" % (label, expected, actual))


BS = chr(92)

# ---- 1. _win_clean table ----
CLEAN = [
    ("//?/C:/p/x", "C:/p/x"), ("//./C:/p/x", "C:/p/x"), ("//?/c:", "c:"),
    ("//?/UNC/host/share/x", "//host/share/x"),
    ("//?/Volume{1234}/p", "//?/Volume{1234}/p"), ("//./pipe/x", "//./pipe/x"),
    ("//?/GLOBALROOT/Device/HarddiskVolume3/p", "//?/GLOBALROOT/Device/HarddiskVolume3/p"),
    ("/c/Users/x", "c:/Users/x"),
    ("C:/p/f::$DATA", "C:/p/f"), ("C:/p/f:ads", "C:/p/f"), ("C:/p/f:a:b", "C:/p/f"), ("file.txt::$DATA", "file.txt"),
    ("C:/p/d::$INDEX_ALLOCATION/x", "C:/p/d/x"),
    ("C:/p/f.", "C:/p/f"), ("C:/p/f ", "C:/p/f"), ("C:/p/f. .", "C:/p/f"), ("C:/p/a./b", "C:/p/a/b"),
    ("C:/p/a.b./x", "C:/p/a.b/x"), ("C:/p/a.b.", "C:/p/a.b"),
    ("C:/p/a /b", "C:/p/a /b"),            # Win32 keeps a trailing space on a directory component (tested on Windows 10)
    ("C:/p/. /x", "C:/p/. /x"),
    ("C:/p/..../x", "C:/p/..../x"), ("C:/p/.../x", "C:/p/.../x"), ("C:/p/...", "C:/p/..."), ("C:/p/..a/x", "C:/p/..a/x"),
    ("C:/p/./x/../y", "C:/p/./x/../y"),
    ("http://host:80/a", "http://host:80/a"), ("PATH=/a:/b", "PATH=/a:/b"), ("C:/p/key:val/x", "C:/p/key:val/x"),
    ("C:foo", "C:foo"),
]
for raw, want in CLEAN:
    check("_win_clean(%r)" % raw, want, g._win_clean(raw))

# ---- 2. fail-closed forms (os.name patched; nothing touches the file system) ----
REFUSED = [
    "//?/Volume{01234567-89ab-cdef-0123-456789abcdef}/proj/.claude/state/x",
    "//?/GLOBALROOT/Device/HarddiskVolume3/proj/.claude/state/x", "//./GLOBALROOT/Device/HarddiskVolume3/proj/x",
    "//localhost/C$/proj/.claude/state/x", "//127.0.0.1/C$/proj/x", "//?/UNC/localhost/C$/proj/x",
    BS * 2 + "localhost" + BS + "C$" + BS + "proj" + BS + "x", BS * 2 + "?" + BS + "UNC" + BS + "localhost" + BS + "C$" + BS + "x",
    "//./pipe/x", "//?/Device/HarddiskVolume3/x",
    "C:.claude/state/x", "C:x", "c:.claude" + BS + "state" + BS + "x",
]
real_name = os.name
g._ROOT_CACHE.clear()
g._ROOT_CACHE["C:/proj"] = ("c:/proj", True)
os.name = "nt"
try:
    for raw in REFUSED:
        try:
            g._abs_norm(raw, "C:/proj")
            got = "no error"
        except g.UnresolvablePath:
            got = "UnresolvablePath"
        except Exception as exc:  # anything else is not the designed refusal
            got = type(exc).__name__
        check("refuses %r" % raw, "UnresolvablePath", got)
finally:
    os.name = real_name
g._ROOT_CACHE.clear()

# ---- 3. POSIX byte-identity against the pre-ADR-0080 code ----
_OLD_CACHE = {}


def _norm(value):
    return str(value or "").replace(BS, "/")


def old_root_norm(root):
    key = str(root)
    if key not in _OLD_CACHE:
        win = bool(re.match(r"^[A-Za-z]:", _norm(key))) or os.name == "nt"
        rootn = posixpath.normpath(_norm(key if win else os.path.realpath(key)))
        _OLD_CACHE[key] = (rootn.casefold() if win else rootn, win)
    return _OLD_CACHE[key]


def old_abs_norm(raw, root):
    rootn, win = old_root_norm(root)
    s = _norm(os.path.expanduser(str(raw or ""))).strip()
    if win:
        s = re.sub(r"^/([A-Za-z])/", r"\1:/", s)
    if not (s.startswith("/") or re.match(r"^[A-Za-z]:/", s)):
        s = rootn + "/" + s
    if not win:
        s = _norm(os.path.realpath(s))
    s = posixpath.normpath(s)
    return (s.casefold() if win else s), rootn


RAWS = ["", "x.sh", "./x.sh", "a/../b", ".claude/state/field-ledger.jsonl", "~/x", "/etc/passwd", "/tmp/a b/c",
        "file::$DATA", "file:ads", "file.", "file ", "a./b", "..../x", "//host/share/x", "//?/Volume{1}/x",
        "http://host:80/a", "PATH=/a:/b", "C:/proj/.claude/state/x", "c:/Proj/X", BS + "x" + BS + "y", "/c/Users/x",
        "C:foo", "C:.claude/state/x", "C:" + BS + "p" + BS + "f::$DATA", "x" * 40 + "/../y", "$HOME/x", "a//b///c"]
ROOTS = ["/tmp/proj", "/", "relative/root", "C:/proj", "C:" + BS + "Proj Dir", "/c/proj", "//host/share/p"]
os.name = "posix"
try:
    n = 0
    bad = []
    for root in ROOTS:
        g._ROOT_CACHE.clear()
        _OLD_CACHE.clear()
        for raw in RAWS:
            n += 1
            try:
                want = old_abs_norm(raw, root)
            except Exception as exc:
                want = type(exc).__name__
            try:
                got = g._abs_norm(raw, root)
            except Exception as exc:
                got = type(exc).__name__
            if want != got:
                bad.append((raw, root, want, got))
        for raw in RAWS[:6]:
            n += 1
            if old_root_norm(root) != g._root_norm(root):
                bad.append(("root", root, old_root_norm(root), g._root_norm(root)))
finally:
    os.name = real_name
    g._ROOT_CACHE.clear()
check("POSIX branch identical to the pre-ADR-0080 code (%d comparisons)" % n, [], bad[:5])

sys.exit(1 if fail else 0)
