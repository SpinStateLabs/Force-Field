---
description: Generate, validate, and audit FIELD governance manifests for agentic AI. Toggle the FIELD skill, bootstrap a manifest, or run a compliance check.
---

# /field — slash command

Handles all `/field *` invocations. Parse the argument, act, confirm. Two things are managed here:
the **skill state** (`field.json`) and the working **manifest** (`field-manifest.yaml`).

## State location

Skill state file (precedence order):

1. `./.claude/state/field.json` (project-level, if it exists in the current working directory tree)
2. `~/.claude/state/field.json` (user-level, always falls back here)

**Always write back to the same file that was read.** Never auto-promote project state to user state.

**Bootstrap**: if neither state file exists, create `~/.claude/state/field.json` by copying the
bundled `skills/field/field-defaults.json` from this plugin. Make `~/.claude/state/` if needed
(`mkdir -p`).

## Manifest location

1. `./field-manifest.yaml` (project-level, primary — one manifest per agent)
2. `~/.claude/state/field-manifest-template.yaml` (user default template, optional)

Bundled bootstrap templates live in this plugin at `skills/field/templates/`.

## Argument parsing

Strip the leading `/field` and parse what's left:

| Input | Action |
|---|---|
| `` (empty) or `status` | Read skill state + report the working manifest (or note none). No mutation. |
| `on` | Set `master=true`. Skill assists proactively. |
| `off` | Set `master=false`. Skill becomes passive (explicit `/field` only). |
| `init` | Create `./field-manifest.yaml` from `preferred_template`. Refuse to overwrite an existing manifest without confirmation. |
| `init <template>` | Same, using `default` \| `financial-agent` \| `read-only-agent` \| `client-facing-agent`. |
| `validate` | Load `./field-manifest.yaml`, check against `skills/field/manifest-schema.json`, output the validation block. No mutation. |
| `assess` | Walk the five letters (F→I→E→L→D) interactively, one at a time, pushing for specifics. Offer to write results into the manifest. |
| `audit` | Output the audit block for `./field-manifest.yaml`. Update `last_audit_at` in state. |
| `export json` / `export yaml` | Print the current manifest in the requested format. No mutation of the file. |
| `template <name>` | Set `preferred_template` in state to a valid template name. |
| `reset` | Restore skill defaults: `master=true`, `preferred_template=default`, clear `working_manifest_path`. |
| `kill` | Trip the Enforcement Gate kill switch: create the sentinel file. Every gated tool call is denied until a human removes it. |
| `resume` | Report the sentinel path and the shell command a human must run to remove it; confirm once it is gone. The agent cannot remove it (E1 denies the call). No mutation. |
| `verify` | Run `hooks/verify-ledger.py` against the ledger and print the result. No mutation. |
| anything else | Show usage help. Do not mutate anything. |

After any state mutation:
- Update `last_updated` to the current ISO 8601 timestamp.
- After `audit`, also update `last_audit_at`.
- Write the state file back to the same path it was read from.

## `init` behavior (detail)

1. Resolve the template: the explicit arg, else `preferred_template` from state.
2. Read the bundled `skills/field/templates/field-manifest-<template>.yaml`.
3. If `./field-manifest.yaml` already exists, STOP and ask before overwriting.
4. Write it to `./field-manifest.yaml`, set `working_manifest_path` in state.
5. Walk the user through the five letters (F→I→E→L→D), replacing every `REPLACE-ME`. Do not accept
   vague answers — push for the specific principal, kill switch endpoint, ledger store, delegation
   grantor and expiry. See `skills/field/framework.md`.

## `validate` behavior (detail)

Check the manifest against `skills/field/manifest-schema.json` AND the critical-gap rules in
`skills/field/framework.md`. A manifest is **INVALID** if any of these hold:

- any of `federated` / `identity` / `enforcement` / `ledger` / `delegation` is missing
- `identity.principal` is absent
- `enforcement.kill_switch` is absent or missing `endpoint`/`method`
- `ledger.cryptographic_seal` is not `true`, or `seal_algorithm` is `none`/absent
- `delegation.granted_by` is absent

Unresolved `REPLACE-ME` values are **warnings**, not blocking. Output the validation block exactly
as specified in `skills/field/SKILL.md`.

## Output format (skill state)

After `status`, `on`, `off`, `template`, `reset` — display state in this exact terse format:

```
FIELD state [~/.claude/state/field.json]
  Master: ON
  Preferred template: default
  Working manifest: ./field-manifest.yaml
  Last audit: never
  Updated: 2026-06-25T14:30:00Z
```

If master is OFF, tag it:

