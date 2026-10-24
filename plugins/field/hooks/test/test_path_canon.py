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
    ("C:/p/state:$I30/new", "C:/p/state/new"), ("C:/p/state:$I30:$INDEX_ALLOCATION/new", "C:/p/state/new"),
    ("secrets:$I30/new", "secrets/new"), ("a:b/c", "a:b/c"),
    ("/??/C:/p/x", "C:/p/x"), ("/??/UNC/host/share/x", "//host/share/x"), ("/??/Volume{1}/x", "/??/Volume{1}/x"),
    ("//localhost//C$/p", "//localhost/C$/p"), ("/??/UNC/localhost/C$/p", "//localhost/C$/p"),
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
    "/??/Volume{1234}/proj/x", "/??/GLOBALROOT/Device/HarddiskVolume3/proj/x", "/??/UNC/localhost/C$/proj/x",
    "//localhost//C$/proj/x", BS * 2 + "localhost" + BS * 2 + "C$" + BS + "proj", "//localhost///C$/proj/x",
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

# ---- 4. the resolution cache and listing (platform independent parts) ----
import tempfile

d = tempfile.mkdtemp(prefix="canon_")
for n in ("File.TXT", "x~1"):
    open(os.path.join(d, n), "w").close()
g._LIST_CACHE.clear()
check("_absent: an entry in a different case is present", False, g._absent(d, "file.txt"))
check("_absent: a missing name is absent", True, g._absent(d, "nope"))
check("_absent: a name with ~ (8.3 alias) is never absent", False, g._absent(d, "NOPE~1"))
check("_absent: a non-ASCII name is never absent", False, g._absent(d, "n\u00f6pe"))
d2 = tempfile.mkdtemp(prefix="canon_big_")
for i in range(5):
    open(os.path.join(d2, "f%d" % i), "w").close()
old_max = g._LIST_MAX
g._LIST_MAX = 3
g._LIST_CACHE.clear()
check("_absent: a directory over _LIST_MAX entries is not listed (never absent)", False, g._absent(d2, "nope"))
g._LIST_MAX = 100
g._LIST_CACHE.clear()
check("_absent: under the cap the listing decides", True, g._absent(d2, "nope"))
g._LIST_MAX = old_max
g._LIST_CACHE.clear()

# Win32 error classes in _win_real: opaque (5, 1920) keep the path, a loop (1921) and anything else raises
real_rp = os.path.realpath


def make_rp(code):
    def fake(path, strict=False):
        if strict:
            e = OSError(code, "x")
            e.winerror = code
            raise e
        return path
    return fake


for code, want in ((5, "kept"), (1920, "kept"), (1921, "raises"), (32, "raises")):
    g._REAL_CACHE.clear()
    g._LIST_CACHE.clear()
    os.path.realpath = make_rp(code)
    try:
        g._win_real("C:" + BS + "no" + BS + "such" + BS + "x")
        got = "kept"
    except OSError:
        got = "raises"
    finally:
        os.path.realpath = real_rp
    check("_win_real: Win32 error %d -> %s" % (code, want), want, got)

if os.name == "nt":
    # with the listing, N absent names under one directory cost a handful of opens, not N: red if _absent is disabled
    calls = [0]

    def counting(path, strict=False):
        calls[0] += 1
        return real_rp(path, strict=strict)
    g._REAL_CACHE.clear()
    g._LIST_CACHE.clear()
    os.path.realpath = counting
    try:
        for i in range(200):
            g._win_real(os.path.join(d, "absent%d" % i))
    finally:
        os.path.realpath = real_rp
    check("_win_real: 200 absent names under one directory use few opens (%d)" % calls[0], True, calls[0] < 10)
    # a differently cased name of an existing entry must reach the OS (a case-sensitive listing would skip it)
    g._REAL_CACHE.clear()
    g._LIST_CACHE.clear()
    check("_win_real: FILE.txt resolves to the real case of File.TXT", "File.TXT",
          os.path.basename(g._win_real(os.path.join(d, "FILE.txt"))))
else:
    print("N/A  _win_real open-count and case tests: Windows only")
