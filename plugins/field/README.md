# field — Claude Code Plugin

FIELD is Spin State Labs' governance framework for agentic AI. Where **FORCE** constrains what an
AI *says* on a given response, **FIELD** constrains how an AI is *deployed, controlled, and held
accountable*. FORCE is runtime prompt hygiene; FIELD is design-time governance. They compose.

## The five letters

- **F** — Federation — trust protocols across ownership boundaries (which peers, on what basis)
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

## Limitations

FIELD v1.0 is a **manifest tool**, not a runtime enforcer. It generates and validates the
governance spec; actual enforcement (kill switches firing, ledger writes, spend caps) is
infrastructure you build around the manifest. `/field audit` produces an audit-ready report;
independent certification is a separate service.

## Related

- Landing page: [spinstatelabs.ca/field](https://spinstatelabs.ca/field)
- Companion plugin: [`force`](../force/README.md) — the runtime protocol FIELD wraps
- Author: Don Hagell · [Spin State Labs](https://spinstatelabs.ca)

## License

MIT — see [LICENSE](../../LICENSE)
