#!/usr/bin/env python3
"""FIELD Estate Connector: a stdio MCP server for the force-field plugin.

Mode comes from the plugin's userConfig (passed in by .mcp.json as environment variables):

  FIELD_ESTATE_MODE     "local" (default) or "estate"
  FIELD_ESTATE_URL      the estate's MCP endpoint (Streamable HTTP), e.g. https://estate.example.com/mcp
  FIELD_ESTATE_API_KEY  the FIELD API key issued by the platform for an existing estate

local   The connector makes no network call. It serves one tool, `estate_status`, which reports that FIELD
        runs locally (the Enforcement Gate hook and the local ledger).
estate  The connector is a transparent proxy: each JSON-RPC message read on stdin is POSTed to
        FIELD_ESTATE_URL with `Authorization: Bearer <FIELD_ESTATE_API_KEY>`, and the reply (JSON or an SSE
        stream) is written to stdout. The estate decides which tools exist. A 401/403 on `initialize` is
        returned as a JSON-RPC error naming the cause, so a bad key shows up in /mcp instead of silently.

The API key is sent only to FIELD_ESTATE_URL and only over https (plain http is accepted for loopback hosts).
It is never logged. Python 3 standard library only.
"""
from __future__ import annotations

import ipaddress
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SERVER_NAME = "field-estate"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2025-06-18"
TIMEOUT_S = float(os.environ.get("FIELD_ESTATE_TIMEOUT_S", "30") or 30)

# JSON-RPC error codes (server-defined range).
E_CONFIG = -32001
E_AUTH = -32002
E_UPSTREAM = -32003


def log(msg: str) -> None:
    print(f"[{SERVER_NAME}] {msg}", file=sys.stderr, flush=True)


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _opt(env: dict, name: str) -> str:
    """A userConfig value; an unset option may arrive as the literal ${user_config.x} placeholder."""
    v = (env.get(name) or "").strip()
    return "" if v.startswith("${user_config.") else v


class Config:
    def __init__(self, env: dict) -> None:
        self.mode = (_opt(env, "FIELD_ESTATE_MODE") or "local").lower()
        self.url = _opt(env, "FIELD_ESTATE_URL")
        self.key = _opt(env, "FIELD_ESTATE_API_KEY")

    def problem(self) -> str | None:
        """Why estate mode cannot run, or None. Never includes the key."""
        if self.mode not in ("local", "estate"):
            return f"estate_mode must be 'local' or 'estate', got {self.mode!r}"
        if self.mode == "local":
            return None
        if not self.url:
            return "estate mode needs estate_url (the estate's MCP server URL); run /plugin configure force-field@force-field"
        if not self.key:
            return "estate mode needs the FIELD API key (field_api_key); run /plugin configure force-field@force-field"
        u = urllib.parse.urlsplit(self.url)
        if u.scheme not in ("https", "http") or not u.hostname:
            return f"estate_url must be an http(s) URL, got {self.url!r}"
        if u.username or u.password:
            return "estate_url must not carry credentials; put the key in field_api_key"
        if u.scheme == "http" and not _is_loopback(u.hostname):
            return "estate_url must use https (plain http is allowed only for localhost) so the API key is not sent in clear"
        return None


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


# ---------------------------------------------------------------- local mode

LOCAL_TOOL = {
    "name": "estate_status",
    "description": "Report which FIELD mode this plugin is in (local or estate) and where enforcement happens.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
}


def status_text(cfg: Config, problem: str | None) -> str:
    if problem:
        return f"FIELD estate connector: NOT CONNECTED. {problem}."
    return ("FIELD mode: local. Enforcement runs on this host only (Enforcement Gate hook, ledger in "
            ".claude/state/field-ledger.jsonl). No estate is contacted. To connect to an estate, set "
            "estate_mode=estate, estate_url and field_api_key with /plugin configure force-field@force-field.")


