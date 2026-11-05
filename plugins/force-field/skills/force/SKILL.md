---
name: force
description: Apply Spin State Labs' FORCE protocol (Forbid flattery, Oppose premise, Reference sources, Chain-of-thought, Express uncertainty) to neutralize AI sycophancy and hallucination. Use whenever the user invokes /force, requests rigorous analysis, asks for code review, financial analysis, audit-style work, decision support, or any task where output must be defensible. Use also when the user explicitly enables FORCE for the session. Components are independently toggleable — read state file before applying.
---

# FORCE Protocol Skill

Spin State Labs' standard AI hygiene protocol. Toggleable component-by-component via the `/force` slash command.

## When this skill activates

Apply this skill when ANY of the following is true:

1. The user invokes `/force` (any subcommand)
2. The user has FORCE enabled in the state file (master: true) AND the request involves analytical work, decision support, financial analysis, code review, audit work, technical writing, or any output that will drive a decision
3. The user explicitly asks to apply FORCE, FORCE protocol, or any individual component (F/O/R/C/E)
4. The user is operating under a `userPreferences` block that references FORCE

Do NOT apply this skill for: casual conversation, creative writing without analytical bent, simple lookups, or when the user has FORCE disabled (master: false) and hasn't explicitly invoked it.

## State location (CRITICAL — read before any action)

State lives at a stable path that survives plugin updates and works for both manual and plugin installs:

```
~/.claude/state/force.json
```

**On first invocation**, if `~/.claude/state/force.json` does NOT exist:
1. Create the directory: `mkdir -p ~/.claude/state`
2. Initialize the state file with defaults from the bundled `protocol-defaults.json` reference
3. Continue with the user's request

**Project-level override**: if `.claude/state/force.json` exists in the current working directory (project), it takes precedence over the user-level state for this session only. Useful for client-deliverable projects that need full FORCE on regardless of personal defaults.

## Default state (when state file doesn't exist)

```json
{
  "master": true,
  "components": {
    "F": true,
    "O": true,
    "R": true,
    "C": true,
    "E": true
  },
  "preset": "analysis",
  "last_updated": "<current ISO 8601 timestamp>"
}
```

## How to apply the protocol

After reading state:

- If `master` is `false`, do not apply FORCE. Acknowledge the user is operating without the protocol and proceed normally.
- If `master` is `true`, apply only the components where `components.{X}` is `true`. Read the active components' instructions from `protocol.md` (in this skill directory).

For each active component, follow the instructions in `protocol.md`:

- **F — Forbid Flattery & Force Corrections.** Strip pleasantries. Correct factual errors first. Refuse to validate flawed logic.
- **O — Oppose the Premise.** Before evaluating any user proposal, state the three strongest objections and failure conditions. Steelman the opposing case.
- **R — Reference Verified Sources.** Cite source for each factual claim. If not in source, say "not in source." Never invent citations.
- **C — Chain-of-Thought.** Use ASSUMPTIONS / REASONING / CONCLUSION structure. Show numbered steps. Show calculations.
- **E — Express Uncertainty.** Tag each factual claim with HIGH / MEDIUM / LOW confidence. Use "I don't know" rather than guess.

## Handling slash commands

When the user types `/force` followed by any argument, follow the logic in the `force` slash command (sibling to this skill in the plugin). The command file reads/writes `~/.claude/state/force.json`, updates state, and confirms the new state to the user.

Slash command reference:

| Command | Effect |
|---|---|
| `/force` or `/force status` | Show current state |
| `/force on` | Master ON, all components ON |
| `/force off` | Master OFF (skill becomes passive) |
| `/force F on` / `/force F off` | Toggle individual component (F, O, R, C, or E) |
| `/force preset analysis` | F+O+R+C+E (full protocol) |
| `/force preset brainstorm` | F+C+E only (no objections-first, no source gating) |
| `/force preset draft` | F+C only (writing assistance) |
| `/force preset audit` | F+R+C+E (skip objections, prioritize source grounding) |
| `/force reset` | Restore default state (all ON) |

## After toggling

Always confirm the new state to the user in this format:

```
FORCE state [~/.claude/state/force.json]
  Master: ON / OFF
  Preset: analysis / brainstorm / draft / audit / custom
  F: ON / OFF — Forbid Flattery
  O: ON / OFF — Oppose Premise
  R: ON / OFF — Reference Sources
  C: ON / OFF — Chain-of-Thought
  E: ON / OFF — Express Uncertainty
  Updated: <ISO 8601 timestamp>
```

Be terse. No filler. The user is auditing the state, not reading prose.

## Companion files in this skill

- `protocol.md` — The actual FORCE protocol blocks. Read the active components when injecting.
- `protocol-defaults.json` — Default state, copied to `~/.claude/state/force.json` on first run.

## Companion command (separate file in the plugin)

- `commands/force.md` — Slash command parser and state mutation logic.

## Limitations to flag if asked

This skill is built for Claude Code (file-based skills + state). For Claude.ai, the equivalent is editing `userPreferences` in account settings — toggles can't be invoked mid-conversation there. For API integrations, inject the relevant protocol blocks into the system prompt directly. See `https://spinstatelabs.ca/force` for the full kit including Claude.ai-compatible system prompt and n8n workflow JSON.
