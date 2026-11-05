# force-field — Claude Code Plugin (2.0.0)

The **Force-Field Protocol** from Spin State Labs, in one package with three skills.

- **FORCE** constrains what an AI *says* at runtime: Forbid flattery, Oppose the premise, Reference verified
  sources, Chain-of-thought, Express uncertainty. Skill `force`, command `/force`. See [FORCE.md](FORCE.md).
- **FIELD** constrains how an agent is *deployed and held accountable* at design time: Federated, Identity,
  Enforcement, Ledger, Delegation, in a per-agent `field-manifest.yaml`. Skill `field`, command `/field`,
  manifest templates, and the **Enforcement Gate** hook. See [FIELD.md](FIELD.md) and [INSTALL.md](INSTALL.md).
- **force-field** explains how they compose, with an "apply both" workflow.

2.0.0 replaces the separate `force` (1.0.2), `field` (1.5.2) and `force-field` (1.0.0) plugins. Remove those
before updating: with an old `field` still installed, the gate hook runs twice.

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

Nothing in this plugin sends data off your machine.

## Links

- FORCE: [spinstatelabs.ca/force](https://spinstatelabs.ca/force) · FIELD: [spinstatelabs.ca/field](https://spinstatelabs.ca/field)
- Repository: [github.com/SpinStateLabs/Force-Field](https://github.com/SpinStateLabs/Force-Field)
- Author: Don Hagell · [Spin State Labs](https://spinstatelabs.ca)

## License

MIT, see [LICENSE](LICENSE).
