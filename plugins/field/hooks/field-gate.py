#!/usr/bin/env python3
"""
FIELD Enforcement Gate — Claude Code PreToolUse hook (field plugin v1.1).

Reads field-manifest.yaml (schema field.spinstatelabs.ca/v1) from the project directory
($CLAUDE_PROJECT_DIR, else the hook input's cwd, else the process cwd) and enforces:
  E1  kill switch      -> deny ALL gated tool calls while the sentinel file exists.
                          Sentinel = enforcement.kill_switch.endpoint when method is `file`;
                          otherwise the default .claude/state/KILL.
  E2  protected paths  -> deny Edit/Write/MultiEdit/NotebookEdit/Bash touching governance files:
                          the manifest, .claude/settings*.json, hooks.json, the ledger, the call
                          counter, plus every regex in enforcement.protected_paths.
  E3  irreversible ops -> deny Bash commands matching enforcement.irreversible_actions.deny_patterns
                          (Python re.search), independent of irreversible_action_policy.
  E4  call budget      -> deny once the session's gated-call count exceeds `max` of the
                          enforcement.rate_limits entry {action: tool_call, period: session}.
  L   ledger           -> append a sha-256 hash-chained JSONL record for every decision to
                          ledger.store when it is path-like, else .claude/state/field-ledger.jsonl.

Exit 0 = allow. Exit 2 = deny (stderr line + JSON permissionDecision surfaced to the model).
Fail-closed: with a manifest present, an unreadable manifest, missing PyYAML, a misconfigured
kill switch, or any internal error denies with rule E0. Without a manifest the hook does nothing.
Dependencies: PyYAML (pip install pyyaml). Without it the gate fails closed (E0).
Limits: regex matching is a tripwire, not a sandbox; the call counter is not locked against
parallel tool calls; Read/Glob/Grep are not gated (see hooks.json matcher).
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys

MANIFEST_NAME = "field-manifest.yaml"
STATE_DIR = ".claude/state"
DEFAULT_KILL = STATE_DIR + "/KILL"
DEFAULT_LEDGER = STATE_DIR + "/field-ledger.jsonl"
COUNTER_FILE = STATE_DIR + "/field-session-calls.json"
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
# Built-in governance files: regexes matched against the target path (file tools) or the
# whole command text (Bash). Backslashes are normalised to '/' before matching.
BUILTIN_PROTECTED = [r".*field-manifest\.ya?ml$", r".*\.claude/settings.*\.json$", r".*hooks\.json$"]
BUDGET_ACTIONS = {"tool_call"}
BUDGET_PERIODS = {"session", "per-session", "per_session"}


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
        return None, None, f"kill_switch.method is 'file' but endpoint {endpoint!r} is not a file path"
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


def ledger_append(ledger_path, record):
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
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
        deny(ledger_path, event, "E1", f"kill switch tripped ({flag}); all tool calls halted")

    # E2 protected governance files: built-ins + resolved ledger/counter + manifest extras.
    counter = root / COUNTER_FILE
    protected = list(BUILTIN_PROTECTED)
    for p in (ledger_path, counter):
        protected.append(re.escape(_norm(p)) + "$")
        try:
            protected.append(re.escape(_norm(p.relative_to(root))) + "$")
        except ValueError:
            pass
    protected += [str(p) for p in (enf.get("protected_paths") or [])]
    targets = []
    if tool in FILE_TOOLS:
        targets.append(_norm(ti.get("file_path") or ti.get("notebook_path") or ""))
    if tool == "Bash":
        targets.append(_norm(ti.get("command", "")))
    for target in targets:
        for pat in protected:
            if re.search(pat, target):
                deny(ledger_path, event, "E2", f"write/touch of protected governance path matched '{pat}'")

    # E3 irreversible action patterns (Bash command text).
    if tool == "Bash":
        cmd = ti.get("command", "") or ""
        pats = (enf.get("irreversible_actions") or {}).get("deny_patterns") or []
        for pat in pats:
            if re.search(str(pat), cmd):
                deny(ledger_path, event, "E3", f"command matched irreversible-action pattern '{pat}'")

    # E4 tool-call budget (runtime proxy for spend_cap): counts gated calls per session.
    budget = tool_call_budget(enf)
    if budget:
        counts = json.loads(counter.read_text(encoding="utf-8")) if counter.exists() else {}
        n = counts.get(session, 0) + 1
        counts[session] = n
        counter.parent.mkdir(parents=True, exist_ok=True)
        counter.write_text(json.dumps(counts), encoding="utf-8")
        if n > budget:
            deny(ledger_path, event, "E4", f"session tool-call budget {budget} exceeded (call #{n})")

    ledger_append(ledger_path, {**event, "decision": "allow"})
    sys.exit(0)


def main():
    try:
        inp = json.load(sys.stdin)
        if not isinstance(inp, dict):
            inp = {}
    except Exception:
        inp = {}
    root = project_root(inp)
    manifest = load_manifest(manifest_path(root))
    if manifest is None:
        sys.exit(0)  # no manifest: not a FIELD-governed project, do nothing
    ledger_path, store_source = resolve_store(manifest, root)
    try:
        enforce(inp, manifest, root, ledger_path, store_source)
    except SystemExit:
        raise
    except Exception as exc:
        emit_deny("E0", f"gate internal error ({exc.__class__.__name__}: {exc}); fail-closed")


if __name__ == "__main__":
    main()
