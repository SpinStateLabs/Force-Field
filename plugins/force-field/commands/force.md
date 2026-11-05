---
description: Toggle FORCE protocol components on or off. Use to enable, disable, or query the FORCE protocol state.
---

# /force — slash command

Handles all `/force *` invocations. Parse the argument, update state, confirm.

## State location

State file path (in precedence order):

1. `./.claude/state/force.json` (project-level, if it exists in the current working directory tree)
2. `~/.claude/state/force.json` (user-level, always falls back here)

**Always write back to the same file that was read.** Never auto-promote project state to user state without explicit instruction.

**Bootstrap**: if neither file exists, create `~/.claude/state/force.json` by copying the bundled `skills/force/protocol-defaults.json` from this plugin. Make the `~/.claude/state/` directory if needed (`mkdir -p`).

## Argument parsing

Strip the leading `/force` and parse what's left:

| Input | Action |
|---|---|
| `` (empty) or `status` | Read state, display. No mutation. |
| `on` | Set master=true, all components=true, preset="analysis". |
| `off` | Set master=false. Leave components untouched. |
| `F on` / `F off` (or O, R, C, E) | Toggle that one component. Master stays as-is. Set preset="custom". |
| `preset analysis` | F+O+R+C+E all true. |
| `preset brainstorm` | F=true, O=false, R=false, C=true, E=true. |
| `preset draft` | F=true, O=false, R=false, C=true, E=false. |
| `preset audit` | F=true, O=false, R=true, C=true, E=true. |
| `reset` | Restore defaults: master=true, all components=true, preset="analysis". |
| anything else | Show usage help. Do not mutate state. |

After mutation:
- Update `last_updated` to current ISO 8601 timestamp.
- Update `preset` if a preset was applied; set to `"custom"` if individual components were toggled.
- Write state file back.

## Output format

After any command (including read-only `status`), display state in this exact terse format. No filler. No prose.

```
FORCE state [~/.claude/state/force.json]
  Master: ON
  Preset: analysis
  F: ON — Forbid Flattery
  O: ON — Oppose Premise
  R: ON — Reference Sources
  C: ON — Chain-of-Thought
  E: ON — Express Uncertainty
  Updated: 2026-06-25T14:30:00Z
```

If master is OFF, still show component states but tag them as inactive:

```
FORCE state [~/.claude/state/force.json]
  Master: OFF (skill is passive)
  Preset: analysis
  F: (was ON)
  O: (was ON)
  R: (was ON)
  C: (was ON)
  E: (was ON)
  Updated: 2026-06-25T14:30:00Z
```

If the project-level state is in effect, the path in brackets should reflect that (e.g. `./.claude/state/force.json`).

## Usage help (when argument is invalid)

```
/force — toggle FORCE protocol components

Usage:
  /force                         show current state
  /force on                      enable everything
  /force off                     disable master switch
  /force {F|O|R|C|E} {on|off}    toggle one component
  /force preset {name}           apply preset
  /force reset                   restore defaults

Presets:
  analysis    F+O+R+C+E (full protocol, default)
  brainstorm  F+C+E    (no objections-first, no source gating)
  draft       F+C      (writing assistance, minimal constraints)
  audit       F+R+C+E  (skip objections, prioritize source grounding)
```

## After state change

Once the state file is updated and confirmation displayed, apply the new state to all subsequent responses in this session until further notice. Do not re-read state on every response unless explicitly asked.

## Examples

User: `/force`
Action: read state, display. No mutation.

User: `/force preset brainstorm`
Action: set F=true, O=false, R=false, C=true, E=true, preset="brainstorm", update timestamp, write file, display new state.

User: `/force O off`
Action: set components.O=false, set preset="custom", update timestamp, write file, display new state.

User: `/force xyzzy`
Action: show usage help. Do not mutate state.
