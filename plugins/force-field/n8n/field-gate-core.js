// FIELD reference enforcement core (n8n). Pure, dependency-free except Node's `crypto`.
//
// A deliberately THIN subset of the Claude Code Enforcement Gate (hooks/field-gate.py), for a host that is not
// Claude Code: E1 kill switch, E3 irreversible-action patterns (+ policy verdicts), E4 per-session tool-call
// budget, L sha-256 hash-chained ledger. NOT implemented: E2 protected paths, E5 session-written exec, shell
// canonicalisation (e3_variants), the estate sentinel. See ../README.md "What this is not".
//
// decide(manifest, input, state, now) -> { permissionDecision: "allow"|"deny"|"ask", rule, reason, hash }
//   manifest  the FIELD manifest as a JSON object (manifest_to_json.py converts the YAML)
//   input     { session_id, tool_name, tool_input, tool_use_id?, permission_mode? }  (the Claude Code hook shape)
//   state     { killed: bool, counts: {session: n}, lastHash: str, ledger: [record] }  -- mutated
// Fail-closed: any error is a deny with rule E0.
"use strict";
const crypto = require("crypto");

const SHELL_TOOLS = ["Bash", "PowerShell"];
const UNGATED = ["Read", "Glob", "Grep", "LS", "NotebookRead", "TodoWrite"];
const MAX_COMMAND_BYTES = 64 * 1024;
const ASK_MODES = ["default", "acceptEdits", "auto", "dontAsk", "bypassPermissions"];
const POLICY_VERDICT = { forbid: "deny", require_human_approval: "ask", allow_with_ledger: "allow" };
// Record provenance, as the Python gate writes it since 1.6.0. The manifest reaches this core as a JSON object,
// not as file bytes, so the digest is over its canonical JSON and has its own name: it is NOT comparable with the
// Python gate's manifest_sha256 (the YAML file's bytes).
const GATE_VERSION = "n8n-1.6.0";
function manifestDigest(manifest) {
  try { return sha256(pyJson(manifest)); } catch (e) { return null; } // a value pyJson cannot write: no digest, no deny
}
const LEDGER_MAX = 1000; // records kept in n8n static data; ship them to a real store (see README)

const sha256 = (s) => crypto.createHash("sha256").update(s, "utf8").digest("hex");

// json.dumps(obj, sort_keys=True) as Python writes it (", " and ": " separators, ensure_ascii), so a chain
// written here verifies under hooks/verify-ledger.py. Integers, strings, booleans, null, arrays, objects only.
function pyJson(v) {
  if (v === null || v === undefined) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (!Number.isInteger(v)) throw new Error("non-integer number in a ledger record");
    return String(v);
  }
  if (typeof v === "string") {
    let out = '"';
    for (let i = 0; i < v.length; i++) {
      const c = v.charCodeAt(i);
      const ch = v[i];
      if (ch === '"') out += '\\"';
      else if (ch === "\\") out += "\\\\";
      else if (ch === "\n") out += "\\n";
      else if (ch === "\r") out += "\\r";
      else if (ch === "\t") out += "\\t";
      else if (ch === "\b") out += "\\b";
      else if (ch === "\f") out += "\\f";
      else if (c < 0x20 || c > 0x7e) out += c === 0x7f ? ch : "\\u" + c.toString(16).padStart(4, "0");
      else out += ch;
    }
    return out + '"';
  }
  if (Array.isArray(v)) return "[" + v.map(pyJson).join(", ") + "]";
  if (typeof v === "object") {
    return "{" + Object.keys(v).sort().map((k) => pyJson(k) + ": " + pyJson(v[k])).join(", ") + "}";
  }
  throw new Error("unserialisable value in a ledger record");
}

function isoUtc(now) { // Python's datetime.isoformat() form: 2026-11-06T18:46:19.123456+00:00
  return new Date(now).toISOString().replace(/\.(\d{3})Z$/, ".$1000+00:00");
}

// Python re.search pattern -> JS RegExp. Supports a leading (?i) (PowerShell patterns use it). Any other inline
// flag group cannot be translated faithfully, so it throws and the call is denied (E0), never silently ignored.
function compilePattern(pat, ignoreCase) {
  let src = String(pat);
  let flags = ignoreCase ? "i" : "";
  const lead = /^\(\?([a-z]+)\)/.exec(src);
  if (lead) {
    if (lead[1] !== "i") throw new Error("unsupported inline flag in pattern: " + lead[0]);
    flags = "i";
    src = src.slice(lead[0].length);
  }
  if (/\(\?[a-zA-Z-]+[:)]/.test(src)) throw new Error("unsupported inline flag group in pattern");
  return new RegExp(src, flags);
}

function budgetOf(enf) {
  for (const e of enf.rate_limits || []) {
    if (!e || typeof e !== "object") continue;
    const action = String(e.action || "").trim().toLowerCase();
    const period = String(e.period || "").trim().toLowerCase();
    if (action === "tool_call" && ["session", "per-session", "per_session"].includes(period)) {
      const n = parseInt(e.max, 10);
      return Number.isNaN(n) ? null : n;
    }
  }
  return null;
}

function append(state, event, extra, now) {
  const prev = state.lastHash || "0".repeat(64);
  const rec = Object.assign({}, event, extra, { prev_hash: prev });
  rec.hash = sha256(prev + pyJson(rec)); // hash covers the record without "hash", like ledger_append()
  state.lastHash = rec.hash;
  state.ledger.push(rec);
  if (state.ledger.length > LEDGER_MAX) state.ledger.splice(0, state.ledger.length - LEDGER_MAX);
  return rec;
}

