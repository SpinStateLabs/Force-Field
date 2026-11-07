# FIELD reference enforcement in n8n

A sample n8n workflow that applies a FIELD manifest's `enforcement` block to tool calls **outside Claude Code**.
It answers one question, "may this call run?", as `allow`, `deny` or `ask`, and writes a hash-chained ledger record
for the answer. Reference quality: read it, adapt it, do not treat it as the Enforcement Gate.

## What it enforces

| Rule | Behaviour |
|---|---|
| E1 kill switch | A flag in the workflow's static data. `POST /field-operate {"op":"kill"}` halts every call, read-only tools included; `{"op":"resume"}` lifts it. Both are ledgered. |
| E3 irreversible actions | `enforcement.irreversible_actions.deny_patterns` run against the shell command (`Bash`, `PowerShell`). Default verdict `deny`; with `deny_patterns_verdict: policy` the match follows `irreversible_action_policy` (`forbid` deny, `require_human_approval` ask, `allow_with_ledger` allow with rule `E3-allowed`), as in the gate. |
| E4 call budget | `rate_limits: [{action: tool_call, period: session, max: N}]`, counted per `session_id`. Calls denied by E3 are not counted, as in the gate. |
| L ledger | sha-256 hash chain, byte-compatible with the gate's: `hooks/verify-ledger.py` verifies it. |
| Fail-closed | Any error, missing manifest, malformed input or untranslatable pattern is `deny` with rule `E0`. |

## What this is not (read before relying on it)

- **It advises; the caller enforces.** n8n cannot stop a tool call. The agent host must call `/field-gate` before every
  tool call and treat anything but `allow` as a block, **including a timeout, an HTTP error or an unreachable n8n**.
  If the host fails open, nothing here protects anything.
- **Not the Enforcement Gate.** Missing: E2 protected paths, E5 session-written execution, the estate sentinel, and
  the gate's shell canonicalisation. Known gaps, asserted in `test/test_n8n.py`: `git push -f origin x` and
  `git push origin +feature:main` are **allowed** unless your patterns name those spellings (the Python gate denies
  both). Write patterns for every spelling you care about, or use the gate.
- **Ledger is not durable.** It lives in n8n workflow static data (last 1000 records), which n8n saves only for
  production (activated) executions, not manual test runs. Ship it to a real store; `../ledger/ledger_ship.py` is the
  reference shipper for files, S3 and Postgres. The chain is tamper-evident, not tamper-proof.
- **Not safe under concurrent calls (measured).** n8n saves static data per execution, last writer wins. With 30 parallel
  `/field-gate` calls, all 30 answered `allow` but only 2 ledger records and a session count of 2 were kept, so **E4 undercounts
  and ledger records are lost**; a `kill` issued during a burst of 25 gate calls was **silently undone** (the kill call
  succeeded, the persisted flag ended `false`, the next call was allowed). Setting `N8N_CONCURRENCY_PRODUCTION_LIMIT=1` did
  **not** serialise these webhook executions in the test (30 calls in 1 s, 1 record kept), so do not rely on it.
  Sequential calls are correct: 30 calls kept 30 records and a count of 30, and the 47-record chain verified intact.
  Until this is redesigned, serialise calls at the **caller** (one in flight at a time) and do not use this workflow for kill
  or budget enforcement with concurrent callers. The Python gate takes a file lock for exactly this reason.
- **Regex dialect.** Patterns are Python regexes in the manifest. A leading `(?i)` is translated; any other inline flag
  (`(?s)`, `(?x)`, `(?i:...)`) is an E0 deny, never silently dropped. Other Python/JS differences (named groups,
  possessive quantifiers) are not translated.
- **Only partly verified in a live n8n**: see "Verification" below.

## Use

```
python3 n8n/build_workflow.py path/to/field-manifest.yaml > field-enforcement.workflow.json   # needs PyYAML
```

1. Import `field-enforcement.workflow.json` into n8n. Without an argument it embeds the `ssl-fp-builder` template as a sample.
2. Create two **Header Auth** credentials (`FIELD gate caller`, `FIELD operator`; use different secrets) and select them on the
   two webhook nodes. Without them the webhooks reject calls; do not switch authentication off.
3. The `Field Gate` Code node calls `require("crypto")`: start n8n with `NODE_FUNCTION_ALLOW_BUILTIN=crypto`.
4. Activate the workflow (static data is not kept in manual runs).
5. Call it with the Claude Code hook input shape:

```
curl -s -H "X-Auth: $SECRET" -H 'content-type: application/json' $N8N/webhook/field-gate \
  -d '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"git push --force origin x"},"permission_mode":"default"}'
# {"permissionDecision":"deny","rule":"E3","reason":"command matched irreversible-action pattern '...'","hash":"..."}
```

To change the manifest, regenerate the workflow (the Code node embeds it as a `MANIFEST` constant) or edit that constant.
`manifest_to_json.py manifest.yaml` prints just the JSON.

## Files

- `field-gate-core.js`: the decision logic, the single source of truth. The workflow's Code nodes embed it verbatim.
- `build_workflow.py`: generates `field-enforcement.workflow.json` from the core and a manifest.
- `manifest_to_json.py`: YAML manifest to JSON.
- `test/run_n8n.sh`: decision cases, a differential check against `hooks/field-gate.py`, known-gap assertions, ledger
  verification under `hooks/verify-ledger.py`, workflow sync and a stubbed execution of the Code nodes.

## Verification

Run against n8n 2.46.6 (Node 24, legacy expression engine, bound to 127.0.0.1), 2026-11-06 and 2026-11-07:

- **Passed:** import with two Header Auth credentials; activation; webhook calls over HTTP. No auth, a wrong secret, and the
  other webhook's secret each get 403. `ls` is allowed; `git push --force` is denied E3; `kill` then a call is denied E1;
  `resume` restores; a body with no `tool_name` and an empty body are denied E0; invalid JSON gets HTTP 422 (the caller must
  treat that as a block). Static data persisted between executions (the kill flag survived). The ledger read back from n8n's
  database verifies under `hooks/verify-ledger.py`. Without `NODE_FUNCTION_ALLOW_BUILTIN=crypto` the Code node fails with
  `DisallowedModuleError`.
- **Failed:** concurrent calls, see "Not safe under concurrent calls" above.
- **Not done:** n8n's native expression engine (would not load in the test environment, so the legacy engine ran the
  `responseBody` expression), other n8n versions, queue mode, Windows.