```
FIELD state [~/.claude/state/field.json]
  Master: OFF (skill is passive)
  Preferred template: default
  Working manifest: none
  Last audit: never
  Updated: 2026-06-25T14:30:00Z
```

If the project-level state is in effect, the path in brackets reflects that
(`./.claude/state/field.json`).

## Usage help (when argument is invalid)

```
/field — FIELD governance for agentic AI

Usage:
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

Templates:
  default             baseline general use
  financial-agent     FP&A / audit-adjacent (7-yr ledger, spend cap)
  read-only-agent     retrieval only, zero write scope
  client-facing-agent draft-only outbound, human review, no autonomous send

The five letters: Federated · Identity · Enforcement · Ledger · Delegation
```

## After state change

Once state is updated and confirmation displayed, apply the new posture to subsequent responses in
this session. Do not re-read state on every response unless explicitly asked.

## Examples

User: `/field`
Action: read state, report working manifest. No mutation.

User: `/field init financial-agent`
Action: copy the financial-agent template to `./field-manifest.yaml`, set `working_manifest_path`,
then walk F→I→E→L→D to fill placeholders.

User: `/field validate`
Action: load `./field-manifest.yaml`, check against schema + critical-gap rules, print the
validation block. No mutation.

User: `/field xyzzy`
Action: show usage help. Do not mutate anything.

## Enforcement Gate (v1.1) — `kill`, `resume`, `verify`, and the `status` line

The plugin ships a Claude Code `PreToolUse` hook (`hooks/hooks.json` → `hooks/field-gate.py`) that
reads `./field-manifest.yaml` and enforces E1 kill switch, E2 protected paths, E3 irreversible
actions, E4 tool-call budget, and writes a sha-256 hash-chained ledger (L). It is active whenever a
manifest exists in the project directory. Conventions (full detail in `skills/field/framework.md`):

- Sentinel file: `enforcement.kill_switch.endpoint` when `method` is `file`; otherwise
  `.claude/state/KILL`. Relative paths resolve against the manifest directory.
- Ledger file: `ledger.store` when path-like (`file://…`, a path containing a separator, `~/…`, or
  a bare `*.jsonl`); otherwise `.claude/state/field-ledger.jsonl`.
- Budget: the `enforcement.rate_limits` entry `{action: tool_call, period: session}`.
- Gated tools: Bash, Edit, Write, MultiEdit, NotebookEdit. Read, Glob and Grep are not gated.

### `kill` behavior (detail)

1. Load `./field-manifest.yaml`. If it does not exist, report that the gate is not active in this
   directory and stop.
2. Resolve the sentinel path (rule above).
3. Create it (`mkdir -p` the parent directory, then create the empty file) and confirm:

```
FIELD kill switch TRIPPED — <path>
  Every Bash / Edit / Write / MultiEdit / NotebookEdit call is now denied (E1)
  until a human removes the file. Lift it with:  rm <path>
```

4. Do not attempt further gated tool calls in this session.

### `resume` behavior (detail)

1. Resolve the sentinel path. Check whether it exists with Glob or Read (both are un-gated).
2. If it exists, the agent cannot remove it — E1 denies every gated call, including the removal.
   Print, and do nothing else:

```
FIELD kill switch is TRIPPED — <path>
  Lift it outside this session:  rm <path>        (PowerShell: Remove-Item <path>)
  Then run /field resume again to confirm.
```

3. If it does not exist: `FIELD kill switch is CLEAR — gate enforcing normally.`
4. No mutation in either case.

### `verify` behavior (detail)

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/verify-ledger.py"` with no arguments — it resolves
   the ledger exactly as the gate does.
2. Print its output verbatim: `LEDGER INTACT (<n> records, <path>)`, or `LEDGER TAMPERED` with the
   offending line numbers, or `LEDGER MISSING: <path>`.
3. State once: the chain is tamper-evident, not tamper-proof — anyone with write access to the
   ledger file can rewrite it.
4. No mutation.

### `status` addition

After the state block, append one line:

```
  Gate: armed (manifest ./field-manifest.yaml · sentinel <path> absent|PRESENT · ledger <path>)
```

or `  Gate: not armed (no ./field-manifest.yaml in this directory)`.

### Gate interaction with `init` and `assess`

Once `./field-manifest.yaml` exists the gate treats it as a protected path (E2): the agent cannot
edit it in place, by design — governance changes are made by the human, outside the session. The
initial `init` write succeeds because no manifest exists yet. When walking F→I→E→L→D after `init`,
or offering to write `assess` results, write the completed manifest to
`./field-manifest.draft.yaml` (not protected) and tell the human to move it into place:
`mv field-manifest.draft.yaml field-manifest.yaml`.
