#!/usr/bin/env python3
"""
FIELD Enforcement Gate — Claude Code PreToolUse hook (field plugin v1.2).

Reads field-manifest.yaml (schema field.spinstatelabs.ca/v1) from the project directory
($CLAUDE_PROJECT_DIR, else the hook input's cwd, else the process cwd) and enforces:
  Gated tools: every tool except the read-only UNGATED set (Read, Glob, Grep, LS, NotebookRead,
  TodoWrite). Shell tools are Bash and PowerShell. MCP and other tools get E1, E2, E4 and L.
  E1  kill switch      -> deny ALL gated tool calls while the sentinel file exists.
                          Sentinel = enforcement.kill_switch.endpoint when method is `file`;
                          otherwise the default .claude/state/KILL.
  E2  protected paths  -> deny any gated tool touching governance files: the manifest,
                          .claude/settings*.json, hooks.json, the ledger, the call counter, the
                          project's whole .claude/state/ directory (except the kill sentinel, which
                          /field kill creates, and the skill's field.json), plus every regex in
                          enforcement.protected_paths. Matched case-insensitively against the
                          target path (file tools); the whole command, every unquoted word, and
                          quoted words that are arguments of a mutating command (rm, mv, cp, tee,
                          sed -i, dd of=, ...), redirect targets or command strings a shell, eval or
                          wrapper runs (Bash); the whole text and every token (PowerShell); every
                          string input and its tokens (other tools). Path-like values are also
                          matched in normalised absolute and root-relative form (~, ., .., backslashes,
                          symlinks). Glob/brace words in those mutating positions (rm *.yaml,
                          ls *.yaml | xargs rm, find -name '*.yaml' -delete) are expanded against the
                          governance paths; ls *, cat *.md and grep "x" are not. A Bash rm/rmdir/mv/
                          shred/unlink aimed at the project directory, a parent or .claude/ is denied.
  E3  irreversible ops -> deny shell commands matching enforcement.irreversible_actions.deny_patterns
                          (Python re.search), independent of irreversible_action_policy.
  E4  call budget      -> deny once the session's gated-call count exceeds `max` of the
                          enforcement.rate_limits entry {action: tool_call, period: session}.
  E5  session-written  -> opt-in (enforcement.irreversible_actions.session_written_exec: deny).
      execution           Deny a Bash command that executes a file this same session was allowed
                          to write with a file tool (Write/Edit/MultiEdit/NotebookEdit). PowerShell
                          is checked conservatively: any command naming such a file is denied.
  L   ledger           -> append a sha-256 hash-chained JSONL record for every decision to
                          ledger.store when it is path-like, else .claude/state/field-ledger.jsonl.
                          File-tool records carry `path`: root-relative inside the project,
                          sha256:<hex> outside it (no plaintext absolute paths).

Exit 0 = allow. Exit 2 = deny (stderr line + JSON permissionDecision surfaced to the model). No other exit
once this file runs, short of the process being killed: field-gate.sh retries another interpreter only on
an exit of 1-127 other than 2, which means this file never ran.
Fail-closed: with a manifest present, an unreadable manifest, missing PyYAML, a misconfigured
kill switch, hook input over MAX_INPUT_BYTES, a shell command over MAX_COMMAND_BYTES, a check that
runs past TIME_BUDGET_S (the hooks.json timeout would otherwise kill the hook, which fails open),
or any internal error denies with rule E0. Without a manifest the hook does nothing.
Dependencies: PyYAML (pip install pyyaml). Without it the gate fails closed (E0).
The call counter and the ledger chain are serialised by a per-project lock
(.claude/state/field-gate.lock) held for the life of each hook process.
Limits: regex matching is a tripwire, not a sandbox; Read/Glob/Grep are not gated. E3/E5 only
read shell tools: an MCP tool that runs commands gets E1/E2/E4/L, not E3/E5. E2 and E5 match
command text, not process execution: variables, eval, globs (rm *), brace expansion, programs that
delete without naming the target (git clean, find -delete) and files created by Bash itself
(echo > x.sh, curl -o) are not caught; paths resolve against the project root, not the shell cwd.
"""
import datetime
import fnmatch
import hashlib
import json
import os
import pathlib
import posixpath
import re
import shlex
import sys
import time

MANIFEST_NAME = "field-manifest.yaml"
STATE_DIR = ".claude/state"
DEFAULT_KILL = STATE_DIR + "/KILL"
DEFAULT_LEDGER = STATE_DIR + "/field-ledger.jsonl"
COUNTER_FILE = STATE_DIR + "/field-session-calls.json"
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
# Read-only tools the hook passes straight through (no manifest read, no ledger record).
# Every other tool, including MCP tools, is gated: unknown tools fail toward gating.
UNGATED = {"Read", "Glob", "Grep", "LS", "NotebookRead", "TodoWrite"}
# Built-in governance files (E2). re.search, case-insensitive; see e2_targets for what is matched.
# No leading '.*': under re.search it is a no-op that makes matching quadratic in the text length.
BUILTIN_PROTECTED = [r"field-manifest\.ya?ml$", r"\.claude/settings.*\.json$", r"hooks\.json$"]
# Bash commands that remove or relocate a tree (E2: the project directory, its parents, .claude/).
DESTRUCTIVE = {"rm", "rmdir", "mv", "shred", "unlink"}
MAX_INPUT_BYTES = 4 * 1024 * 1024  # whole hook input
MAX_COMMAND_BYTES = 64 * 1024      # shell command text (E2/E3/E5 scan it)
TIME_BUDGET_S = 5.0                # enforce() wall clock; hooks.json gives the hook 10 s
BUDGET_ACTIONS = {"tool_call"}
BUDGET_PERIODS = {"session", "per-session", "per_session"}
SWE_MODES = {"allow", "deny"}
# Interpreters whose first non-flag argument is a script path (E5).
INTERPRETER_RE = re.compile(
    r"^(?:(?:ba|z|da|k)?sh|source|\.|python(?:\d+(?:\.\d+)?)?|node|deno|bun|ruby|perl|php|"
    r"pwsh(?:\.exe)?|powershell(?:\.exe)?)$")
