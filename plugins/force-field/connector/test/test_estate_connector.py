"""Tests for connector/estate_connector.py. Run: python3 -m unittest -v (from this folder) or run_connector.sh."""
import http.server
import json
import os
import subprocess
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CONNECTOR = os.path.join(HERE, "..", "estate_connector.py")
KEY = "test-field-key-123"


class FakeEstate(http.server.BaseHTTPRequestHandler):
    seen = []  # (method, path, headers, body)

    def log_message(self, *a):
        pass

    def _reply(self, code, body=b"", ctype="application/json", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_DELETE(self):
        FakeEstate.seen.append(("DELETE", self.path, {k.lower(): v for k, v in self.headers.items()}, None))
        self._reply(200)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeEstate.seen.append(("POST", self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        if self.path == "/redirect":
            return self._reply(307, extra={"Location": "http://127.0.0.1:1/elsewhere"})
        if self.headers.get("Authorization") != f"Bearer {KEY}":
            return self._reply(401, b'{"error":"unauthorized"}')
        if "id" not in body:
            return self._reply(202)
        m, rid = body["method"], body["id"]
        if m == "initialize":
            res = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                   "serverInfo": {"name": "fake-estate", "version": "0"}}
            return self._reply(200, json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}).encode(),
                               extra={"Mcp-Session-Id": "sess-1"})
        if m == "tools/list":  # answered as an SSE stream
            msg = {"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "estate_agents", "inputSchema": {"type": "object"}}]}}
            sse = f"event: message\ndata: {json.dumps(msg)}\n\n".encode()
            return self._reply(200, sse, ctype="text/event-stream")
        return self._reply(200, json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"echo": m}}).encode())


def start_estate():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeEstate)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run(env_over, msgs):
    env = {k: v for k, v in os.environ.items() if not k.startswith("FIELD_ESTATE_")}
    env.update(env_over)
    inp = "".join(json.dumps(m) + "\n" for m in msgs)
    p = subprocess.run([sys.executable, CONNECTOR], input=inp, capture_output=True, text=True, env=env, timeout=30)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()], p.stderr


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
INITED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
STATUS = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "estate_status", "arguments": {}}}


class LocalMode(unittest.TestCase):
    def test_default_is_local_with_status_tool(self):
        out, _ = run({}, [INIT, INITED, LIST, STATUS])
        self.assertEqual([m["id"] for m in out], [1, 2, 3])
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "field-estate")
        self.assertEqual([t["name"] for t in out[1]["result"]["tools"]], ["estate_status"])
        self.assertIn("FIELD mode: local", out[2]["result"]["content"][0]["text"])
        self.assertFalse(out[2]["result"]["isError"])

    def test_unsubstituted_placeholders_mean_unset(self):
        out, _ = run({"FIELD_ESTATE_MODE": "${user_config.estate_mode}",
                      "FIELD_ESTATE_API_KEY": "${user_config.field_api_key}"}, [STATUS])
        self.assertIn("FIELD mode: local", out[0]["result"]["content"][0]["text"])

    def test_local_makes_no_network_call(self):
        srv = start_estate(); FakeEstate.seen.clear()
        url = f"http://127.0.0.1:{srv.server_port}/mcp"
        run({"FIELD_ESTATE_MODE": "local", "FIELD_ESTATE_URL": url, "FIELD_ESTATE_API_KEY": KEY}, [INIT, LIST])
        srv.shutdown(); srv.server_close()
        self.assertEqual(FakeEstate.seen, [])


