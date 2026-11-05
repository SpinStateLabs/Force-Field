# force — Claude Code Plugin

A toggleable FORCE protocol implementation for Claude Code. Five letters, five constraints, designed to neutralize AI sycophancy and hallucination on analytical work.

## What it does

- **F** — Forbid Flattery & Force Corrections
- **O** — Oppose the Premise
- **R** — Reference Verified Sources
- **C** — Chain-of-Thought
- **E** — Express Uncertainty

Each component is independently toggleable via the `/force` slash command. State persists across sessions in `~/.claude/state/force.json`.

## Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install force@force-field
/reload-plugins
/force
```

## Usage

```
/force                         show current state
/force on                      enable all five components
/force off                     master OFF (skill becomes passive)
/force F off                   disable Forbid Flattery only
/force preset brainstorm       F+C+E (no objections-first, no source gating)
/force preset audit            F+R+C+E (skip objections, prioritize sources)
/force reset                   restore defaults
```

## Presets

| Preset | Components | Use case |
|---|---|---|
| `analysis` (default) | F+O+R+C+E | Client analysis, financial modeling, audit work |
| `brainstorm` | F+C+E | Exploratory chat, idea generation |
| `draft` | F+C | Writing assistance |
| `audit` | F+R+C+E | Document review against source material |

## File structure

```
force/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── force/
│       ├── SKILL.md                    # When and how to apply
│       ├── protocol.md                 # The 5 letter blocks
│       └── protocol-defaults.json      # Seed state for first run
├── commands/
│   └── force.md                        # /force slash command logic
└── README.md
```

State lives outside the plugin at `~/.claude/state/force.json` so it survives plugin updates.

## When the skill auto-applies

Without explicit invocation, the skill activates when:
1. Master is ON in state file AND
2. The request involves analytical work, decision support, financial analysis, code review, audit work, or technical writing.

For casual conversation or simple lookups, the skill stays passive.

## Related

- Landing page: [spinstatelabs.ca/force](https://spinstatelabs.ca/force) — full kit (one-pager PDFs, Claude.ai system prompt, n8n workflow)
- Author: Don Hagell · [Spin State Labs](https://spinstatelabs.ca)

## License

MIT — see [LICENSE](../../LICENSE)
