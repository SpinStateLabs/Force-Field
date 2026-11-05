"""hooks.json configuration tests (ADR-0081). Run by run_hooks_config.sh; prints PASS/FAIL lines.

A PreToolUse command hook that times out, crashes, cannot start or prints invalid JSON does not block the tool
call unless the hook sets "onFailure": "block" (Claude Code 2.1.295 and later). The gate is a PreToolUse hook, so
without the key a stalled or broken gate lets every call through. Static checks, no Claude Code needed (the live
proof is run_timeout_live.sh, which is not in run_all.sh or CI):

  1. every PreToolUse hook in hooks.json (the gate) is a command or http hook with onFailure "block", an explicit
     integer timeout, and no async/asyncRewake (the docs: onFailure has no effect on background hooks);
  2. the PostToolUse evidence hook does not set onFailure "block" (ADR-0081: the tool already ran, so a failure
     could only show stderr to the model; there is nothing to block);
  3. the checker itself: each mutant of the shipped file below must be rejected for the reason it names.
     A checker that passes a mutant is a FAIL.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS_JSON = os.path.join(HERE, "..", "hooks.json")
GATE = 'sh "${CLAUDE_PLUGIN_ROOT}/hooks/field-gate.sh"'
POST = 'sh "${CLAUDE_PLUGIN_ROOT}/hooks/field-post.sh"'
fail = 0


def report(ok, label, detail=""):
    global fail
    if ok:
        print("PASS  " + label)
    else:
        print("FAIL  " + label + (" (" + detail + ")" if detail else ""))
        fail = 1


def handlers(cfg, event):
    for group in (cfg.get("hooks") or {}).get(event) or []:
        for h in group.get("hooks") or []:
            yield group.get("matcher"), h


def problems(cfg):
    """Every reason this hooks.json would let a failed gate hook through or misregisters the hooks; [] = OK."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("hooks"), dict):
        return ["no top-level hooks object"]
    out = []
    pre = list(handlers(cfg, "PreToolUse"))
    if not any(m == "*" and h.get("command") == GATE for m, h in pre):
        out.append("PreToolUse '*' does not run the gate launcher")
    for _, h in pre:
        name = h.get("command") or h.get("url") or repr(h)
        if h.get("type") not in ("command", "http"):
            out.append("PreToolUse hook %s: type %r takes no onFailure (command and http only)" % (name, h.get("type")))
        if h.get("onFailure") != "block":
            out.append("PreToolUse hook %s: onFailure is %r, not 'block'" % (name, h.get("onFailure", "<unset>")))
        t = h.get("timeout")
        if not (isinstance(t, int) and not isinstance(t, bool) and 1 <= t <= 600):
            out.append("PreToolUse hook %s: timeout %r is not an explicit integer number of seconds (1-600)" % (name, t))
        for k in ("async", "asyncRewake"):
            if h.get(k):
                out.append("PreToolUse hook %s: %s is set (onFailure has no effect on background hooks)" % (name, k))
    post = list(handlers(cfg, "PostToolUse"))
    if not any(h.get("command") == POST for _, h in post):
        out.append("PostToolUse does not run the evidence hook launcher")
    for _, h in post:
        if h.get("onFailure") not in (None, "continue"):
            out.append("PostToolUse hook %s: onFailure %r (ADR-0081: leave it 'continue')" % (h.get("command"), h.get("onFailure")))
    return out


try:
    with open(HOOKS_JSON, encoding="utf-8") as fh:
        shipped = json.load(fh)
except Exception as exc:  # unreadable or invalid JSON: Claude Code would not load the gate at all
    report(False, "hooks.json parses as JSON", "%s: %s" % (exc.__class__.__name__, exc))
    sys.exit(1)
report(True, "hooks.json parses as JSON")
found = problems(shipped)
report(not found, "shipped hooks.json: gate hook fails closed (onFailure block, explicit timeout, not async)", "; ".join(found))
gate = [h for m, h in handlers(shipped, "PreToolUse") if h.get("command") == GATE]
report(len(gate) == 1 and gate[0].get("onFailure") == "block" and gate[0].get("timeout") == 10,
       "shipped gate entry: onFailure == 'block' and timeout == 10", repr(gate))


def mutant(label, expect, edit):
    """Apply edit(cfg) to a copy of the shipped file; the checker must reject it with a reason containing expect."""
    cfg = copy.deepcopy(shipped)
    edit(cfg)
    got = problems(cfg)
    report(any(expect in p for p in got), "mutant rejected: " + label, "checker said %r" % got)


def gate_entry(cfg):
    return cfg["hooks"]["PreToolUse"][0]["hooks"][0]


def post_entry(cfg):
    return cfg["hooks"]["PostToolUse"][0]["hooks"][0]


mutant("onFailure removed from the gate", "not 'block'", lambda c: gate_entry(c).pop("onFailure", None))
mutant("gate onFailure 'continue'", "not 'block'", lambda c: gate_entry(c).__setitem__("onFailure", "continue"))
mutant("gate onFailure 'Block' (wrong case)", "not 'block'", lambda c: gate_entry(c).__setitem__("onFailure", "Block"))
mutant("gate timeout removed (600 s default)", "timeout None", lambda c: gate_entry(c).pop("timeout", None))
mutant("gate timeout as a string", "timeout '10'", lambda c: gate_entry(c).__setitem__("timeout", "10"))
mutant("gate timeout true", "timeout True", lambda c: gate_entry(c).__setitem__("timeout", True))
mutant("gate async true", "async is set", lambda c: gate_entry(c).__setitem__("async", True))
mutant("gate asyncRewake true", "asyncRewake is set", lambda c: gate_entry(c).__setitem__("asyncRewake", True))
mutant("gate as a prompt hook", "takes no onFailure", lambda c: gate_entry(c).__setitem__("type", "prompt"))
mutant("a second PreToolUse hook without onFailure", "onFailure is '<unset>'",
       lambda c: c["hooks"]["PreToolUse"].append({"matcher": "Bash", "hooks": [{"type": "command", "command": "sh x.sh", "timeout": 5}]}))
mutant("gate launcher no longer registered", "does not run the gate launcher",
       lambda c: gate_entry(c).__setitem__("command", "python3 x.py"))
mutant("PostToolUse evidence hook onFailure 'block'", "leave it 'continue'", lambda c: post_entry(c).__setitem__("onFailure", "block"))
mutant("no hooks object", "no top-level hooks object", lambda c: c.pop("hooks"))

sys.exit(1 if fail else 0)