g._REAL_CACHE.clear()
g._LIST_CACHE.clear()
import shutil
shutil.rmtree(d, ignore_errors=True)
shutil.rmtree(d2, ignore_errors=True)
# ---- 5. bare words that name a link (PR 14): `echo x >> link` writes through the link ----
bd = tempfile.mkdtemp(prefix="canon_bare_")
os.makedirs(os.path.join(bd, "sub"))
open(os.path.join(bd, "plain"), "w").close()
if os.name != "nt":
    os.symlink(os.path.join(bd, ".claude", "state", "newf"), os.path.join(bd, "dl"))   # dangling
    os.symlink(os.path.join(bd, "sub"), os.path.join(bd, "lv"))                         # live
    for cap, label in ((100000, "cached listing"), (0, "per-word lstat fallback (root over _LIST_MAX)")):
        old_max = g._LIST_MAX
        g._LIST_MAX = cap
        g._LINK_CACHE.clear()
        try:
            check("bare word naming a dangling symlink resolves (%s)" % label, True, g._bare_name_resolves("dl", bd))
            check("bare word naming a live symlink resolves (%s)" % label, True, g._bare_name_resolves("lv", bd))
            check("bare word naming a plain file does not resolve (%s)" % label, False, g._bare_name_resolves("plain", bd))
            check("bare word naming a plain directory does not resolve (%s)" % label, False, g._bare_name_resolves("sub", bd))
            check("bare word naming nothing does not resolve (%s)" % label, False, g._bare_name_resolves("nope", bd))
            check("bare flag, glob and dot words do not resolve (%s)" % label, [False] * 4,
                  [g._bare_name_resolves(w, bd) for w in ("-x", "*", ".", "..")])
        finally:
            g._LIST_MAX = old_max
    g._LINK_CACHE.clear()
    check("_path_forms: a bare link name gains its resolved form", True,
          any(f.endswith("/.claude/state/newf") for f in g._path_forms("dl", bd)))
    check("_path_forms: a plain bare word stays exactly as given", ["plain"], g._path_forms("plain", bd))
    g._LINK_CACHE.clear()
    check("_root_links: the listing holds links only", {"dl", "lv"}, g._root_links(bd))
else:
    print("N/A  bare-word link cases (POSIX branch): run on POSIX; Windows keeps its any-entry rule")
shutil.rmtree(bd, ignore_errors=True)

