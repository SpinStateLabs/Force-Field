---
description: Run the plugin-agent (Force-Field marketplace maintenance under FORCE audit + FIELD) — status, release, check, or report.
argument-hint: "status | check | report | release <force|field|force-field> <patch|minor|major> \"<summary>\""
---

Delegate to the `plugin-agent` subagent with the request below. It runs under the Force-Field Protocol:
FORCE preset `audit` for its output, and the FIELD manifest `field-manifest.yaml` (Enforcement Gate) for its actions.

Request: `$ARGUMENTS`

Subcommands:

| Subcommand | Does | Stops before |
|---|---|---|
| `status` (default when empty) | Job 2 — directory status table | any portal action |
| `check` | Jobs 3 + 4 — compliance and README/code drift | any edit |
| `report` | Jobs 2 + 3 + 4 in one table, plus the open-items list | any edit |
| `release <plugin> <patch\|minor\|major> "<summary>"` | Job 1 — bump, CHANGELOG, validate, local commit | `git push` |

Before running, check whether the gate is armed: `field-manifest.yaml` exists at the repo root and the `field`
plugin is installed. If it is not armed, say so in the first line of the output and carry on in report-only mode:
no edits, no commits.

End every run with one line: `Next human action: <what Don must do, or "none">`.
