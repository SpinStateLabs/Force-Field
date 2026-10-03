# Proposal: E5 strictness throttle

**Status:** proposed, not implemented. **Date:** 2026-10-03. **Applies to:** the Enforcement Gate, E5 session-written execution (field 1.2.x).

## Problem

E5 denies a Bash command that names a file the same session wrote with a file tool, except for a short list of read-only tools. That list is a usability choice: it lets an agent read back its own file with `cat` or add it with `git add`. Some estates want the opposite trade and would accept blocking legitimate work to shrink the gate's blind spots. Today there is one Bash behaviour for everyone. PowerShell is already maximally strict, because it has no parser and every token counts.

## Proposal

One optional manifest key, read only when `session_written_exec` is `deny`:

```yaml
enforcement:
  irreversible_actions:
    session_written_exec: deny
    session_written_exec_strictness: standard   # standard | strict | paranoid
```

Default `standard`: manifests without the key behave exactly as field 1.2.2. Any other value denies with `E0` (fail-closed, like the existing `session_written_exec` check). `session_written_exec_allow[]` exemptions apply at every tier.

| Tier | What E5 checks on a Bash command | What it can over-block |
|---|---|---|
| `standard` | The read-only allowlist applies. A command word with a path separator that resolves to a session-written file is checked (1.2.2). | Nothing beyond 1.2.x. |
| `strict` | Everything in `standard`, plus: a bare command word that equals a session-written path is checked; allowlisted tools are not exempt in command forms that can themselves run a named file; the value in `NAME=value` and `--flag=value` tokens is checked as a path. | A command that both uses one of those forms and names a written file, or a written file that shares a name with a tool. |
| `paranoid` | No allowlist. Every token of every command is checked, as PowerShell is today. | Any command that names a written file, including `cat x.sh` and `git add x.sh`. |

## Prototype measurements

A throwaway prototype (not merged, not in this repository) ran the 167-case `run_e5.sh` suite at each tier:

- `standard`: 167 of 167 pass.
- `strict`: 162 pass. The 5 differences are the bare-name controls, which are meant to flip.
- `paranoid`: 158 pass. The 9 differences are those 5 plus four read-only allows (`cat x.sh`, `git add x.sh`, `ls x.sh`, `cat x.sh | grep a`).

## Rollout

- Schema: one additive optional enum under `enforcement.irreversible_actions`; `schema_version` unchanged.
- Templates and docs: a commented example and a tier table.
- `field-platform`: `field-core` rejects unknown manifest keys (`extra="forbid"`), so a manifest carrying the key validates INVALID there until the schema is re-vendored. This is the same follow-up as for the 1.2 keys.
- Ledger: each record should carry the active tier, so the gate's posture is auditable. The prototype does not do this.

## Limits

No tier is a sandbox. A tier changes which command text is matched. Implicit execution (`make`, `npm test`, git hooks), files created by Bash itself, indirection (`eval`, a variable holding a path) and a changed working directory are outside every tier (see Known limitations in the 1.2.0 CHANGELOG entry).

## Open questions

1. Two tiers or three? `paranoid` is the only tier with no allowlist at all.
2. Should `standard` absorb any part of what `strict` adds, where doing so blocks no legitimate work? A throttle should trade usability for safety, not hold back fixes.
3. Should the active tier be written into every ledger record?
