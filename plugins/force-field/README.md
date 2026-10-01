# force-field — Claude Code Plugin

The **Force-Field Protocol** umbrella plugin from Spin State Labs. One install for both layers of the
protocol, plus a skill that explains how they fit together.

- **FORCE** constrains what an AI *says* at runtime — Forbid flattery, Oppose the premise, Reference
  verified sources, Chain-of-thought, Express uncertainty.
- **FIELD** constrains how an agent is *deployed and held accountable* at design time — Federated,
  Identity, Enforcement, Ledger, Delegation — captured in a per-agent `field-manifest.yaml`.

They compose: every FIELD-governed agent runs FORCE at runtime. This plugin is a thin bundle. It holds
no protocol text of its own; the full FORCE protocol and FIELD framework ship in the companion plugins.

## What it installs

| Piece | Source | What you get |
|---|---|---|
| `force` plugin | dependency | `/force` command and the FORCE skill |
| `field` plugin | dependency | `/field` command, the FIELD skill, manifest templates, and the Enforcement Gate hook |
| `force-field` skill | this plugin | How FORCE and FIELD compose, when to use which, an "apply both" workflow, and a status check |

`force` and `field` are declared in this plugin's `dependencies` (same marketplace, no version pin), so
each tracks the latest version the marketplace publishes.

## Install

In Claude Code:

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install force-field@force-field
/reload-plugins
```

Claude Code installs `force` and `field` automatically as dependencies.

**On claude.ai and Cowork**, plugin dependencies are a Claude Code-only feature: installing
`force-field` there may not install its companions. Install `force` and `field` as well. The skill
checks for them and tells you if either is missing.

## Usage

Ask about the Force-Field Protocol, or about applying FORCE and FIELD to an agent, and the
`force-field` skill activates. Typical prompts:

- "Which Force-Field plugins do I have installed?" — status check; reports FORCE / FIELD present or missing.
- "Should I use FORCE or FIELD for this?" — the when-to-use-which guidance.
- "Set up governance for a new agent." — the apply-both workflow: set FORCE with `/force`, draft the
  manifest with `/field init` and `/field assess`, review the manifest's claims under FORCE, then
  `/field validate` and `/field audit`.

Day-to-day commands come from the companions: `/force` and `/field`. See their READMEs:
[force](../force/README.md) · [field](../field/README.md).

## What this plugin runs, sends, or fetches

**This plugin: nothing.** It contains one skill (Markdown instructions) and this README. No commands,
hooks, scripts, MCP servers, or network calls, and it reads no credentials.

**Its dependencies:**

- `force` — instructions only. Reads and writes a local state file, `~/.claude/state/force.json`.
- `field` — instructions plus the **Enforcement Gate**, a `PreToolUse` hook that runs `python3`
  locally (`hooks/field-gate.py`) on Bash, Edit, Write, MultiEdit, and NotebookEdit calls. When a
  `./field-manifest.yaml` exists, it can deny tool calls (kill switch, protected paths, irreversible
  actions, tool-call budget) and appends each decision to a local hash-chained ledger
  (`.claude/state/field-ledger.jsonl` by default). It requires PyYAML and makes no network calls.
  Without a manifest it does nothing. FIELD also reads and writes `~/.claude/state/field.json`.

Nothing in this plugin or its dependencies sends data off your machine.

## Links

- FORCE: [spinstatelabs.ca/force](https://spinstatelabs.ca/force)
- FIELD: [spinstatelabs.ca/field](https://spinstatelabs.ca/field)
- Repository: [github.com/SpinStateLabs/Force-Field](https://github.com/SpinStateLabs/Force-Field)
- Author: Don Hagell · [Spin State Labs](https://spinstatelabs.ca)

## License

MIT — see [LICENSE](LICENSE).
