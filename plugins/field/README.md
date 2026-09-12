# field — Claude Code Plugin

FIELD is Spin State Labs' governance framework for agentic AI. Where **FORCE** constrains what an
AI *says* on a given response, **FIELD** constrains how an AI is *deployed, controlled, and held
accountable*. FORCE is runtime prompt hygiene; FIELD is design-time governance. They compose.

## The five letters

- **F** — Federated — trust protocols across ownership boundaries (which peers, on what basis)
- **I** — Identity — attribution and sovereignty (whose agent, what jurisdiction, what data scope)
- **E** — Enforcement — the brakes and rails (kill switch, spend cap, escalation, irreversible-action policy)
- **L** — Ledger — the immutable, cryptographically sealed audit trail
- **D** — Delegation — the authorization chain from a human principal to the agent

Every FIELD-governed agent carries one **manifest** (`field-manifest.yaml`) declaring its posture
across all five. The `/field` command generates, validates, and audits it.

## Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install field@force-field
/reload-plugins
/field
```

Manual / air-gapped installs: see [INSTALL.md](INSTALL.md).

## Usage

```
/field                         show skill state + working manifest
/field on | off                toggle proactive assistance
/field init [template]         create ./field-manifest.yaml
/field validate                check the manifest against the schema
/field assess                  walk the five letters interactively
/field audit                   audit-ready summary of the manifest
/field export [json|yaml]      print the manifest in a format
/field template <name>         set the default template
/field reset                   restore skill defaults
/field kill                    trip the kill switch (create the sentinel file)
/field resume                  show how a human lifts the kill switch; confirm when lifted
/field verify                  check the ledger hash chain (tamper-evident)
```

## Templates

| Template | Use case |
|---|---|
| `default` | Baseline general use. Fill in principal, kill switch, and delegation. |
| `financial-agent` | FP&A / audit-adjacent. 7-year ledger retention, sealed, kill switch tied to spend cap. |
| `read-only-agent` | Retrieval / analysis. Zero write scope, no write delegation, reduced enforcement. |
| `client-facing-agent` | Draft-only outbound. Human review at every escalation, no autonomous send. |

Bootstrap with `/field init <template>`.

## The manifest lifecycle

```
/field init financial-agent     →  writes ./field-manifest.yaml from a template
   (walk F→I→E→L→D, fill REPLACE-ME)
/field validate                 →  VALID / INVALID + critical gaps + warnings
/field audit                    →  audit-ready block for external review
```

A manifest is **INVALID** if it lacks any of the five sections, or is missing a kill switch, a
delegation grantor, an identity principal, or a sealed ledger. Those are the non-negotiables.

## File structure

```
field/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── field/
│       ├── SKILL.md                    # when and how to apply
│       ├── framework.md                # the five letters in operational depth
│       ├── field-defaults.json         # seed state for first run
│       ├── manifest-schema.json        # JSON Schema for field-manifest.yaml
│       └── templates/
│           ├── field-manifest-default.yaml
│           ├── field-manifest-financial-agent.yaml
│           ├── field-manifest-read-only-agent.yaml
│           └── field-manifest-client-facing-agent.yaml
├── commands/
│   └── field.md                        # /field slash command logic
├── hooks/
│   ├── hooks.json                      # PreToolUse registration (auto-loaded by Claude Code)
│   ├── field-gate.py                   # the Enforcement Gate (E1–E4, L)
│   ├── verify-ledger.py                # hash-chain verifier (/field verify)
│   └── test/                           # fixture + smoke test: bash hooks/test/run.sh
├── install.ps1 / install.sh            # manual installers
├── INSTALL.md
└── README.md
```

Skill state lives outside the plugin at `~/.claude/state/field.json` so it survives plugin updates.
Manifests live per-project at `./field-manifest.yaml` — one per agent.

## Composition with FORCE

Every FIELD-governed agent should apply FORCE at runtime. The manifest declares it:

```yaml
runtime_protocol:
  name: FORCE
  version: "1.0"
  preset: analysis
```

Install both: `/plugin install force@force-field` and `/plugin install field@force-field`.

## Runtime enforcement (v1.1)

The plugin ships an **Enforcement Gate**: a Claude Code `PreToolUse` hook (`hooks/`) that reads
`./field-manifest.yaml` and enforces it while you work.

| Rule | Manifest key | Effect |
|---|---|---|
| E1 kill switch | `enforcement.kill_switch.endpoint` with `method: file` (else `.claude/state/KILL`) | sentinel file present → every gated tool call denied |
| E2 protected paths | built-in set + `enforcement.protected_paths` (regexes) | edits/commands touching the manifest, `.claude/settings*.json`, `hooks.json`, the ledger denied |
| E3 irreversible actions | `enforcement.irreversible_actions.deny_patterns` (regexes) | matching Bash commands denied |
| E4 call budget | `enforcement.rate_limits` entry `{action: tool_call, period: session}` | per-session tool-call ceiling (a proxy, not a dollar spend cap) |
| L ledger | `ledger.store` when path-like, else `.claude/state/field-ledger.jsonl` | every decision appended, sha-256 hash-chained; `/field verify` checks it |

Gated tools: Bash, Edit, Write, MultiEdit, NotebookEdit. Requires `python3` and PyYAML on PATH;
without PyYAML the gate fails closed. The gate loads only with the plugin install (Method A);
`--bare` and `disableAllHooks` turn it off. Once a manifest exists the agent cannot edit it —
governance changes are made by the human, outside the session.

## Limitations

Enforcement and Ledger are runtime-enforced in Claude Code (E1–E4, L above); Federated, Identity
and Delegation remain declared, not enforced. The spend cap remains a tool-call proxy. The ledger
hash chain is tamper-evident, not tamper-proof — anyone with write access can rewrite it. Regex
matching is a guardrail, not a sandbox. `/field audit` produces an audit-ready report;
independent certification is a separate service.

## Related

- Landing page: [spinstatelabs.ca/field](https://spinstatelabs.ca/field)
- Companion plugin: [`force`](../force/README.md) — the runtime protocol FIELD wraps
- Author: Don Hagell · [Spin State Labs](https://spinstatelabs.ca)

## License

MIT — see [LICENSE](../../LICENSE)