# Wrapper commands that run another program (E5): their whole command line is checked.
WRAPPERS = {"sudo", "env", "nohup", "time", "exec", "command", "nice", "builtin"}


def project_root(inp):
    for cand in (os.environ.get("CLAUDE_PROJECT_DIR"), inp.get("cwd")):
        if cand and os.path.isdir(cand):
            return pathlib.Path(cand)
    return pathlib.Path.cwd()


def manifest_path(root):
    override = os.environ.get("FIELD_MANIFEST")
    return root / override if override else root / MANIFEST_NAME


def load_manifest(path):
    """None = no manifest (project is not FIELD-governed). {'_unparsed': why} = fail-closed."""
    if not path.exists():
        return None
    try:
        import yaml
    except ImportError:
        return {"_unparsed": "PyYAML missing (pip install pyyaml)"}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # yaml.YAMLError, decode errors
        return {"_unparsed": f"manifest parse error ({exc.__class__.__name__})"}
    if not isinstance(data, dict):
        return {"_unparsed": "manifest is not a mapping"}
    return data


def is_pathlike(value):
    """True for a value the gate may treat as a local file path: no whitespace, not a
    REPLACE-ME placeholder, and a file:// URI, a path containing a separator, a ~ path,
    or a bare *.jsonl name. Prose ('append-only store'), s3:// URIs and service
    descriptions are not path-like."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v or re.search(r"\s", v) or "REPLACE-ME" in v.upper():
        return False
    if "://" in v:
        return v.lower().startswith("file://")
    return "/" in v or "\\" in v or v.startswith("~") or v.endswith(".jsonl")


def resolve_path(value, base):
    v = value.strip()
    if v.lower().startswith("file://"):
        v = v[len("file://"):]
    p = pathlib.Path(os.path.expanduser(v))
    return p if p.is_absolute() else base / p


def kill_switch_path(enf, base):
    """(path, source, error). source: 'manifest' | 'default'. error is set on misconfiguration."""
    ks = enf.get("kill_switch") or {}
    if not isinstance(ks, dict):
        ks = {}
    method = str(ks.get("method") or "").strip().casefold()
    if method == "file":
        endpoint = ks.get("endpoint")
        if is_pathlike(endpoint):
            return resolve_path(endpoint, base), "manifest", None
        return None, None, "kill_switch.method is 'file' but endpoint is not a file path"
    return base / DEFAULT_KILL, "default", None


def resolve_store(manifest, base):
    """(ledger path, source). source is 'manifest' when ledger.store is path-like, else 'default'."""
    ledger = (manifest or {}).get("ledger") or {}
    store = ledger.get("store") if isinstance(ledger, dict) else None
    if is_pathlike(store):
        return resolve_path(store, base), "manifest"
    return base / DEFAULT_LEDGER, "default"


def tool_call_budget(enf):
    """`max` of the first rate_limits entry with action tool_call and a session period, else None."""
    for entry in enf.get("rate_limits") or []:
        if not isinstance(entry, dict):
            continue
        action = str(entry.get("action") or "").strip().casefold()
        period = str(entry.get("period") or "").strip().casefold()
        if action in BUDGET_ACTIONS and period in BUDGET_PERIODS:
            try:
                return int(entry.get("max"))
            except (TypeError, ValueError):
                return None
    return None


_ROOT_CACHE = {}


def _root_norm(root):
    """(normalised project root, win). Windows is detected from a drive letter or os.name; there
    the root is case-folded, on POSIX symlinks are resolved. Cached: called once per token."""
    key = str(root)
    if key not in _ROOT_CACHE:
        win = bool(re.match(r"^[A-Za-z]:", _norm(key))) or os.name == "nt"
        rootn = posixpath.normpath(_norm(key if win else os.path.realpath(key)))
        _ROOT_CACHE[key] = (rootn.casefold() if win else rootn, win)
    return _ROOT_CACHE[key]


def _abs_norm(raw, root):
    """(normalised absolute POSIX-style path, normalised root). ~ expanded, backslashes to '/',
    relative paths joined to the root, Git Bash /c/ mapped to C:/ and case folded on Windows,
    symlinks and '..' resolved on POSIX (realpath), then normpath."""
    rootn, win = _root_norm(root)
    s = _norm(os.path.expanduser(str(raw or ""))).strip()
    if win:
        s = re.sub(r"^/([A-Za-z])/", r"\1:/", s)
    if not (s.startswith("/") or re.match(r"^[A-Za-z]:/", s)):
        s = rootn + "/" + s
    if not win:
        s = _norm(os.path.realpath(s))
    s = posixpath.normpath(s)
    return (s.casefold() if win else s), rootn


def path_key(raw, root):
    """Ledger key for a file path. Root-relative POSIX path when it is inside the project root;
    otherwise 'sha256:<hex>' of the normalised absolute path, so the ledger never holds plaintext
    paths from outside the project (usernames, client folders). None for an empty value."""
    if not _norm(os.path.expanduser(str(raw or ""))).strip():
        return None
    s, rootn = _abs_norm(raw, root)
    if rootn in ("/", "") or re.match(r"^[a-z]:$", rootn.casefold()):
        return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()
    if s.startswith(rootn + "/"):
        return s[len(rootn) + 1:]
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def _path_forms(raw, root, force=False):
    """Strings E2 matches for one value: as given (backslashes to '/') and, when it looks like a
    path (contains '/', starts with '~', or force), its normalised absolute form and, inside the
    project, its root-relative form. So ./.claude/state/../state/x, ~/x, a symlink and C:\\x are
    matched by the same patterns as the plain name."""
    s = _norm(raw).strip()
    forms = [s]
    if s and (force or "/" in s or s.startswith("~")):
        a, rootn = _abs_norm(s, root)
        forms.append(a)
        if a.startswith(rootn + "/"):
            forms.append(a[len(rootn) + 1:])
    return forms


def session_written_paths(ledger_path, session):
    """Path keys this session was allowed to write via a file tool. Raises ValueError on an
    unreadable record, so the caller fails closed."""
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


READ_ONLY = {"cat", "ls", "head", "tail", "less", "more", "wc", "grep", "rg", "diff", "stat", "file",
             "git", "sha256sum", "md5sum", "chmod", "echo", "printf", "test", "["}
SHELL_KEYWORDS = {"if", "then", "elif", "else", "do", "while", "until", "!", "{", "}", "(", ")", "time", "coproc"}
SEPARATORS = {";", "&", "&&", "|", "||", "|&", "\n", ";;"}
REDIRECT = re.compile(r"^\d*(?:[<>]+&?|&>>?)$")


QUOTE_SPAN = re.compile(r"""\\.|'[^']*'|"(?:\\.|[^"\\])*\"""")
MARK = "\ue000"  # private-use char placed before each opening quote so words remember they were quoted