def serve_local(cfg: Config, problem: str | None) -> None:
    """Minimal MCP server: initialize, tools/list, tools/call(estate_status), ping."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send(error(None, -32700, "parse error"))
            continue
        if not isinstance(msg, dict) or "id" not in msg:
            continue  # notification (e.g. notifications/initialized): nothing to answer
        rid, method = msg.get("id"), msg.get("method")
        if method == "initialize":
            pv = (msg.get("params") or {}).get("protocolVersion") or DEFAULT_PROTOCOL
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": pv,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": status_text(cfg, problem),
            }})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [LOCAL_TOOL]}})
        elif method == "tools/call":
            name = (msg.get("params") or {}).get("name")
            if name != LOCAL_TOOL["name"]:
                send(error(rid, -32602, f"unknown tool {name!r}"))
            else:
                send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": status_text(cfg, problem)}],
                    "isError": bool(problem),
                }})
        else:
            send(error(rid, -32601, f"method not found: {method}"))


# ---------------------------------------------------------------- estate mode

class EstateProxy:
    def __init__(self, cfg: Config, opener=None) -> None:
        self.cfg = cfg
        self.session_id: str | None = None
        self.protocol: str | None = None
        self.opener = opener or urllib.request.build_opener(_NoRedirect)

    def headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.cfg.key}",
            "User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        if self.protocol:
            h["MCP-Protocol-Version"] = self.protocol
        return h

    def forward(self, msg: dict) -> list[dict]:
        """POST one message to the estate; return the JSON-RPC messages to write back."""
        rid = msg.get("id")
        is_request = "id" in msg and "method" in msg
        body = json.dumps(msg).encode()
        req = urllib.request.Request(self.cfg.url, data=body, headers=self.headers(), method="POST")
        try:
            with self.opener.open(req, timeout=TIMEOUT_S) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            if not is_request:
                log(f"estate returned HTTP {e.code} for a notification")
                return []
            if e.code in (401, 403):
                return [error(rid, E_AUTH, f"estate rejected the FIELD API key (HTTP {e.code}); check field_api_key "
                                           "and that the key belongs to this estate")]
            if e.code == 404 and self.session_id:
                self.session_id = None
                return [error(rid, E_UPSTREAM, "estate session expired (HTTP 404); reconnect with /mcp")]
            if 300 <= e.code < 400:
                return [error(rid, E_UPSTREAM, f"estate redirected (HTTP {e.code}); set estate_url to the final "
                                               "URL (redirects are not followed, so the key is not forwarded)")]
            return [error(rid, E_UPSTREAM, f"estate returned HTTP {e.code}")]
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            return [error(rid, E_UPSTREAM, f"estate unreachable: {reason}")] if is_request else []

        if status == 202 or not raw.strip():
            return []
        if ctype == "text/event-stream":
            out = parse_sse(raw.decode("utf-8", "replace"))
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return [error(rid, E_UPSTREAM, "estate sent a response that is not JSON")] if is_request else []
            out = data if isinstance(data, list) else [data]
        if msg.get("method") == "initialize":
            for m in out:
                pv = (m.get("result") or {}).get("protocolVersion") if isinstance(m, dict) else None
                if pv:
                    self.protocol = pv
        return [m for m in out if isinstance(m, dict)]

    def close(self) -> None:
        if not self.session_id:
            return
        req = urllib.request.Request(self.cfg.url, headers=self.headers(), method="DELETE")
        try:
            self.opener.open(req, timeout=5).close()
        except Exception:
            pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow redirects: urllib would re-send the Authorization header to the new host."""

    def redirect_request(self, *a, **k):
        return None


def parse_sse(text: str) -> list[dict]:
    out, buf = [], []
    for line in text.splitlines() + [""]:
        if line.startswith("data:"):
            buf.append(line[5:].lstrip(" "))
        elif line == "" and buf:
            try:
                obj = json.loads("\n".join(buf))
                out.extend(obj if isinstance(obj, list) else [obj])
            except json.JSONDecodeError:
                log("skipped a non-JSON SSE event")
            buf = []
    return out


def serve_estate(proxy: EstateProxy) -> None:
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                send(error(None, -32700, "parse error"))
                continue
            for m in (msg if isinstance(msg, list) else [msg]):
                if isinstance(m, dict):
                    for reply in proxy.forward(m):
                        send(reply)
    finally:
        proxy.close()


def main() -> int:
    cfg = Config(os.environ)
    problem = cfg.problem()
    if cfg.mode == "estate" and not problem:
        host = urllib.parse.urlsplit(cfg.url).hostname
        log(f"estate mode: proxying to {host}")
        serve_estate(EstateProxy(cfg))
    else:
        if problem:
            log(f"configuration problem: {problem}")
        serve_local(cfg, problem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
