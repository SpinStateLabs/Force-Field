#!/usr/bin/env python3
"""Convert a FIELD manifest (YAML) to the JSON the n8n reference workflow embeds.

Usage: manifest_to_json.py field-manifest.yaml > manifest.json
Needs PyYAML (the Enforcement Gate needs it too). Exits 1 on anything that is not a mapping with an
`enforcement` mapping, so a broken manifest never reaches the workflow (which would deny every call, E0).
"""
import json
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")


def convert(text):
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or not isinstance(doc.get("enforcement"), dict):
        raise ValueError("manifest must be a mapping with an `enforcement` mapping")
    return doc


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            print(json.dumps(convert(fh.read()), indent=2, default=str, sort_keys=True))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        sys.exit(f"manifest_to_json: {exc}")