def _shell_words(cmd):
    """[(word, quoted)] for a Bash command: shlex words with quotes and escapes resolved, the
    punctuation ; & | ( ) < > as words of their own, $( ` <( >( and newlines as separators.
    `quoted` marks a word that was wholly or partly quoted. ValueError propagates (unbalanced quote)."""
    cmd = re.sub(r"\$\(|`|<\(|>\(", " ; ", (cmd or "").replace(MARK, "")).replace("\n", " ; ")
    cmd = QUOTE_SPAN.sub(lambda m: m.group(0) if m.group(0)[0] == "\\" else MARK + m.group(0), cmd)
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    lex.commenters = ""
    return [(t.replace(MARK, ""), MARK in t) for t in lex]


def _shell_tokens(cmd):
    return [w for w, _q in _shell_words(cmd)]  # ValueError propagates: caller fails closed


def _split(words):
    """(word, quoted) list -> pipelines (split at ; & && || ;; newline) of stages (split at | |&)."""
    pipelines, pipe, stage = [], [], []
    for w, q in words + [(";", False)]:
        if w not in SEPARATORS:
            stage.append((w, q))
            continue
        if stage:
            pipe.append(stage)
        stage = []
        if w not in ("|", "|&"):
            if pipe:
                pipelines.append(pipe)
            pipe = []
    return pipelines


def _segments(cmd):
    """Shell words grouped into simple commands (split at ; & && | || and newlines)."""
    return [[w for w, _q in st] for pipe in _split(_shell_words(cmd)) for st in pipe]


def _command_index(seg):
    """Index of the command word in a simple command, skipping shell keywords, redirections and
    VAR=value assignments; None when nothing is left."""
    i = 0
    while i < len(seg) and (seg[i] in SHELL_KEYWORDS or REDIRECT.match(seg[i])
                            or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[i])):
        i += 2 if REDIRECT.match(seg[i]) else 1
    return i if i < len(seg) else None


ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=(.*)$", re.S)
# Options that hand a program or a config value to the tool they belong to.
EXEC_VALUE_FLAGS = {"-c", "--pre", "--hostname-bin", "--config-env", "--exec-path", "--upload-pack", "--receive-pack"}


def _value_forms(value):
    """The value, and the pieces of it a path can hide in (KEY=!path, a:b lists)."""
    value = value.lstrip("!")
    return [value] + [p for p in re.split(r"[=!:;,|\s]+", value) if p]


def indirect_exec_tokens(seg):
    """Words in one simple command that a tool can be told to run: the value of a VAR=value
    assignment, an attached option value (--opt=value, -cKEY=value), the argument of an option in
    EXEC_VALUE_FLAGS, and a !-prefixed word. A read-only tool's own arguments are not checked, but
    what it is configured to execute is."""
    out, prev = [], ""
    for t in seg:
        m = ASSIGN_RE.match(t)
        if m:
            out.extend(_value_forms(m.group(1)))
        elif t.startswith("--") and "=" in t:
            out.extend(_value_forms(t.split("=", 1)[1]))
        elif t.startswith("-c") and len(t) > 2:
            out.extend(_value_forms(t[2:]))
        elif prev in EXEC_VALUE_FLAGS:
            out.extend(_value_forms(t))
        if t.startswith("!"):
            out.extend(_value_forms(t))
        prev = t
    return out