function decide(manifest, input, state, now) {
  state.counts = state.counts || {};
  state.ledger = state.ledger || [];
  const prov = { manifest_json_sha256: manifestDigest(manifest), gate_version: GATE_VERSION, phase: "pre" };
  let event = Object.assign({ ts: isoUtc(now), tool: "unknown", store_source: "n8n" }, prov);
  const out = (decision, rule, reason) => {
    const extra = { decision, rule: rule || null, reason: rule ? reason : null }; // same keys on every decision
    const rec = append(state, event, extra, now);
    return { permissionDecision: decision, rule: rule || null, reason: reason || null, hash: rec.hash };
  };
  try {
    const inp = input && typeof input === "object" && !Array.isArray(input) ? input : null;
    const tool = inp && typeof inp.tool_name === "string" ? inp.tool_name : "";
    const ti = inp && inp.tool_input && typeof inp.tool_input === "object" ? inp.tool_input : {};
    event = {
      ts: isoUtc(now), session: (inp && inp.session_id) || "unknown", tool: tool || "unknown",
      tool_use_id: (inp && inp.tool_use_id) || null, permission_mode: (inp && inp.permission_mode) || null,
      input_digest: sha256(pyJson(ti)).slice(0, 16), store_source: "n8n",
    };
    Object.assign(event, prov);
    if (!inp || !tool) return out("deny", "E0", "input is not a tool call (no tool_name); fail-closed");
    if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
      return out("deny", "E0", "manifest missing or not an object; fail-closed");
    }
    const enf = manifest.enforcement;
    if (!enf || typeof enf !== "object" || Array.isArray(enf)) {
      return out("deny", "E0", "enforcement section missing or not a mapping; fail-closed");
    }

    // E1 kill switch. A kill always holds, including for read-only tools (the Python gate reads the default
    // sentinel before the UNGATED shortcut for the same reason).
    if (state.killed) return out("deny", "E1", "kill switch tripped; all tool calls halted");

    if (UNGATED.includes(tool)) return out("allow");

    const isShell = SHELL_TOOLS.includes(tool);
    const cmd = isShell ? String(ti.command || "") : "";
    if (isShell && Buffer.byteLength(cmd, "utf8") > MAX_COMMAND_BYTES) {
      return out("deny", "E0", "shell command exceeds " + MAX_COMMAND_BYTES + " bytes; fail-closed");
    }

    // E3 irreversible-action patterns, then (policy mode) the manifest's irreversible_action_policy.
    let pending = null;
    if (isShell) {
      const ia = enf.irreversible_actions || {};
      if (typeof ia !== "object" || Array.isArray(ia)) return out("deny", "E0", "irreversible_actions is not a mapping; fail-closed");
      const vmode = String(ia.deny_patterns_verdict || "deny").trim().toLowerCase();
      if (!["deny", "policy"].includes(vmode)) return out("deny", "E0", "deny_patterns_verdict must be deny or policy; fail-closed");
      const pats = ia.deny_patterns || [];
      if (!Array.isArray(pats)) return out("deny", "E0", "deny_patterns is not a list; fail-closed");
      for (const pat of pats) {
        let rx;
        try { rx = compilePattern(pat, tool === "PowerShell"); } catch (e) {
          return out("deny", "E0", "invalid deny_patterns entry (" + e.message + "); fail-closed");
        }
        if (!rx.test(cmd)) continue;
        if (vmode === "deny") return out("deny", "E3", "command matched irreversible-action pattern '" + pat + "'");
        const verdict = POLICY_VERDICT[String(enf.irreversible_action_policy || "").trim().toLowerCase()];
        if (!verdict) return out("deny", "E0", "deny_patterns_verdict is policy but irreversible_action_policy is missing or invalid; fail-closed");
        if (verdict === "deny") return out("deny", "E3", "command matched irreversible-action pattern '" + pat + "' (irreversible_action_policy: forbid)");
        if (verdict === "ask") {
          if (!ASK_MODES.includes(inp.permission_mode)) {
            return out("deny", "E3", "command matched irreversible-action pattern '" + pat + "'; policy is require_human_approval but permission_mode " + JSON.stringify(inp.permission_mode || null) + " has no known human prompt; denied");
          }
          pending = ["ask", "E3-policy", "command matched irreversible-action pattern '" + pat + "'; irreversible_action_policy is require_human_approval"];
        } else {
          pending = ["allow", "E3-allowed", "command matched irreversible-action pattern '" + pat + "'; irreversible_action_policy is allow_with_ledger"];
        }
        break;
      }
    }

    // E4 per-session tool-call budget (counts gated calls that reach this point, as the Python gate does).
    const budget = budgetOf(enf);
    if (budget !== null) {
      const sid = String(event.session);
      const n = (state.counts[sid] || 0) + 1;
      state.counts[sid] = n;
      if (n > budget) return out("deny", "E4", "session tool-call budget " + budget + " exceeded (call #" + n + ")");
    }

    if (pending) return out(pending[0], pending[1], pending[2]);
    return out("allow");
  } catch (e) {
    return out("deny", "E0", "gate error (" + (e && e.message ? e.message : "unknown") + "); fail-closed");
  }
}

// Operator actions (kill / resume) are ledgered like any decision.
function operate(state, op, now) {
  state.ledger = state.ledger || [];
  if (op !== "kill" && op !== "resume") throw new Error("unknown operator action");
  state.killed = op === "kill";
  const rec = append(state, { ts: isoUtc(now), session: "operator", tool: "operator", store_source: "n8n" },
    { decision: "allow", rule: op === "kill" ? "E1-kill" : "E1-resume", reason: "operator " + op }, now);
  return { killed: state.killed, hash: rec.hash };
}

module.exports = { decide, operate, pyJson, compilePattern };
