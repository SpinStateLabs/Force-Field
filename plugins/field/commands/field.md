---
description: FIELD governance manifest tools. Initialize, validate, assess, and audit governance manifests for agentic AI systems.
---

# /field — slash command

Handles all `/field *` invocations. Parse the argument, take the appropriate action, confirm.

## Manifest location

Read from and write to (in order of precedence):

1. `./field-manifest.yaml` in the current working directory (project-level, primary)
2. `~/.claude/state/field-manifest-template.yaml` (user-level template, if project doesn't exist and user is asking about defaults)

Always operate on the project-level file unless the user explicitly specifies a template action.

## Argument parsing

Strip the leading `/field` and parse what's left:

| Input | Action |
|---|---|
| `` (empty) or `status` | Display current manifest. If missing, say so and suggest `/field init`. |
| `init` | Copy `templates/field-manifest-default.yaml` from plugin to `./field-manifest.yaml`. Walk user through filling `<TODO>` markers. |
| `init default` | Same as `init` |
| `init financial-agent` | Copy `templates/field-manifest-financial-agent.yaml` |
| `init read-only-agent` | Copy `templates/field-manifest-read-only-agent.yaml` |
| `init client-facing-agent` | Copy `templates/field-manifest-client-facing-agent.yaml` |
| `validate` | Check current manifest against `skills/field/manifest-schema.json`. Report all violations. |
| `assess` | Walk through five-letter compliance evaluation interactively |
| `audit` | Generate audit-ready summary of current manifest |
| `export` | Convert current manifest to JSON and display |
| `help` | Show usage |
| anything else | Show usage |

## `/field init` workflow

1. Check if `./field-manifest.yaml` exists.
2. If yes, ask user if they want to overwrite. Default: no.
3. Copy the requested template to `./field-manifest.yaml`.
4. Read the file and identify all `<TODO ...>` markers.
5. Walk the user through filling them in, in this order: metadata → identity → federation → enforcement → ledger → delegation.
6. After each section, offer to save progress.
7. On completion, run `/field validate` automatically.

Be terse in the walkthrough. One question at a time. Don't lecture — the user knows FIELD if they're using this plugin.

## `/field validate` output format

```
FIELD manifest validation — ./field-manifest.yaml
  Schema: field.spinstatelabs.ca/v1

  metadata:      OK
  federation:    OK
  identity:      GAP — missing required field: jurisdiction
  enforcement:   OK
  ledger:        WARNING — retention_days=90 is below recommended 365
  delegation:    GAP — scope array is empty; agent has no authorized actions

  Validation: FAILED
  Gaps: 2
  Warnings: 1

  Cannot deploy without resolving gaps.
```

If validation passes:

```
FIELD manifest validation — ./field-manifest.yaml
  All sections OK. Manifest is deployable.
```

## `/field assess` workflow

Walk through the five letters, ask targeted questions, evaluate responses.

For each letter:
1. State the letter name and one-sentence purpose.
2. Show what the manifest currently declares for that letter.
3. Ask one probing question. Examples:
   - **F**: "Which peers can this agent talk to that you haven't listed in `allowed_peers`?"
   - **I**: "If a regulator asks who's responsible for this agent's decisions, who do you name?"
   - **E**: "Walk me through what happens when the spend cap is hit."
   - **L**: "How long after an incident could you produce a full action log?"
   - **D**: "Show me the signed authorization that granted this scope."
4. If the response reveals a gap, mark the letter with GAP; if adequate, PASS.

After all five, produce the same audit summary format as `/field audit`.

## `/field audit` output format

Exact structure — the user is preparing for external review, not reading prose.

```
FIELD manifest audit — ./field-manifest.yaml
  Generated: 2026-06-25T14:30:00Z
  Agent: fp-analyst-client-alpha
  Principal: don@spinstatelabs.ca
  Jurisdiction: CA-ON

  F — Federation:  PASS  — 3 allowed peers, mTLS verification, no PII crossing
  I — Identity:    PASS  — Attribution complete, jurisdiction declared
  E — Enforcement: PASS  — Kill switch wired, $250/mo cap, 3 escalation triggers
  L — Ledger:      PASS  — s3 with 2555-day retention, cryptographic seal enabled
  D — Delegation:  PASS  — Scope declared, expiry 2026-12-31, chain traceable

  Runtime protocol: FORCE v1.0 preset=audit

  Gaps requiring resolution before deploy:
    None

  Recommended reviewers:
    - Principal: don@spinstatelabs.ca
    - Compliance: CFO of client (per delegation chain)
```

If any letter has GAPS, list them under "Gaps requiring resolution before deploy" — bullet points, one per gap, specific and actionable.

## `/field export` behavior

Convert the YAML manifest to JSON. Display it. Do not write to disk unless the user explicitly asks (e.g., `/field export > manifest.json`).

## `/field help` output

```
/field — FIELD governance manifest tools

Usage:
  /field                            show current manifest status
  /field init [template]            create a new manifest from a template
                                    templates: default | financial-agent
                                               | read-only-agent | client-facing-agent
  /field validate                   check manifest against schema
  /field assess                     walk through five-letter compliance evaluation
  /field audit                      generate audit-ready summary
  /field export                     convert manifest to JSON

FIELD constrains:
  F  Federation    — trust protocols across agent boundaries
  I  Identity      — who owns the agent, whose interests it represents
  E  Enforcement   — runtime harnessing (kill switches, spend caps, escalation)
  L  Ledger        — immutable audit trail
  D  Delegation    — authorization chain from human to agent

Sibling of FORCE (runtime prompt protocol). See spinstatelabs.ca/field for full framework.
```

## Never fabricate

If the manifest is incomplete or the answer to a validation question requires information not in the manifest, say so. Never guess a jurisdiction, an expiry date, a kill switch endpoint, or a delegation chain. Half a governance manifest is worse than none.

Operating under FORCE. If in doubt, tag confidence LOW and refuse to commit.
