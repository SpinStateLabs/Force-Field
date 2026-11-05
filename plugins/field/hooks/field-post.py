#!/usr/bin/env python3
"""
FIELD post-call evidence hook -- Claude Code PostToolUse hook (field plugin v1.5, ADR-0075 part (a)).

Evidence only. It never blocks, never fails a tool and writes nothing to stdout: it ALWAYS exits 0, and any
internal error is swallowed (fail-open; one stderr line says the evidence was not recorded).

What it records: when the gate (field-gate.py) answered a call with "ask" (ledger record decision "ask",
rule "E3-policy") and Claude Code then fires PostToolUse for the same tool_use_id in the same session, the
call RAN. The hook appends ONE record, rule "E3-policy-executed", to the same hash-chained ledger, under the
gate's lock, through the gate's own ledger_append. A declined or blocked call produces no PostToolUse, so a
logged ask with no "E3-policy-executed" record did not run (declined, or never answered).

What it does NOT record: who approved. The PostToolUse input names no approver (ADR-0071 Implementation, host
matrix), so every record says human_approval "not_evidenced" and approver null. P-25 stays unmet. A call that
ran under a permission_mode other than "default" is marked as NOT a human approval (mode_is_default false):
`auto`, `acceptEdits`, `dontAsk`, `bypassPermissions` or an unknown mode can run an ask without a person.

Finding the ask: the newest ledger record for the tool_use_id. The ledger stays the only store of record. The
gate keeps a sidecar index of its asks in the state directory (see field-gate.py, ledger_view); this hook reads
it without the lock, scans only the ledger bytes after the index's offset, and uses the index for the rest. It
trusts the sidecar exactly when the gate does: it must match the ledger (identity, length, bytes before its offset)
and its claims must re-derive from the ledger (the open segment, the newest 512 lines, every time, plus the gate's
random sample of completed segments). Otherwise it scans the whole ledger newest first, as before. It never
writes the sidecar (only the gate does, under its lock). A hit in the index, ask or executed record, is confirmed
by reading the ledger line it names. Cost: O(records appended since the gate last saved the index, plus the
sampled segments) instead of one read of the whole ledger per PostToolUse. What a forged sidecar can still do:
hide an ask that sits in a completed segment the check did not re-derive on this call (no record is written; the
same window the gate's E5 has, see the README); it cannot make the hook write a record for a call that has no ask.
A non-ask call is found absent without taking the lock.

Fields read from the hook input: hook_event_name, session_id, tool_use_id, permission_mode, cwd. Nothing else
(tool_input and tool_response are not read, so no tool output reaches the ledger).
No manifest (project not governed), an unparsable manifest, no ledger, a missing ledger entry, an ask that is
not in this session, or a record already written for the id: no-op.
"""
import datetime
import importlib.util
import json
import pathlib
import sys

RULE = "E3-policy-executed"
ASK_RULE = "E3-policy"
MAX_POST_INPUT_BYTES = 8 * 1024 * 1024  # PostToolUse carries tool_response, so more than the gate's 4 MiB


def _gate():
    here = pathlib.Path(__file__).resolve().with_name("field-gate.py")
    spec = importlib.util.spec_from_file_location("field_gate", here)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find(ledger_path, session, tool_use_id, gate=None, root=None):
    """'duplicate', the ask record, or None. Newest first; the ask precedes any executed record.
    With the gate module: the gate's incremental index answers for the verified part of the ledger and only the
    bytes appended since are scanned (gate.ledger_find_ask; same answer as the full scan below, which it falls
    back to when the sidecar is missing or does not match the ledger)."""
    if gate is not None:
        return gate.ledger_find_ask(ledger_path, root, session, tool_use_id)
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


def record(ask, session, tool_use_id, mode, source):
    default = mode == "default"
    if default:
        note = ("the call ran after the gate's ask; permission_mode was default, so a prompt was expected, "
                "but the hook input does not say who answered")
    else:
        note = (f"NOT a human approval: the call ran under permission_mode {mode!r}, which can run an ask "
                "without a person; the hook input does not say who, if anyone, answered")
    return {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "session": session, "tool": ask.get("tool"), "tool_use_id": tool_use_id,
            "permission_mode": mode, "input_digest": ask.get("input_digest"), "store_source": source,
            "decision": "executed", "rule": RULE, "ran": True, "ask_hash": ask.get("hash"),
            "human_approval": "not_evidenced", "approver": None, "mode_is_default": default,
            "reason": note}


def main():
    raw = sys.stdin.buffer.read(MAX_POST_INPUT_BYTES + 1)
    if len(raw) > MAX_POST_INPUT_BYTES:
        return
    inp = json.loads(raw)
    if not isinstance(inp, dict) or inp.get("hook_event_name", "PostToolUse") != "PostToolUse":
        return
    tool_use_id = inp.get("tool_use_id")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        return
    session = inp.get("session_id", "unknown")  # as the gate reads it, so the two compare equal
    mode = inp.get("permission_mode")
    mode = mode if isinstance(mode, str) else None
    gate = _gate()
    root = gate.project_root(inp)
    manifest = gate.load_manifest(gate.manifest_path(root))
    if not isinstance(manifest, dict) or manifest.get("_unparsed"):
        return  # not governed, or unreadable: evidence only, so nothing to enforce and nothing to record
    ledger_path, source = gate.resolve_store(manifest, root)
    if not ledger_path.exists() or not isinstance(find(ledger_path, session, tool_use_id, gate, root), dict):
        return  # most calls end here, without the lock (the ask is in the ledger before the tool runs)
    _lock = gate.gate_lock(root)  # noqa: F841  (held until exit)
    ask = find(ledger_path, session, tool_use_id, gate, root)  # again under the lock: parallel posts append once
    if isinstance(ask, dict):
        gate.ledger_append(ledger_path, record(ask, session, tool_use_id, mode, source))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:  # evidence only: never a non-zero exit, never a blocked or failed tool
        try:
            sys.stderr.write(f"FIELD post-hook: evidence not recorded ({exc.__class__.__name__})\n")
        except Exception:
            pass
    sys.exit(0)
