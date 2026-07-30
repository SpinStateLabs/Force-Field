# FIELD Skill — Install Guide

Three ways to install. Pick the one that matches your stack.

| Method | Best for | Effort |
|---|---|---|
| **A. Claude Code `/plugin install`** | Anyone with Claude Code who wants FIELD running | 30 seconds |
| **B. Bash installer (`install.sh`)** | macOS / Linux / WSL, or air-gapped | 1 minute |
| **C. PowerShell installer (`install.ps1`)** | Native Windows, or air-gapped | 1 minute |

All three land the skill at `~/.claude/skills/field/`, the command at `~/.claude/commands/field.md`,
and seed skill state at `~/.claude/state/field.json`. **State is create-only** — reinstalling never
overwrites your toggles or last-audit timestamp.

Per-agent **manifests** are separate: `/field init` writes a `./field-manifest.yaml` into whatever
project directory you run it from. One manifest per agent.

---

## Method A — Claude Code native install (recommended)

FIELD ships in the Force-Field marketplace alongside FORCE:

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install field@force-field
```

Then:

```
/reload-plugins
/field
```

That's the whole install. Install FORCE too if you haven't — FIELD wraps it:

```
/plugin install force@force-field
```

---

## Method B — Bash installer (macOS / Linux / WSL)

From this plugin directory (`plugins/field/`):

```bash
# User-level (default, all projects)
./install.sh

# Project-level (just this directory)
./install.sh project
```

Skill and command files refresh on every run; `~/.claude/state/field.json` is preserved if present.

---

## Method C — PowerShell installer (Windows)

From this plugin directory (`plugins/field/`):

```powershell
# User-level (default)
.\install.ps1

# Project-level
.\install.ps1 -Level project
```

If PowerShell blocks the script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# or one-time:
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

---

## Verifying any install worked

```
/field
```

Expected output:

```
FIELD state [~/.claude/state/field.json]
  Master: ON
  Preferred template: default
  Working manifest: none
  Last audit: never
  Updated: 2026-07-29T00:00:00Z
```

If you see this, the skill is installed and active. If `/field` does nothing:
- Method A: run `/reload-plugins`, then restart Claude Code if needed.
- Method B/C: confirm `~/.claude/skills/field/SKILL.md` and `~/.claude/commands/field.md` exist.

---

## Deploying FIELD to an agent

The skill is the tool; the **manifest** is what you attach to each agent:

```
cd path/to/your-agent
/field init financial-agent     # writes ./field-manifest.yaml from a template
                                # then walk F→I→E→L→D to fill every REPLACE-ME
/field validate                 # VALID / INVALID + gaps
/field audit                    # audit-ready summary before deploy
```

Commit `field-manifest.yaml` alongside the agent it governs. One manifest per agent.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `/field` does nothing | `/reload-plugins`; if that fails, restart Claude Code. |
| State not updating after a toggle | Check permissions on `~/.claude/state/`. The command confirms state after every change — verify it matches. |
| Plugin not found in marketplace | `/plugin marketplace update force-field` to refresh the cache. |
| `install.ps1` blocked | See Method C execution-policy note above. |
| Conflict with another `field` skill | Plugin skills are namespaced `field:field`, so they won't collide with a manual install. Prefer one install method. |

---

*Spin State Labs · FIELD Skill v1.0 · spinstatelabs.ca/field*
