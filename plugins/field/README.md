# field — Claude Code Plugin

Governance manifest tool for agentic AI systems. The design-time counterpart to the FORCE runtime protocol. Together they form the Force Field Framework.

## What it does

FIELD is a governance framework covering five dimensions of autonomous agent deployment:

- **F** — Federation. Trust protocols across agent boundaries.
- **I** — Identity. Who owns the agent, whose interests it represents.
- **E** — Enforcement. Kill switches, spend caps, escalation triggers.
- **L** — Ledger. Cryptographic immutable audit trail.
- **D** — Delegation. Authorization chain from human to agent.

The plugin lets you generate, validate, and audit FIELD manifests via the `/field` slash command.

## Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install field@force-field
/reload-plugins
/field
```

## Usage

```
/field                            show manifest status
/field init                       create manifest from default template
/field init financial-agent       create manifest from FP&A template
/field init read-only-agent       create manifest from research/analysis template
/field init client-facing-agent   create manifest from client-touch template
/field validate                   check manifest against schema
/field assess                     interactive five-letter compliance walkthrough
/field audit                      audit-ready summary for external review
/field export                     convert manifest to JSON
```

## Manifest location

FIELD manifests are per-project. The plugin operates on `./field-manifest.yaml` in the current working directory. Each agent or project gets its own manifest.

## Available templates

| Template | For agents that... |
|---|---|
| `default` | General baseline. Fill in every field. |
| `financial-agent` | Touch financial systems (NSPB, EPBCS, GL, journals). Tight enforcement, 7-year ledger. |
| `read-only-agent` | Read documents or run analysis without side effects. Wide read scope, zero write. |
| `client-facing-agent` | Interact directly with customers. Draft-only outbound, aggressive escalation. |

## Composition with FORCE

Every FIELD manifest declares a `runtime_protocol` block. Default: FORCE, preset "analysis". Override per template. Runtime protocol is asserted in v1.0 but not automatically wired — the actual application of FORCE at runtime is separate infrastructure.

## What v1.0 does NOT do

Be clear-eyed about scope:

- **Not a runtime enforcer.** v1.0 generates and validates the governance spec. Actual enforcement (halting agents when the kill switch fires, deducting from spend caps, appending to the ledger) requires infrastructure you build around the manifest.
- **Not automated certification.** `/field audit` produces an audit-ready report; independent third-party verification is separate.
- **Not cryptographic sealing.** The manifest declares seal_algorithm; the ledger store you configure must implement it.

Roadmap for v1.1+:

- Reference implementation of runtime enforcement in n8n
- Sample ledger stores (s3, Postgres) with sealing wired
- Third-party audit format specification

## File structure

```
field/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── field/
│       ├── SKILL.md
│       ├── framework.md              # The five letters in detail
│       └── manifest-schema.json      # JSON Schema for validation
├── commands/
│   └── field.md                      # /field slash command logic
├── templates/
│   ├── field-manifest-default.yaml
│   ├── field-manifest-financial-agent.yaml
│   ├── field-manifest-read-only-agent.yaml
│   └── field-manifest-client-facing-agent.yaml
└── README.md
```

## Related

- Landing page: [spinstatelabs.ca/field](https://spinstatelabs.ca/field) — full framework, methodology, reference architectures
- FORCE plugin: `/plugin install force@force-field` — runtime prompt protocol
- Roadmap: [ROADMAP.md](../../ROADMAP.md)

## License

MIT — see [LICENSE](../../LICENSE)
