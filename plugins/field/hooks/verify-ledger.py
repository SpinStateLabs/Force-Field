#!/usr/bin/env python3
"""Verify the sha-256 hash chain of a FIELD ledger.

Usage: verify-ledger.py [path]
Without a path the ledger is located exactly as the gate locates it: ledger.store from
field-manifest.yaml when it is path-like, else .claude/state/field-ledger.jsonl, relative to
$CLAUDE_PROJECT_DIR or the current directory.
Exit 0 = LEDGER INTACT, 1 = LEDGER TAMPERED, 2 = ledger missing.
The chain is tamper-evident, not tamper-proof: anyone with write access can rewrite it.
"""
import hashlib
import importlib.util
import json
import pathlib
import sys


def _gate():
    here = pathlib.Path(__file__).resolve().with_name("field-gate.py")
    spec = importlib.util.spec_from_file_location("field_gate", here)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve(argv):
    if len(argv) > 1:
        return pathlib.Path(argv[1])
    gate = _gate()
    root = gate.project_root({})
    manifest = gate.load_manifest(gate.manifest_path(root))
    return gate.resolve_store(manifest if isinstance(manifest, dict) else None, root)[0]


def main():
    path = resolve(sys.argv)
    if not path.exists():
        print(f"LEDGER MISSING: {path}")
        sys.exit(2)
    prev = "0" * 64
    ok = True
    records = 0
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            records += 1
            try:
                rec = json.loads(line)
                h = rec.pop("hash")
            except Exception:
                print(f"line {i}: unreadable record")
                ok = False
                continue
            if rec.get("prev_hash") != prev:
                print(f"line {i}: broken link")
                ok = False
            body = json.dumps(rec, sort_keys=True)
            if hashlib.sha256((prev + body).encode()).hexdigest() != h:
                print(f"line {i}: hash mismatch")
                ok = False
            prev = h
    print(f"{'LEDGER INTACT' if ok else 'LEDGER TAMPERED'} ({records} records, {path})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
