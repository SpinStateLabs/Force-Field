---
name: field
description: Spin State Labs' FIELD governance framework for agentic AI. Generate, validate, and audit FIELD governance manifests. Use when designing a new autonomous agent, when defining runtime enforcement/kill switches/spend caps for an agent, when clarifying agent identity or delegation chains, when scoping multi-agent federation, or when the user invokes /field. Use also when preparing an agent deployment for audit, when reviewing an existing agent for governance gaps, or when composing FIELD with the FORCE runtime protocol.
---

# FIELD Governance Skill

Spin State Labs' governance framework for agentic AI systems. Where FORCE constrains what an AI says (runtime), FIELD constrains how an AI is deployed and accountable (governance).

## When this skill activates

Apply this skill when ANY of the following is true:

1. The user invokes `/field` (any subcommand)
2. The user is designing, deploying, or auditing an autonomous agent
3. The user needs to define kill switches, spend caps, escalation triggers, or other runtime enforcement mechanisms
4. The user is scoping identity/attribution — who owns an agent, whose interests it serves, what jurisdiction governs it
5. The user is establishing delegation — what actions have been authorized, by whom, in what scope
6. The user is designing federation between multiple agents from different organizations
7. The user is preparing an agent deployment for audit or compliance review

Do NOT apply this skill for: general AI questions unrelated to agent deployment, purely prompt-engineering questions (that's FORCE territory), or conversations about non-agentic AI use.

## The five letters

- **F — Federation.** Multi-agent trust protocols across ownership boundaries. Trusted peers, contract semantics, boundary controls.
- **I — Identity.** Attribution — principal, org, jurisdiction, data scope.
- **E — Enforcement.** Runtime harnessing — kill switches, spend caps, escalation triggers, irreversible action rules.
- **L — Ledger.** Immutable audit trail. Retention, cryptographic sealing, what gets logged.
- **D — Delegation.** Authorization chain — granted_by, scope, expiry, revocation.

## Manifest location (CRITICAL)

FIELD manifests live at:

```
./field-manifest.yaml    (project-level, primary — one manifest per agent/project)
```

Or, for user-level defaults:

```
~/.claude/state/field-manifest-template.yaml
```

**On first invocation**, if `./field-manifest.yaml` does NOT exist in the working directory:
1. Look for `~/.claude/state/field-manifest-template.yaml` as a user template
2. If neither exists, offer to run `/field init` to bootstrap from the plugin's `templates/field-manifest-default.yaml`

## Handling slash commands

When the user types `/field` followed by any argument, follow the logic in `commands/field.md` (sibling to this skill). Command surface:

| Command | Effect |
|---|---|
| `/field` or `/field status` | Show current manifest at ./field-manifest.yaml (or note it doesn't exist) |
| `/field init` | Create a new field-manifest.yaml in the working directory from the default template |
| `/field init <template>` | Use a specific template (e.g. `financial-agent`, `read-only-agent`, `client-facing-agent`) |
| `/field validate` | Check current manifest against schema. Report gaps. |
| `/field assess` | Walk through FIELD compliance evaluation, five letters at a time |
| `/field audit` | Generate an audit-ready summary of the manifest for external review |
| `/field export` | Export the manifest as JSON for downstream systems |

## When generating or editing manifests

Every FIELD manifest MUST include all five sections: `federation`, `identity`, `enforcement`, `ledger`, `delegation`. A manifest missing any section is invalid — flag it and offer to fill.

Prefer explicit over implicit:
- Empty allowed_peers list means "isolated agent, no federation" — don't leave the field undeclared
- Missing kill_switch is a critical gap — refuse to mark valid without one
- Missing delegation is a sovereignty violation — refuse to mark valid without an authorization chain

When walking a user through `/field init`, ask about each letter in order (F → I → E → L → D). Do not accept vague answers ("the usual defaults"). Push for specifics: which peers, which principal, which kill switch endpoint, which ledger store, which delegation expiry.

## Composition with FORCE

Every FIELD-governed agent SHOULD apply the FORCE runtime protocol during operation. The manifest can declare this explicitly:

```yaml
runtime_protocol:
  name: FORCE
  version: 1.0
  preset: analysis  # or brainstorm/draft/audit
```

If FORCE is missing from the manifest, note it but don't refuse. Some agents (highly constrained, single-purpose bots) may not need FORCE. Flag the absence for review.

## Audit output format

When the user runs `/field audit`, output in this exact structure:

```
FIELD manifest audit — <path>
  Generated: <ISO timestamp>
  Agent: <identity.principal>
  Jurisdiction: <identity.jurisdiction>

  F — Federation:  <PASS/GAP>  — <one line summary>
  I — Identity:    <PASS/GAP>  — <one line summary>
  E — Enforcement: <PASS/GAP>  — <one line summary>
  L — Ledger:      <PASS/GAP>  — <one line summary>
  D — Delegation:  <PASS/GAP>  — <one line summary>

  FORCE runtime: <enabled/disabled/absent>

  Gaps requiring resolution before deploy:
    - <bulleted list, or "None">

  Recommended reviewers:
    - Principal: <identity.principal>
    - Compliance / audit: <if jurisdiction requires>
```

Be terse. The user is auditing, not reading prose.

## Limitations to flag if asked

- FIELD v1.0 is a **manifest tool**, not a runtime enforcer. It generates and validates the governance spec. Actual enforcement (kill switches firing, spend caps triggering, ledger writes) requires additional infrastructure the user builds around the manifest.
- Certification is not automated. `/field audit` produces an audit-ready report; independent verification is a separate service.
- Cryptographic sealing of the ledger is declared in the manifest but not implemented by this plugin — the ledger store the user configures must handle it.
- Composition with FORCE is asserted in v1.0 but not runtime-wired. If FORCE is declared in the manifest, the actual application of FORCE protocol at runtime is separate infrastructure.

For the full framework document, methodology, and reference architectures, see [spinstatelabs.ca/field](https://spinstatelabs.ca/field).

## Companion files in this plugin

- `skills/field/framework.md` — The five-letter framework in detail.
- `skills/field/manifest-schema.json` — JSON Schema for FIELD manifests. Use this for validation.
- `templates/field-manifest-default.yaml` — Baseline manifest template.
- `templates/field-manifest-financial-agent.yaml` — Preset for FP&A / financial agents.
- `templates/field-manifest-read-only-agent.yaml` — Preset for retrieval/read-only agents.
- `commands/field.md` — Slash command handling logic.