class Misconfigured(unittest.TestCase):
    def check(self, env, needle):
        out, err = run(env, [INIT, STATUS])
        r = out[1]["result"]
        self.assertTrue(r["isError"])
        self.assertIn("NOT CONNECTED", r["content"][0]["text"])
        self.assertIn(needle, r["content"][0]["text"])
        self.assertNotIn(KEY, err + json.dumps(out))

    def test_estate_without_url(self):
        self.check({"FIELD_ESTATE_MODE": "estate", "FIELD_ESTATE_API_KEY": KEY}, "estate_url")

    def test_estate_without_key(self):
        self.check({"FIELD_ESTATE_MODE": "estate", "FIELD_ESTATE_URL": "https://e.example/mcp"}, "FIELD API key")

    def test_plain_http_to_remote_host_refused(self):
        self.check({"FIELD_ESTATE_MODE": "estate", "FIELD_ESTATE_URL": "http://estate.example/mcp",
                    "FIELD_ESTATE_API_KEY": KEY}, "https")

    def test_credentials_in_url_refused(self):
        self.check({"FIELD_ESTATE_MODE": "estate", "FIELD_ESTATE_URL": "https://u:p@e.example/mcp",
                    "FIELD_ESTATE_API_KEY": KEY}, "credentials")

    def test_bad_mode(self):
        self.check({"FIELD_ESTATE_MODE": "cloud"}, "estate_mode")


class EstateMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = start_estate()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def env(self, path="/mcp", key=KEY):
        return {"FIELD_ESTATE_MODE": "estate", "FIELD_ESTATE_URL": self.base + path, "FIELD_ESTATE_API_KEY": key}

    def test_proxies_json_and_sse_with_session_and_bearer(self):
        FakeEstate.seen.clear()
        out, err = run(self.env(), [INIT, INITED, LIST])
        self.assertEqual([m["id"] for m in out], [1, 2])
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "fake-estate")
        self.assertEqual(out[1]["result"]["tools"][0]["name"], "estate_agents")
        posts = [s for s in FakeEstate.seen if s[0] == "POST"]
        self.assertEqual(len(posts), 3)
        self.assertTrue(all(h["authorization"] == f"Bearer {KEY}" for _, _, h, _ in posts))
        self.assertNotIn("mcp-session-id", posts[0][2])
        self.assertEqual(posts[1][2]["mcp-session-id"], "sess-1")
        self.assertEqual(posts[2][2]["mcp-protocol-version"], "2025-06-18")
        self.assertEqual([s[0] for s in FakeEstate.seen][-1], "DELETE")  # session closed at EOF
        self.assertNotIn(KEY, err)

    def test_bad_key_is_auth_error(self):
        out, err = run(self.env(key="wrong"), [INIT])
        self.assertEqual(out[0]["error"]["code"], -32002)
        self.assertIn("rejected the FIELD API key", out[0]["error"]["message"])
        self.assertNotIn("wrong", out[0]["error"]["message"])

    def test_redirect_not_followed(self):
        FakeEstate.seen.clear()
        out, _ = run(self.env(path="/redirect"), [INIT])
        self.assertIn("redirect", out[0]["error"]["message"])
        self.assertEqual(len(FakeEstate.seen), 1)

    def test_unreachable(self):
        out, _ = run({"FIELD_ESTATE_MODE": "estate", "FIELD_ESTATE_URL": "http://127.0.0.1:1/mcp",
                      "FIELD_ESTATE_API_KEY": KEY}, [INIT])
        self.assertIn("unreachable", out[0]["error"]["message"])


class Manifest(unittest.TestCase):
    def test_mcp_json_maps_every_user_config_key(self):
        root = os.path.join(HERE, "..", "..")
        with open(os.path.join(root, ".mcp.json")) as f:
            mcp = json.load(f)["mcpServers"]["field-estate"]
        with open(os.path.join(root, ".claude-plugin", "plugin.json")) as f:
            uc = json.load(f)["userConfig"]
        refs = {v[len("${user_config."):-1] for v in mcp["env"].values()}
        self.assertEqual(refs, set(uc))
        self.assertTrue(uc["field_api_key"]["sensitive"])
        self.assertEqual(uc["estate_mode"]["options"], ["local", "estate"])
        self.assertEqual(uc["estate_mode"]["default"], "local")


if __name__ == "__main__":
    unittest.main()
