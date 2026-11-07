#!/usr/bin/env python3
"""Generate field-enforcement.workflow.json (the importable n8n workflow) from field-gate-core.js.

Usage: build_workflow.py [manifest.yaml] > field-enforcement.workflow.json
The Code node embeds the core verbatim, so the workflow cannot drift from the tested file: the tests rebuild
and compare. Without an argument the sample manifest is the ssl-fp-builder template.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from manifest_to_json import convert  # noqa: E402

DEFAULT_MANIFEST = HERE.parent / "skills" / "field" / "templates" / "field-manifest-ssl-fp-builder.yaml"


def core_source():
    src = (HERE / "field-gate-core.js").read_text(encoding="utf-8")
    src, n = re.subn(r"^module\.exports = .*$", "", src, flags=re.M)
    if n != 1:
        raise SystemExit("field-gate-core.js: expected exactly one module.exports line")
    return src.rstrip() + "\n"


GATE_TAIL = '''
// ---- n8n glue ----
// MANIFEST: replace with `manifest_to_json.py your-manifest.yaml`. An empty or malformed manifest denies every call (E0).
const MANIFEST = %s;
const sd = $getWorkflowStaticData("global");
sd.field = sd.field || { killed: false, counts: {}, lastHash: "0".repeat(64), ledger: [] };
return $input.all().map((item) => ({ json: decide(MANIFEST, item.json.body !== undefined ? item.json.body : item.json, sd.field, Date.now()) }));
'''

OPERATE_TAIL = '''
// ---- n8n glue ----
const sd = $getWorkflowStaticData("global");
sd.field = sd.field || { killed: false, counts: {}, lastHash: "0".repeat(64), ledger: [] };
return $input.all().map((item) => {
  const body = item.json.body !== undefined ? item.json.body : item.json;
  return { json: operate(sd.field, body && body.op, Date.now()) };
});
'''


def build(manifest):
    core = core_source()
    gate_js = core + GATE_TAIL % json.dumps(manifest, indent=2, sort_keys=True, default=str)
    operate_js = core + OPERATE_TAIL

    def webhook(node_id, name, path, pos, cred):
        return {"id": node_id, "name": name, "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": pos,
                "webhookId": node_id,
                "parameters": {"httpMethod": "POST", "path": path, "authentication": "headerAuth",
                               "responseMode": "responseNode", "options": {}},
                "credentials": {"httpHeaderAuth": {"id": "REPLACE-ME", "name": cred}}}

    def code(node_id, name, js, pos):
        return {"id": node_id, "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos,
                "parameters": {"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": js}}

    def respond(node_id, name, pos):
        return {"id": node_id, "name": name, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
                "position": pos,
                "parameters": {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}",
                               "options": {"responseCode": 200}}}

    nodes = [
        webhook("5c1d0001-0000-4000-8000-00000000f001", "Gate Webhook", "field-gate", [0, 0], "FIELD gate caller"),
        code("5c1d0001-0000-4000-8000-00000000f002", "Field Gate", gate_js, [260, 0]),
        respond("5c1d0001-0000-4000-8000-00000000f003", "Respond Verdict", [520, 0]),
        webhook("5c1d0001-0000-4000-8000-00000000f004", "Operate Webhook", "field-operate", [0, 240], "FIELD operator"),
        code("5c1d0001-0000-4000-8000-00000000f005", "Field Operate", operate_js, [260, 240]),
        respond("5c1d0001-0000-4000-8000-00000000f006", "Respond Operate", [520, 240]),
    ]
    link = lambda a, b: {a: {"main": [[{"node": b, "type": "main", "index": 0}]]}}  # noqa: E731
    connections = {**link("Gate Webhook", "Field Gate"), **link("Field Gate", "Respond Verdict"),
                   **link("Operate Webhook", "Field Operate"), **link("Field Operate", "Respond Operate")}
    return {"name": "FIELD reference enforcement (ssl-fp)", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "active": False}


if __name__ == "__main__":
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MANIFEST
    print(json.dumps(build(convert(path.read_text(encoding="utf-8"))), indent=2, sort_keys=True))
