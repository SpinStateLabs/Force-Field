# force-field — Claude Code Plugin (2.2.0)

The **Force-Field Protocol** from Spin State Labs, in one package with three skills.

- **FORCE** constrains what an AI *says* at runtime: Forbid flattery, Oppose the premise, Reference verified
  sources, Chain-of-thought, Express uncertainty. Skill `force`, command `/force`. See [FORCE.md](FORCE.md).
- **FIELD** constrains how an agent is *deployed and held accountable* at design time: Federated, Identity,
  Enforcement, Ledger, Delegation, in a per-agent `field-manifest.yaml`. Skill `field`, command `/field`,
  manifest templates, and the **Enforcement Gate** hook. See [FIELD.md](FIELD.md) and [INSTALL.md](INSTALL.md).
- **force-field** explains how they compose, with an "apply both" workflow.

2.0.0 replaces the separate `field` (1.5.2) and `force-field` (1.0.0) plugins and includes FORCE. Remove the old
`field` before updating: with it still installed, the gate hook runs twice. The marketplace also lists `force`
(FORCE only, no governance hooks) for people who want just that; install `force` or `force-field`, not both, or
`/force` is defined twice.

## Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install force-field@force-field
/reload-plugins
```

## What it runs, sends, or fetches

- Skills and commands: Markdown instructions. `force` reads and writes `~/.claude/state/force.json`; `field`
  reads and writes `~/.claude/state/field.json`.
- The Enforcement Gate: a `PreToolUse` hook and a `PostToolUse` evidence hook, run locally
  (`hooks/field-gate.sh` starts `hooks/field-gate.py` with Python 3 and PyYAML) on every tool call except Read,
  Glob, Grep, LS, NotebookRead and TodoWrite. With a `./field-manifest.yaml` it can deny tool calls (kill
  switch, protected paths, irreversible actions, tool-call budget) and appends each decision to a local
  hash-chained ledger (`.claude/state/field-ledger.jsonl`). With no manifest and no FIELD state in
  `.claude/state/` it does nothing. A project that already holds FIELD state and loses its manifest is
  denied (E0) until a human restores it or removes `.claude/state/`. No network calls.
- The gate is a tripwire on command text, not a sandbox. Requirements and limitations: FIELD.md, INSTALL.md.
- The Estate Connector: an MCP server (`field-estate`, `connector/estate_connector.py`, Python 3 standard
  library) started by Claude Code. In `local` mode (the default) it makes no network call. In `estate` mode it
  forwards MCP messages to the estate URL you set, with your FIELD API key as a Bearer token.

In `local` mode nothing in this plugin sends data off your machine. In `estate` mode the MCP traffic of the
`field-estate` server (tool calls to it and their arguments) goes to your estate URL, and nowhere else.

## Estate Connector (local or estate)

Settings (Claude Code asks for them on install from `/plugin`; change them later with
`/plugin configure force-field@force-field`, then restart Claude Code):

| Setting | What it is |
|---|---|
| `estate_mode` | `local` (default): FIELD runs on this machine only. `estate`: connect to an existing estate created by the FIELD platform. |
| `estate_url` | Estate mode only. The estate's MCP server endpoint (Streamable HTTP), e.g. `https://estate.example.com/mcp`. https is required except for localhost. |
| `field_api_key` | Estate mode only. The FIELD API key the platform issued for the estate. Marked sensitive: Claude Code keeps it in its credential store, not in `settings.json`. |

From a shell: `claude plugin install force-field@force-field --config estate_mode=estate --config estate_url=<url>`
and set the key with `claude plugin configure force-field@force-field --values-stdin` (a JSON object on stdin),
so it does not land in shell history.

Check the connection with `/mcp` (server `plugin:force-field:field-estate`). In local mode, or when the estate
settings are incomplete, the server offers one tool, `estate_status`, that says which mode is active and what is
missing. In estate mode the tools are whatever the estate's MCP server provides. A rejected key appears in `/mcp`
as "rejected the FIELD API key (HTTP 401)". Redirects are not followed, so the key is never sent to a second host.

Limits: the connector does not change the Enforcement Gate, which still enforces locally from
`./field-manifest.yaml` in both modes. Server-to-client requests over a standalone SSE stream (HTTP GET) are not
relayed; request/response tools work. The command is `python3`; on Windows that must be on `PATH`.

## Links

- FORCE: [spinstatelabs.ca/force](https://spinstatelabs.ca/force) · FIELD: [spinstatelabs.ca/field](https://spinstatelabs.ca/field)
- Repository: [github.com/SpinStateLabs/Force-Field](https://github.com/SpinStateLabs/Force-Field)
- Author: Don Hagell · [Spin State Labs](https://spinstatelabs.ca)

## License

MIT, see [LICENSE](LICENSE).
