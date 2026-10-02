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
  E2  protected paths  -> deny any gated tool touching governance files (file tools: the target
                          path; shell tools: the command text; other tools: every string input):
                          the manifest, .claude/settings*.json, hooks.json, the ledger, the call
                          counter, plus every regex in enforcement.protected_paths.
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

Exit 0 = allow. Exit 2 = deny (stderr line + JSON permissionDecision surfaced to the model).
Fail-closed: with a manifest present, an unreadable manifest, missing PyYAML, a misconfigured
kill switch, or any internal error denies with rule E0. Without a manifest the hook does nothing.
Dependencies: PyYAML (pip install pyyaml). Without it the gate fails closed (E0).
Limits: regex matching is a tripwire, not a sandbox; the call counter is not locked against
parallel tool calls; Read/Glob/Grep are not gated. E3/E5 only read shell tools: an MCP tool that
runs commands gets E1/E2/E4/L, not E3/E5. E5 matches command
text, not process execution: renames, sh -c "$(cat x)", eval and files created by Bash itself
(echo > x.sh, curl -o) are not caught; paths resolve against the project root, not the shell cwd.
"""
import datetime
import hashlib
import json
import os
import pathlib
import posixpath
import re
import shlex
import sys

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
# Built-in governance files: regexes matched against the target path (file tools) or the
# whole command text (shell tools) or every string input (other tools). Backslashes are normalised to '/' before matching.
BUILTIN_PROTECTED = [r".*field-manifest\.ya?ml$", r".*\.claude/settings.*\.json$", r".*hooks\.json$"]
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


def path_key(raw, root):
    """Ledger key for a file path. Root-relative POSIX path when it is inside the project root;
    otherwise 'sha256:<hex>' of the normalised absolute path, so the ledger never holds plaintext
    paths from outside the project (usernames, client folders). None for an empty value."""
    s = _norm(os.path.expanduser(str(raw or ""))).strip()
    if not s:
        return None
    win = bool(re.match(r"^[A-Za-z]:", _norm(str(root)))) or os.name == "nt"
    rootn = posixpath.normpath(_norm(str(root) if win else os.path.realpath(str(root))))
    if win:
        s = re.sub(r"^/([A-Za-z])/", r"\1:/", s)
    if not (s.startswith("/") or re.match(r"^[A-Za-z]:/", s)):
        s = rootn + "/" + s
    if not win:
        s = _norm(os.path.realpath(s))
    s = posixpath.normpath(s)
    if win:
        s, rootn = s.casefold(), rootn.casefold()
    if rootn in ("/", "") or re.match(r"^[a-z]:$", rootn.casefold()):
        return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()
    if (s.casefold() if win else s).startswith((rootn.casefold() if win else rootn) + "/"):
        return s[len(rootn) + 1:]
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


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


def _shell_tokens(cmd):
    cmd = re.sub(r"\$\(|`|<\(|>\(", " ; ", cmd).replace("\n", " ; ")
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)  # ValueError propagates: caller fails closed


def exec_suspect_tokens(cmd, depth=0):
    """Tokens that may be executed. Fail-closed: every token of a segment whose command word is
    not a known read-only tool, plus every token of a command that pipes/redirects into an interpreter."""
    toks = _shell_tokens(cmd or "")
    out, seg, segs = [], [], []
    for t in toks + [";"]:
        if t in SEPARATORS:
            segs.append(seg); seg = []
        else:
            seg.append(t)
    interp_anywhere = False
    for seg in segs:
        i = 0
        while i < len(seg) and (seg[i] in SHELL_KEYWORDS or REDIRECT.match(seg[i])
                                or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[i])):
            i += 2 if REDIRECT.match(seg[i]) else 1
        if i >= len(seg):
            continue
        word = posixpath.basename(_norm(seg[i]))
        if INTERPRETER_RE.match(re.sub(r"(?i)\.exe$", "", word).lower()) or word in WRAPPERS:
            interp_anywhere = True
        if word not in READ_ONLY:
            out.extend(seg)
            if depth < 3:
                for j, t in enumerate(seg[:-1]):
                    if t in ("-c", "-Command"):
                        out.extend(exec_suspect_tokens(seg[j + 1], depth + 1))
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
    sys.stderr.write(f"FIELD DENY [{rule}]: {reason}\n")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": "deny", "permissionDecisionReason": f"[{rule}] {reason}"}}))
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


def enforce(inp, manifest, root, ledger_path, store_source):
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

    # E2 protected governance files: built-ins + resolved ledger/counter + manifest extras.
    counter = root / COUNTER_FILE
    # (regex, label). Labels for the ledger and counter avoid echoing their absolute paths.
    protected = [(p, p) for p in BUILTIN_PROTECTED]
    for p, label in ((ledger_path, "the ledger"), (counter, "the call counter")):
        protected.append((re.escape(_norm(p)) + "$", label))
        try:
            protected.append((re.escape(_norm(p.relative_to(root))) + "$", label))
        except ValueError:
            pass
    protected += [(str(p), str(p)) for p in (enf.get("protected_paths") or [])]
    targets = []
    if tool in FILE_TOOLS:
        targets.append(_norm(ti.get("file_path") or ti.get("notebook_path") or ""))
    elif tool in SHELL_TOOLS:
        targets.append(_norm(shell_command(tool, ti)))
        if tool == "PowerShell":  # no parser: also check each token (conservative, like E5)
            targets.extend(_norm(t) for t in ps_tokens(shell_command(tool, ti)))
    else:  # MCP and other tools: any string input, or any token in one, naming a governance file
        for v in string_leaves(ti):
            targets.append(_norm(v).strip())
            targets.extend(_norm(t) for t in ps_tokens(v))
    for target in targets:
        for pat, label in protected:
            if re.search(pat, target):
                deny(ledger_path, event, "E2", f"write/touch of protected governance path matched '{label}'")

    # E3 irreversible action patterns (shell command text).
    if tool in SHELL_TOOLS:
        cmd = shell_command(tool, ti)
        pats = (enf.get("irreversible_actions") or {}).get("deny_patterns") or []
        for pat in pats:
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
                    toks = exec_suspect_tokens(shell_command(tool, ti))
                else:  # PowerShell: no parser, so every token counts (over-blocks reads; safe side)
                    toks = ps_tokens(shell_command(tool, ti))
                    # $PWD/x.sh, -FilePath:x.sh: also try the text after the last ':' or '$var/'.
                    toks += [re.sub(r"^.*(?::|\$[^/]*/)", "", _norm(t)) for t in toks]
            except ValueError:
                deny(ledger_path, event, "E0", "command could not be tokenised for E5; fail-closed")
            for tok in toks:
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
    bad_input = False
    try:
        inp = json.load(sys.stdin)
        if not isinstance(inp, dict):
            inp, bad_input = {}, True
    except Exception:
        inp, bad_input = {}, True
    if not bad_input and not isinstance(inp.get("tool_name", ""), str):
        bad_input = True
    if not bad_input and inp.get("tool_name") in UNGATED:
        sys.exit(0)  # read-only tool: not gated
    root = project_root(inp)
    manifest = load_manifest(manifest_path(root))
    if manifest is None:
        sys.exit(0)  # no manifest: not a FIELD-governed project, do nothing
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
    main()