def exec_suspect_tokens(cmd, depth=0, root=None, written=None):
    """Tokens that may be executed. Fail-closed: every token of a segment whose command word is
    not a known read-only tool, plus every token of a command that pipes/redirects into an interpreter.
    A path-qualified command word (./git, tools/cat) that names a file this session wrote is not a
    read-only tool, whatever its basename: READ_ONLY describes the tool, not a path that borrows its name."""
    segs = _segments(cmd)
    out = []
    interp_anywhere = False
    for seg in segs:
        out.extend(indirect_exec_tokens(seg))
        i = _command_index(seg)
        if i is None:
            continue
        word = posixpath.basename(_norm(seg[i]))
        if INTERPRETER_RE.match(re.sub(r"(?i)\.exe$", "", word).lower()) or word in WRAPPERS:
            interp_anywhere = True
        # A command word containing a separator is a path, not a PATH lookup: if it resolves to a
        # file this session wrote, the read-only exemption does not apply to it.
        runs_written = (written is not None and "/" in _norm(seg[i])
                        and path_key(seg[i], root) in written)
        if runs_written or word not in READ_ONLY:
            out.extend(seg)
            if depth < 3:
                for j, t in enumerate(seg[:-1]):
                    if t in ("-c", "-Command"):
                        out.extend(exec_suspect_tokens(seg[j + 1], depth + 1, root, written))
    if interp_anywhere:
        out.extend(t for s in segs for t in s)
    return out


def ledger_append(ledger_path, record):
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


def gate_lock(root):
    """Exclusive lock held for the rest of this hook process, so parallel tool calls do not race
    on the call counter or the ledger chain. Released by the OS when the process exits."""
    path = root / STATE_DIR / "field-gate.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+")
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        for _ in range(100):  # LK_LOCK itself retries ~10 times at 1 s; keep trying within the hook timeout
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                import time
                time.sleep(0.05)
        else:
            raise OSError("gate lock busy")
    else:
        import fcntl
        fcntl.flock(fh, fcntl.LOCK_EX)
    return fh


def emit_deny(rule, reason):
    # Exit 2 must survive a closed stdout or stderr (Claude Code gone, the hook timed out): any other exit is
    # non-blocking, and field-gate.sh would read it as "this Python never ran the gate" and retry.
    try:
        sys.stderr.write(f"FIELD DENY [{rule}]: {reason}\n")
        sys.stderr.flush()
    except Exception:
        pass
    try:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "permissionDecision": "deny", "permissionDecisionReason": f"[{rule}] {reason}"}}), flush=True)
    except Exception:
        try:  # point fd 1 at devnull so the exit-time flush of the unsent buffer cannot fail (exit 120)
            os.dup2(os.open(os.devnull, os.O_WRONLY), 1)
        except OSError:
            pass
    sys.exit(2)


def deny(ledger_path, event, rule, reason):
    try:
        ledger_append(ledger_path, {**event, "decision": "deny", "rule": rule, "reason": reason})
    except Exception as exc:  # the deny must still reach Claude Code
        sys.stderr.write(f"FIELD ledger write failed: {exc!r}\n")
    emit_deny(rule, reason)


def _norm(value):
    return str(value or "").replace("\\", "/")


