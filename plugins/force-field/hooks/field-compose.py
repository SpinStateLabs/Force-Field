#!/usr/bin/env python3
"""FIELD x FORCE runtime composition (SessionStart hook).

Reads the project's field-manifest.yaml (same lookup as field-gate.py: $FIELD_MANIFEST, else
field-manifest.yaml under $CLAUDE_PROJECT_DIR, else the hook input's cwd, else the working directory)
and, when `runtime_protocol` declares `name: FORCE` with a valid `preset`, injects that preset's FORCE
blocks (skills/force/protocol.md) into the session as additionalContext. The manifest wins over the
user-level force.json: a FIELD-governed agent runs the preset its manifest signs.

Fails OPEN and says nothing: this hook only adds context. It never blocks, never denies, never writes
state. The Enforcement Gate (field-gate.py) is unchanged and stays fail-closed. Any problem (no manifest,
no PyYAML and no parsable block, unknown preset, missing protocol.md) -> exit 0 with no stdout.
"""
import json
import os
import re
import sys

PRESETS = {  # skills/force/protocol-defaults.json "_comment"
    "analysis": "FORCE",
    "brainstorm": "FCE",
    "draft": "FC",
    "audit": "FRCE",
}


def manifest_path(cwd):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    if not (root and os.path.isdir(root)):
        root = cwd if cwd and os.path.isdir(cwd) else os.getcwd()
    m = os.environ.get("FIELD_MANIFEST") or "field-manifest.yaml"
    return m if os.path.isabs(m) else os.path.join(root, m)


def runtime_protocol(text):
    try:
        import yaml
        doc = yaml.safe_load(text)
        rp = doc.get("runtime_protocol") if isinstance(doc, dict) else None
        return rp if isinstance(rp, dict) else None
    except Exception:
        pass
    m = re.search(r"(?m)^runtime_protocol:\s*\n((?:[ \t]+\S.*\n?|[ \t]*\n)+)", text)
    if not m:
        return None
    rp = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"\s+(\w+):\s*[\"']?([^\"'#\s]+)", line)
        if kv:
            rp[kv.group(1)] = kv.group(2)
    return rp


def force_blocks(letters, protocol_md):
    parts = re.split(r"(?m)^---\s*$", protocol_md)
    out = []
    for p in parts:
        h = re.search(r"(?m)^## \[(\w)\] ", p)
        if h and h.group(1) in letters:
            out.append(p.strip())
        elif re.search(r"(?m)^## OUTPUT RULES", p):
            out.append(p.strip())
    return out


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}
    try:
        with open(manifest_path(data.get("cwd")), encoding="utf-8") as f:
            rp = runtime_protocol(f.read())
        if not rp or str(rp.get("name", "")).upper() != "FORCE":
            return
        preset = str(rp.get("preset", "")).lower()
        if preset not in PRESETS:
            sys.stderr.write("FIELD compose: unknown FORCE preset %r; nothing injected\n" % preset)
            return
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "..", "skills", "force", "protocol.md"), encoding="utf-8") as f:
            blocks = force_blocks(PRESETS[preset], f.read())
        if not blocks:
            return
        ctx = ("FORCE runtime protocol, preset `%s`, applied because this project's field-manifest.yaml "
               "declares it as runtime_protocol. Apply the following to every response in this session.\n\n%s"
               % (preset, "\n\n".join(blocks)))
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                            "additionalContext": ctx}}) + "\n")
    except Exception:
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
