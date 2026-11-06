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
- **Single-writer assumption.** Parallel executions can race on the static data (counter and chain tip). The Python gate
  holds a file lock for this; n8n offers none. Run the workflow with concurrency 1 if the chain must stay linear.
- **Regex dialect.** Patterns are Python regexes in the manifest. A leading `(?i)` is translated; any other inline flag
  (`(?s)`, `(?x)`, `(?i:...)`) is an E0 deny, never silently dropped. Other Python/JS differences (named groups,
  possessive quantifiers) are not translated.
- **Not verified in a live n8n** unless the PR says otherwise: see "Verification" below.

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

See the PR description for what was and was not run against a real n8n.