def string_leaves(value):
    """Every string inside a tool_input (dict/list values, recursively)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from string_leaves(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from string_leaves(v)


PS_TOKEN = re.compile(r"'([^']*)'|\"([^\"]*)\"|([^\s;|&(){}<>,'\"`=]+)")


def ps_tokens(cmd):
    """PowerShell text -> candidate path tokens. Deliberately crude: quoted strings whole, else
    runs of non-separator characters. E5 checks every one (no read-only allowlist)."""
    return [a or b or c for a, b, c in PS_TOKEN.findall(cmd or "")]


PS_FOLD = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
                         "\u201c": '"', "\u201d": '"', "\u201e": '"',
                         "\u2013": "-", "\u2014": "-", "\u2015": "-"})


def shell_command(tool, ti):
    """Command text of a shell tool. PowerShell: every string input, whatever its key."""
    if tool == "Bash":
        return str(ti.get("command", "") or "")
    # PowerShell: fold smart quotes/dashes to ASCII and drop escape backticks (`x -> x).
    return re.sub(r"`(.)", r"\1", " ".join(string_leaves(ti)).translate(PS_FOLD))


def text_tokens(text, depth=0):
    """ps_tokens plus, for every quoted string among them, the tokens a nested shell would see in
    it (sh -c 'rm x; true', -Command "..."), three levels deep. Unquoted tokens hold no separator,
    so only quoted strings recurse."""
    toks = ps_tokens(text)
    if depth < 3:
        for t in list(toks):
            if re.search(r"[\s;|&(){}<>,=]", t):
                toks += text_tokens(t, depth + 1)
    return toks


# Bash commands whose arguments E2 checks even when quoted or globbed, and which arguments:
# all non-flag arguments; the destination (last) only, sources too when the destination is a
# governance path; of= values; all arguments when an in-place flag (-i, -pi, --in-place) is present.
MUTATING = {"rm": "all", "rmdir": "all", "unlink": "all", "shred": "all", "mv": "all", "ln": "all",
            "tee": "all", "truncate": "all", "chmod": "all", "chown": "all", "chattr": "all",
            "cp": "dest", "install": "dest", "dd": "of", "sed": "inplace", "perl": "inplace"}
# Words that run another command given as their arguments (sudo -u root rm x, xargs rm, timeout 5 rm x).
E2_WRAPPERS = WRAPPERS | {"timeout", "xargs", "su", "doas", "ionice"}
# Shells that run a command string after -c (bash -c, bash -lc, su -c, pwsh -Command).
SHELL_C = re.compile(r"^(?:(?:ba|z|da|k)?sh|su|pwsh|powershell)$")
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
GLOB_CHARS = re.compile(r"[*?\[{]")


def _base(word):
    return re.sub(r"(?i)\.exe$", "", posixpath.basename(_norm(word))).lower()


def _xargs_mutating(stage):
    """True for an `xargs ... rm`-style stage: what the pipeline feeds it gets deleted or rewritten."""
    i = _command_index([w for w, _q in stage])
    return (i is not None and _base(stage[i][0]) == "xargs"
            and any(_base(w) in MUTATING or SHELL_C.match(_base(w)) or _base(w) == "eval" for w, _q in stage[i + 1:]))


def _interpreter_sink(stage):
    """True for a stage that runs what the pipeline feeds it (`... | sh`, `... | bash -s`, `... | python3`)."""
    i = _command_index([w for w, _q in stage])
    return i is not None and bool(SHELL_C.match(_base(stage[i][0])) or INTERPRETER_RE.match(_base(stage[i][0])))


def _stage_marks(stage, i, hits):
    """For one simple command: {argument index: quoted-glob-counts} of the words E2 must check even
    when quoted or globbed, and the nested command strings (sh -c '...', eval ..., su -c) to analyse
    as commands. Scans past wrappers (sudo -u root rm x) to the real command."""
    marked, nested = {}, []
    span = range(i, len(stage)) if _base(stage[i][0]) in E2_WRAPPERS else [i]
    for k in span:
        b = _base(stage[k][0])
        rest = list(range(k + 1, len(stage)))
        args = [j for j in rest if not stage[j][0].startswith("-") or stage[j][0] == "-"]
        if b in MUTATING:
            rule = MUTATING[b]
            if rule == "all":
                sel = args
            elif rule == "dest":
                sel = args[-1:]
                if sel and hits(stage[sel[0]][0]):
                    sel = args
            elif rule == "of":
                sel = [j for j in rest if stage[j][0].startswith("of=")]
            else:  # inplace
                sel = args if any(re.match(r"^-[a-zA-Z]*i|^--in-place", stage[j][0]) for j in rest) else []
            marked.update((j, False) for j in sel)
            break
        if SHELL_C.match(b):
            nested += [stage[j + 1][0] for j in rest[:-1]
                       if re.match(r"^-[a-zA-Z]*c$", stage[j][0]) or stage[j][0] == "-Command"]
            break
        if b == "eval":
            nested.append(" ".join(stage[j][0] for j in rest))
            break
        if b == "find":  # find matches its own patterns: a quoted '*.yaml' counts as a glob here
            fw = [stage[j][0] for j in rest]
            if "-delete" in fw or any(w in FIND_EXEC and n + 1 < len(fw) and _base(fw[n + 1]) in MUTATING
                                      for n, w in enumerate(fw)):
                marked.update((j, True) for j in rest)
            break
    return marked, nested


def bash_e2_words(cmd, root, hits, depth=0):
    """(plain, globs) for a Bash command. plain: every unquoted word (a governance file named bare
    anywhere in the command is denied, as 1.2.2 did for the command's last word), plus quoted words
    that are arguments of a mutating command (MUTATING), redirect targets, fed to `xargs rm`, or part
    of a command string a shell, eval or wrapper runs (re-analysed, three levels). globs: words in
    those positions the shell (or find/xargs) would expand; `ls *` and `grep "x" f` yield none.
    `hits(word)` says whether a word names a governance path (cp/install sources count only when
    the destination does). When shlex cannot parse the text, crude tokens, no globs."""
    try:
        words = _shell_words(cmd)
    except ValueError:
        return ps_tokens(cmd), []
    plain, globs = [], []
    for pipe in _split(words):
        xargs_mut = any(_xargs_mutating(st) for st in pipe)
        sink = any(_interpreter_sink(st) for st in pipe)  # echo "rm x" | sh: upstream quoted text is a command
        for stage in pipe:
            plain += [w for w, q in stage if not q]
            marked = {j + 1: False for j, (w, _q) in enumerate(stage[:-1]) if REDIRECT.match(w)}
            i = _command_index([w for w, _q in stage])
            if i is not None:
                m, nested = _stage_marks(stage, i, hits)
                marked.update(m)
                if sink and not _interpreter_sink(stage):
                    nested += [w for w, q in stage if q]
                for n in nested if depth < 3 else []:
                    p, g = bash_e2_words(n, root, hits, depth + 1)
                    plain += p
                    globs += g
                if xargs_mut:
                    marked.update((j, True) for j in range(len(stage))
                                  if j != i and not stage[j][0].startswith("-") and j not in marked)
            for j, quoted_glob_ok in marked.items():
                w, q = stage[j]
                w = re.sub(r"^of=", "", w)
                plain.append(w)
                if GLOB_CHARS.search(w) and (not q or quoted_glob_ok):
                    globs.append(w)
    return plain, globs


def e2_targets(tool, ti, root, hits):
    """(targets, globs). targets: the strings E2's regexes run on: the target path (file tools); the
    whole command plus the words bash_e2_words selects (Bash); the whole text and every token,
    quoted strings re-tokenised (PowerShell, which has no parser); every string input and its tokens
    (other tools). Each path-like one is matched in normalised absolute and root-relative form as
    well (_path_forms). globs: shell words to expand against the governance paths (shell tools only;
    PowerShell when a mutating cmdlet or a redirect is present)."""
    if tool in FILE_TOOLS:
        return _path_forms(ti.get("file_path") or ti.get("notebook_path") or "", root, force=True), []
    out, toks, globs = [], [], []
    if tool == "Bash":
        cmd = shell_command(tool, ti)
        out.append(_norm(cmd))
        toks, globs = bash_e2_words(cmd, root, hits)
    elif tool == "PowerShell":
        cmd = shell_command(tool, ti)
        out.append(_norm(cmd))
        toks = text_tokens(cmd)
        if ">" in cmd or any(t.casefold() in PS_MUTATING for t in toks):
            globs = [t for t in ps_tokens(cmd) if GLOB_CHARS.search(t) and not re.search(r"\s", t)]
    else:  # MCP and other tools
        for v in string_leaves(ti):
            out.append(_norm(v).strip())
            toks += text_tokens(v)
    for t in dict.fromkeys(toks):  # de-duplicated, order kept
        out += _path_forms(t, root)
    return out, globs


PS_MUTATING = set(MUTATING) | {"remove-item", "del", "erase", "rd", "ri", "move-item", "mi", "move",
                               "copy-item", "copy", "cpi", "rename-item", "ren", "rni", "set-content", "sc",
                               "add-content", "ac", "out-file", "clear-content", "clc", "new-item", "ni",
                               "tee-object", "set-itemproperty", "robocopy", "xcopy", "cmd"}


def state_dir_rules(flag, root):
    """(regex, label) pairs protecting the project's .claude/state/ directory and everything in it,
    in absolute and root-relative form, except the kill sentinel (/field kill creates it; E1 stops
    its removal) and the skill's field.json state file. ~/.claude/state of another root is not it."""
    abs_state, _rootn = _abs_norm(STATE_DIR, root)
    exempt = [r"field\.json"]
    k, _ = _abs_norm(flag, root)
    if k.startswith(abs_state + "/"):
        exempt.append(re.escape(k[len(abs_state) + 1:]))
    tail = r"(?:/(?!(?:%s)$)|$)" % "|".join(exempt)
    return [("^" + re.escape(abs_state) + tail, "the state directory"),
            ("^" + re.escape(STATE_DIR) + tail, "the state directory")]


def _lean(pat):
    """Drop a leading '.*': a no-op under re.search that makes a miss quadratic in the text length."""
    return pat[2:] if pat.startswith(".*") and pat[2:3] not in ("?", "*", "+", "{") else pat


def _brace_expand(tok, limit=1024):
    """Shell {a,b} expansion, nested, capped at `limit` results."""
    m = re.search(r"\{([^{}]*,[^{}]*)\}", tok)
    if not m:
        return [tok]
    out = []
    for alt in m.group(1).split(","):
        out += _brace_expand(tok[:m.start()] + alt + tok[m.end():], limit)
    return out[:limit]


def glob_hit(tok, names, root):
    """Label of the first concrete governance path a shell glob token would expand to. Component-
    wise fnmatch of the normalised absolute forms: '*' does not cross '/' and, like the shell, does
    not match a leading dot. Only for shell words: a '*' inside MCP file content is not a glob."""
    for pat in _brace_expand(tok):
        p, _ = _abs_norm(pat, root)
        pc = p.casefold().split("/")
        for name, label in names:
            nc = name.casefold().split("/")
            if len(nc) == len(pc) and all(fnmatch.fnmatchcase(a, b) and not (a.startswith(".") and b[:1] in "*?")
                                           for a, b in zip(nc, pc)):
                return label
    return None


def _find_wipes(seg, i):
    """True for `find <dirs> ... -delete` or `-exec rm` with no name/path filter: every file under
    the start directories goes. With a filter, the glob check covers a governance name."""
    rest = seg[i + 1:]
    deletes = "-delete" in rest or any(w in FIND_EXEC and n + 1 < len(rest) and _base(rest[n + 1]) in MUTATING
                                       for n, w in enumerate(rest))
    return deletes and not any(w in ("-name", "-iname", "-path", "-ipath", "-regex", "-iregex") for w in rest)


def dir_wipe_target(cmd, root):
    """Label of an argument of a Bash rm/rmdir/mv/shred/unlink (or an unfiltered find -delete) that
    is the project directory, one of its parents or the .claude/ directory (where the state and
    settings live), else None."""
    rootn, _win = _root_norm(root)
    try:
        segs = _segments(cmd)
    except ValueError:
        return None
    for seg in segs:
        i = _command_index(seg)
        if i is None:
            continue
        b = _base(seg[i])
        if b not in DESTRUCTIVE and not (b == "find" and _find_wipes(seg, i)):
            continue
        for t in seg[i + 1:]:
            if t.startswith("-"):
                if b == "find":
                    break  # find's options start here; the start directories came before
                continue
            a, _ = _abs_norm(t, root)
            if a == rootn + "/.claude":
                return "the .claude directory"
            if a == rootn or rootn.startswith(a.rstrip("/") + "/"):
                return "the project directory"
    return None


def shell_pattern_hit(tool, cmd, globs, names, root):
    """E2 reason when one of the selected glob/brace words expands to a governance path, or (Bash)
    when rm/rmdir/mv/shred/unlink is aimed at the project directory, a parent or .claude/; else None."""
    for w in dict.fromkeys(globs):
        hit = glob_hit(w, names, root)
        if hit:
            return f"shell glob/brace pattern expands to {hit}"
    hit = dir_wipe_target(cmd, root) if tool == "Bash" else None
    return f"destructive command aimed at {hit}" if hit else None


_T0 = 0.0


def _overdue():
    return time.monotonic() - _T0 > TIME_BUDGET_S


def enforce(inp, manifest, root, ledger_path, store_source):
    global _T0
    _T0 = time.monotonic()  # after the gate lock: time waiting for parallel calls is not ours
    tool = inp.get("tool_name", "")
    ti = inp.get("tool_input", {}) or {}
    session = inp.get("session_id", "unknown")
    event = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "session": session, "tool": tool,
             "tool_use_id": inp.get("tool_use_id"),
             "permission_mode": inp.get("permission_mode"),
             "input_digest": hashlib.sha256(json.dumps(ti, sort_keys=True).encode()).hexdigest()[:16],
             "store_source": store_source}
    if tool in FILE_TOOLS:
        event["path"] = path_key(ti.get("file_path") or ti.get("notebook_path") or "", root)

    if manifest.get("_unparsed"):
        deny(ledger_path, event, "E0", f"manifest unreadable ({manifest['_unparsed']}); fail-closed")
    enf = manifest.get("enforcement") or {}
    if not isinstance(enf, dict):
        deny(ledger_path, event, "E0", "enforcement section is not a mapping; fail-closed")

    # E1 kill switch: sentinel file (endpoint when method is `file`, else the default).
    flag, _flag_source, err = kill_switch_path(enf, root)
    if err:
        deny(ledger_path, event, "E0", f"{err}; fail-closed")
    if flag.exists():
        # path_key, not the raw path: an absolute sentinel path would put a username in the ledger.
        deny(ledger_path, event, "E1", f"kill switch tripped ({path_key(flag, root)}); all tool calls halted")

    # Size cap: E2/E3/E5 scan the command text and a scan that outlives the hook timeout fails open.
    if tool in SHELL_TOOLS and len(shell_command(tool, ti).encode("utf-8")) > MAX_COMMAND_BYTES:
        deny(ledger_path, event, "E0", f"shell command exceeds {MAX_COMMAND_BYTES} bytes; fail-closed")

    # E2 protected governance files: built-ins + state directory + resolved manifest/ledger/counter
    # + manifest extras, all case-insensitive (a case-insensitive file system can exist anywhere).
    counter = root / COUNTER_FILE
    # (regex, label). Labels for resolved paths avoid echoing absolute paths in the deny reason.
    protected = [(p, p) for p in BUILTIN_PROTECTED] + state_dir_rules(flag, root)
    for p, label in ((manifest_path(root), "the manifest"), (ledger_path, "the ledger"),
                     (counter, "the call counter")):
        a, rootn = _abs_norm(p, root)
        protected.append((re.escape(a) + "$", label))
        if a.startswith(rootn + "/"):
            protected.append((re.escape(a[len(rootn) + 1:]) + "$", label))
    protected += [(str(p), str(p)) for p in (enf.get("protected_paths") or [])]
    try:
        rules = [(re.compile(_lean(pat), re.IGNORECASE), label) for pat, label in protected]
    except re.error:
        deny(ledger_path, event, "E0", "invalid protected_paths pattern; fail-closed")
    # Concrete governance paths, for glob words the shell would expand after the gate has seen
    # the text (rm *.yaml, rm {field-manifest,}.yaml): matched against these, not the regexes.
    names = [(_abs_norm(p, root)[0], label) for p, label in (
        (manifest_path(root), "the manifest"), (ledger_path, "the ledger"), (counter, "the call counter"),
        (STATE_DIR, "the state directory"), (".claude/settings.json", ".claude/settings.json"),
        (".claude/settings.local.json", ".claude/settings.local.json"))]

    def hits(word):  # does one shell word name a governance path (cp/install destination test)
        return (any(rx.search(f) for f in _path_forms(word, root) for rx, _l in rules)
                or (GLOB_CHARS.search(word) and glob_hit(word, names, root) is not None))

    targets, globs = e2_targets(tool, ti, root, hits)
    for target in targets:
        if _overdue():
            deny(ledger_path, event, "E0", f"E2 check exceeded {TIME_BUDGET_S:g} s; fail-closed")
        for rx, label in rules:
            if rx.search(target):
                deny(ledger_path, event, "E2", f"write/touch of protected governance path matched '{label}'")
    if tool in SHELL_TOOLS:
        reason = shell_pattern_hit(tool, shell_command(tool, ti), globs, names, root)
        if reason:
            deny(ledger_path, event, "E2", reason)

    # E3 irreversible action patterns (shell command text).
    if tool in SHELL_TOOLS:
        cmd = shell_command(tool, ti)
        pats = (enf.get("irreversible_actions") or {}).get("deny_patterns") or []
        for pat in pats:
            if _overdue():
                deny(ledger_path, event, "E0", f"E3 check exceeded {TIME_BUDGET_S:g} s; fail-closed")
            if re.search(str(pat), cmd, re.IGNORECASE if tool == "PowerShell" else 0):
                deny(ledger_path, event, "E3", f"command matched irreversible-action pattern '{pat}'")

    # E5 session-written execution (opt-in): deny running a file this session wrote via a file tool.
    if tool in SHELL_TOOLS:
        ia = enf.get("irreversible_actions") or {}
        if not isinstance(ia, dict):
            deny(ledger_path, event, "E0", "irreversible_actions is not a mapping; fail-closed")
        mode = str(ia.get("session_written_exec") or "allow").strip().casefold()
        if mode not in SWE_MODES:
            deny(ledger_path, event, "E0", "session_written_exec must be allow or deny; fail-closed")
        if mode == "deny":
            allow = ia.get("session_written_exec_allow") or []
            if not isinstance(allow, list):
                deny(ledger_path, event, "E0", "session_written_exec_allow must be a list; fail-closed")
            try:
                flags = re.IGNORECASE if (os.name == "nt" or re.match(r"^[A-Za-z]:", _norm(str(root)))) else 0
                exempt = [re.compile(str(p), flags) for p in allow]
            except re.error:
                deny(ledger_path, event, "E0", "invalid session_written_exec_allow pattern; fail-closed")
            try:
                written = session_written_paths(ledger_path, session)
            except (OSError, ValueError) as exc:
                deny(ledger_path, event, "E0", f"ledger unreadable for E5 ({exc.__class__.__name__}); fail-closed")
            try:
                if tool == "Bash":
                    toks = exec_suspect_tokens(shell_command(tool, ti), root=root, written=written)
                else:  # PowerShell: no parser, so every token counts (over-blocks reads; safe side)
                    toks = ps_tokens(shell_command(tool, ti))
                    # $PWD/x.sh, -FilePath:x.sh: also try the text after the last ':' or '$var/'.
                    toks += [re.sub(r"^.*(?::|\$[^/]*/)", "", _norm(t)) for t in toks]
            except ValueError:
                deny(ledger_path, event, "E0", "command could not be tokenised for E5; fail-closed")
            for tok in dict.fromkeys(toks):  # de-duplicated: path_key resolves the file system
                if _overdue():
                    deny(ledger_path, event, "E0", f"E5 check exceeded {TIME_BUDGET_S:g} s; fail-closed")
                key = path_key(tok, root)
                if key in written and not (not key.startswith("sha256:")
                                           and any(rx.search(key) for rx in exempt)):
                    # Name the ledger key, not the raw token: an absolute token would put a
                    # plaintext path (username, client folder) into the ledger.
                    deny(ledger_path, event, "E5",
                         f"command executes '{key}', a file this session wrote")

    # E4 tool-call budget (runtime proxy for spend_cap): counts gated calls per session.
    budget = tool_call_budget(enf)
    if budget:
        counts = json.loads(counter.read_text(encoding="utf-8")) if counter.exists() else {}
        n = counts.get(session, 0) + 1
        counts[session] = n
        counter.parent.mkdir(parents=True, exist_ok=True)
        tmp = counter.with_name(counter.name + ".tmp")
        tmp.write_text(json.dumps(counts), encoding="utf-8")
        os.replace(tmp, counter)  # atomic: a parallel reader never sees a truncated file
        if n > budget:
            deny(ledger_path, event, "E4", f"session tool-call budget {budget} exceeded (call #{n})")

    ledger_append(ledger_path, {**event, "decision": "allow"})
    sys.exit(0)