# ---- 6. Windows: a dangling junction/symlink whose target is spelled differently from the resolved root ----
# CI (windows-latest) hit `manifest rule ^secrets/ via dd/x` allowed: the project lives under C:\Users\RUNNER~1\...
# (8.3 spelling of runneradmin) and `mklink` stored that spelling as the link target. Not reproducible locally (this
# volume has no 8.3 names, Python 3.12.12 and 3.14 resolve the existing prefix of a dangling target), so the
# case is built two ways: a target spelled through an ALIAS junction to the root (a different spelling of the same
# directory on every Windows volume), and, where the volume has 8.3 names, the real short spelling. The
# lenient realpath is also replaced by one that returns the link text verbatim, which is what the failing runner
# is believed to do; with the dangling re-resolve in `_win_real` removed these cases turn red.
if os.name == "nt":
    import ctypes
    import subprocess

    def short_name(p):
        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.kernel32.GetShortPathNameW(p, buf, 1024)
        return buf.value or p

    def lenient_verbatim(path, strict=False):
        if strict:
            return real_rp(path, strict=True)
        try:
            tgt = os.readlink(path)
        except OSError:
            return real_rp(path)
        return tgt[4:] if tgt.startswith(BS * 2 + "?" + BS) else tgt

    wd = tempfile.mkdtemp(prefix="canon_dang_")
    proj = os.path.join(wd, "proj_with_a_long_name")
    os.makedirs(os.path.join(proj, "secrets", "newd"))
    alias = os.path.join(wd, "alias")
    mk = subprocess.run(["cmd", "/c", "mklink", "/J", alias, proj], capture_output=True, text=True)
    check("fixture: alias junction to the project made", 0, mk.returncode)
    spellings = [("alias junction", os.path.join(alias, "secrets", "newd"))]
    sp = short_name(proj)
    if sp.casefold() != proj.casefold():
        spellings.append(("8.3 short name", os.path.join(sp, "secrets", "newd")))
    else:
        print("N/A  8.3 short-name spelling: this volume has no short names (the alias junction stands in)")
    want_dir = real_rp(proj, strict=True)
    for label, tgt in spellings:
        for kind in ("/J", "/D"):
            lnk = os.path.join(proj, "dd" + kind[1])
            mk = subprocess.run(["cmd", "/c", "mklink", kind, lnk, tgt], capture_output=True, text=True)
            if mk.returncode != 0:
                check("fixture: mklink %s (%s) made" % (kind, label), 0, mk.returncode)
                continue
            os.rmdir(os.path.join(proj, "secrets", "newd"))
            want = BS.join([want_dir, "secrets", "newd", "x"]).casefold()
            for mode, rp in (("real realpath", real_rp), ("verbatim link text", lenient_verbatim)):
                g._REAL_CACHE.clear()
                g._LIST_CACHE.clear()
                os.path.realpath = rp
                try:
                    got = g._win_real(lnk + BS + "x").casefold()
                finally:
                    os.path.realpath = real_rp
                check("dangling %s via %s: target converges with the resolved root (%s)" % (kind, label, mode), want, got)
            g._ROOT_CACHE.clear()
            rootn = g._root_norm(proj)[0]
            os.path.realpath = lenient_verbatim
            g._REAL_CACHE.clear()
            g._LIST_CACHE.clear()
            try:
                forms = g._abs_norm("dd" + kind[1] + "/x", proj)[0]
            finally:
                os.path.realpath = real_rp
            check("dangling %s via %s: _abs_norm lands under the root as secrets/newd/x" % (kind, label),
                  True, forms == rootn + "/secrets/newd/x")
            os.rmdir(lnk) if kind == "/J" else os.remove(lnk)
            os.makedirs(os.path.join(proj, "secrets", "newd"))
    # a chain of dangling links and a loop stay bounded
    a, b = os.path.join(proj, "ca"), os.path.join(proj, "cb")
    for lk, tg in ((a, b), (b, a)):
        subprocess.run(["cmd", "/c", "mklink", "/D", lk, tg], capture_output=True)
    g._REAL_CACHE.clear()
    try:
        g._win_real(a + BS + "x")
        got = "returned"
    except OSError:
        got = "raises"
    check("dangling link loop raises OSError (E0 deny), never hangs", "raises", got)
    for lk in (a, b):
        try:
            os.remove(lk)
        except OSError:
            pass
    os.rmdir(alias)
    shutil.rmtree(wd, ignore_errors=True)
    g._REAL_CACHE.clear()
    g._LIST_CACHE.clear()
else:
    print("N/A  dangling-link spelling cases: Windows only")

# ---- 7. PR 15: colon-bound PowerShell parameters, the state-dir rule after a parameter prefix, a:b:c ----
check("ps_tokens: -Path:x yields the value as a token", True, "x/y" in g.ps_tokens("Set-Content -Path:x/y -Value v"))
check("ps_tokens: -LiteralPath:'a b' yields the unquoted value", True, "a b" in g.ps_tokens("Set-Content -LiteralPath:'a b' -Value v"))
check("ps_tokens: http://h:80/a is not split", False, any(tk == "//h:80/a" or tk == "80/a" for tk in g.ps_tokens("curl http://h:80/a")))
sd = tempfile.mkdtemp(prefix="canon_sd_")
rules = g.state_dir_rules(".claude/state/KILL", sd)
for word in (".claude/state/x", "-Path:.claude/state/x", "-LiteralPath:.claude/state/x"):
    check("state_dir_rules match %s" % word, True, any(re.search(rx, word) for rx, _l in rules))
check("state_dir_rules do not match -Path:other/x", False, any(re.search(rx, "-Path:other/x") for rx, _l in rules))
shutil.rmtree(sd, ignore_errors=True)
if os.name == "nt":
    free = [c for c in "qrstuvwxyz" if not os.path.exists(c + ":/")]
    if free:
        w = free[0] + ":b:c"
        try:
            g._abs_norm(w, "C:/proj")
            got = "no error"
        except g.UnresolvablePath:
            got = "E0"
        check("_abs_norm: %s (no such drive) is not E0" % w, "no error", got)
    try:
        g._abs_norm("C:foo", "C:/proj")
        got = "no error"
    except g.UnresolvablePath:
        got = "E0"
    check("_abs_norm: C:foo (drive-relative on an existing drive) is still E0", "E0", got)
else:
    print("N/A  a:b:c drive-relative cases: Windows only")

sys.exit(1 if fail else 0)