def main():
    bad_input = oversize = False
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            inp, oversize = {}, True  # not parsed: the root comes from CLAUDE_PROJECT_DIR or cwd
        else:
            inp = json.loads(raw)
        if not isinstance(inp, dict):
            inp, bad_input = {}, True
    except Exception:
        inp, bad_input = {}, True
    if not bad_input and not isinstance(inp.get("tool_name", ""), str):
        bad_input = True
    if not (bad_input or oversize) and inp.get("tool_name") in UNGATED:
        sys.exit(0)  # read-only tool: not gated
    root = project_root(inp)
    manifest = load_manifest(manifest_path(root))
    if manifest is None:
        sys.exit(0)  # no manifest: not a FIELD-governed project, do nothing
    if oversize:
        emit_deny("E0", f"hook input exceeds {MAX_INPUT_BYTES} bytes; fail-closed")
    if bad_input:
        emit_deny("E0", "hook input is not a JSON object; fail-closed")
    ledger_path, store_source = resolve_store(manifest, root)
    try:
        _lock = gate_lock(root)  # noqa: F841  (held until exit)
        enforce(inp, manifest, root, ledger_path, store_source)
    except SystemExit:
        raise
    except OSError as exc:  # strerror only: str(exc) carries the file path
        emit_deny("E0", f"gate internal error ({exc.__class__.__name__}: {exc.strerror or 'I/O error'}); fail-closed")
    except Exception as exc:
        emit_deny("E0", f"gate internal error ({exc.__class__.__name__}: {exc}); fail-closed")


if __name__ == "__main__":
    # Once the gate runs it exits 0 or 2 only; field-gate.sh relies on this to tell "ran" from "never started".
    try:
        main()
    except SystemExit as exc:
        if exc.code not in (0, 2):
            os._exit(2)
        raise
    except BaseException:  # an error before main()'s own handlers, KeyboardInterrupt: deny, never exit 1
        os._exit(2)
