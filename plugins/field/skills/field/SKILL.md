---
name: field
description: Apply Spin State Labs' FIELD governance framework for agentic AI. Generate, validate, and audit FIELD governance manifests (Federated, Identity, Enforcement, Ledger, Delegation). Use whenever the user invokes /field, is designing a new autonomous agent, needs to define kill switches or spend caps or escalation triggers, scopes identity or delegation chains, is preparing an agent deployment for audit, or is composing FIELD with the FORCE runtime protocol. FIELD is design-time governance; FORCE is runtime prompt hygiene. Read state before applying.
---

# FIELD Governance Skill

Spin State Labs' governance framework for agentic AI systems. Where FORCE constrains what an AI *says* (runtime), FIELD constrains how an AI is *deployed and accountable* (design-time). Toggleable via the `/field` slash command.

## When this skill activates

Apply this skill when ANY of the following is true:

1. The user invokes `/field` (any subcommand)
2. The user is designing, deploying, or auditing an autonomous agent
3. The user needs to define kill switches, spend caps, escalation triggers, or other runtime enforcement mechanisms
4. The user is scoping identity/attribution — who owns an agent, whose interests it serves, what jurisdiction governs it
5. The user is establishing delegation — what actions have been authorized, by whom, in what scope, with what expiry
6. The user is designing federated trust between multiple agents from different organizations
7. The user is preparing an agent deployment for audit or compliance review
8. The user asks about any of Federated / Identity / Enforcement / Ledger / Delegation in an agent context

Do NOT apply this skill for: general AI questions unrelated to agent deployment, purely prompt-engineering questions (that's FORCE territory), conversations about non-agentic AI use, or single-shot LLM calls without persistent state.

## State location (CRITICAL — read before any action)

State lives at a stable path that survives plugin updates and works for both marketplace and manual installs:

```
~/.claude/state/field.json
```

**On first invocation**, if `~/.claude/state/field.json` does NOT exist:
1. Create the directory: `mkdir -p ~/.claude/state`
2. Initialize the state file from the bundled `field-defaults.json` (in this skill directory)
3. Continue with the user's request

**Project-level override**: if `.claude/state/field.json` exists in the current working directory, it takes precedence over user-level state for this session only. Useful for projects that require a specific FIELD posture regardless of personal defaults.

If `master` is `false`, do not proactively apply FIELD; act only on explicit `/field` invocations. Acknowledge the user is operating without automatic FIELD assistance and proceed normally.

If `master` is `true`, use `preferred_template` when bootstrapping new manifests and apply the audit-ready output format for review requests.

## The five letters

- **F — Federated.** Multi-agent trust protocols across ownership boundaries. Which peers this agent may talk to. What contracts govern the exchange. `isolated: true` (empty peer list) is valid — it declares an *isolated* agent explicitly.
- **I — Identity.** Attribution. Principal (whose agent is this?), org, jurisdiction, data scope. An agent without a declared principal is a sovereignty violation.
- **E — Enforcement.** Runtime harnessing. Kill switches, spend caps, escalation triggers, rules for irreversible actions. An agent without a kill switch is a critical gap — refuse to mark valid.
- **L — Ledger.** Cryptographic immutable audit trail. `cryptographic_seal: true` is baseline, not optional. Retention period, what gets logged, seal algorithm.
- **D — Delegation.** Authorization chain. `granted_by`, `scope`, `expiry`, `revocation`. An agent without an authorization chain has no legitimate authority.

Full operational detail for each letter is in `framework.md` (this skill directory). Read it when generating, validating, or auditing a manifest.

## Manifest location (CRITICAL)

FIELD manifests live at:

```
./field-manifest.yaml                              (project-level, primary — one manifest per agent)
~/.claude/state/field-manifest-template.yaml       (user-level default template, optional)
```

Project-level wins over user-level.

**On first invocation**, if `./field-manifest.yaml` does NOT exist in the working directory:
1. Look for `~/.claude/state/field-manifest-template.yaml` as a user default
2. If neither exists, offer to run `/field init` to bootstrap from the preferred template in `field.json`

Bundled bootstrap templates ship inside this skill at `templates/`.

## Handling slash commands

When the user types `/field` followed by any argument, follow `commands/field.md` in this plugin. Command surface:

| Command | Effect |
|---|---|
| `/field` or `/field status` | Show current manifest at ./field-manifest.yaml (or note it doesn't exist) and current skill state |
| `/field on` | Master ON — skill will proactively assist with agent design |
| `/field off` | Master OFF — skill only responds to explicit invocation |
| `/field init` | Create a new field-manifest.yaml in cwd from the preferred template |
| `/field init <template>` | Use a specific template: `default`, `financial-agent`, `read-only-agent`, `client-facing-agent` |
| `/field validate` | Check current manifest against `manifest-schema.json`. Report gaps. |
| `/field assess` | Walk through FIELD compliance evaluation, five letters at a time |
| `/field audit` | Generate an audit-ready summary of the manifest for external review |
| `/field export [json\|yaml]` | Export the manifest in the requested format |
| `/field template <name>` | Set the preferred template for future `/field init` calls |
| `/field reset` | Restore skill defaults (master ON, preferred_template=default) |

## After toggling

Always confirm the new state to the user in this format:

```
FIELD state [~/.claude/state/field.json]
  Master: ON / OFF
  Preferred template: <default | financial-agent | read-only-agent | client-facing-agent>
  Working manifest: <path or "none">
  Last audit: <ISO timestamp or "never">
  Updated: <ISO 8601 timestamp>
```

Be terse. No filler. The user is auditing the state, not reading prose.

## When generating or editing manifests

Every FIELD manifest MUST include `schema_version`, an `agent` block, and all five sections: `federated`, `identity`, `enforcement`, `ledger`, `delegation`. A manifest missing any is invalid — flag it and offer to fill.

Prefer explicit over implicit:
- `federated.isolated: true` with an empty `allowed_peers` means "isolated agent, no federated peers" — don't leave it undeclared. If `isolated: false`, `allowed_peers` must be non-empty.
- Missing `enforcement.kill_switch` is a critical gap — refuse to mark valid without one.
- Missing `delegation.granted_by` is a sovereignty violation — refuse to mark valid without an authorization chain.
- `ledger.cryptographic_seal` MUST be `true` — the schema treats it as a `const`. `"none"` is not a valid `seal_algorithm`.

When walking a user through `/field init`, ask about each letter in order (F → I → E → L → D). Do not accept vague answers ("the usual defaults"). Push for specifics: which peers, which principal, which kill switch endpoint, which ledger store, which delegation expiry. Values left as `REPLACE-ME` are structurally valid but MUST be flagged as unresolved before deploy.

## Composition with FORCE

Every FIELD-governed agent SHOULD apply the FORCE runtime protocol during operation. The manifest declares this:

```yaml
runtime_protocol:
  name: FORCE
  version: "1.0"
  preset: analysis   # or brainstorm / draft / audit
```

Default preset is `analysis` (all five FORCE letters active). If FORCE is missing from the manifest, note it but don't refuse — some highly constrained single-purpose agents may not need it. Flag the absence for review.

FIELD wraps FORCE. Runtime and design-time compose; they never conflict.

## Validation output format

When the user runs `/field validate`, output in this exact structure:

```
FIELD manifest validation — <path>
  Schema: field.spinstatelabs.ca/v1
  Status: VALID / VALID_WITH_WARNINGS / INVALID

  Required sections present:
    federated:   [✓/✗]
    identity:    [✓/✗]
    enforcement: [✓/✗]
    ledger:      [✓/✗]
    delegation:  [✓/✗]

  Critical gaps (blocking):
    - <bulleted list, or "None">

  Warnings (non-blocking):
    - <unresolved REPLACE-ME values, missing runtime_protocol, near-term expiry, etc. — or "None">

  Runtime protocol: <FORCE/absent> — <preset if declared>
```

## Audit output format

When the user runs `/field audit`, output in this exact structure:

```
FIELD manifest audit — <path>
  Generated: <ISO timestamp>
  Agent: <agent.name> (principal: <identity.principal>)
  Jurisdiction: <identity.jurisdiction joined>
  Ledger retention: <ledger.retention_days> days
  Cryptographic seal: <ledger.cryptographic_seal> (<ledger.seal_algorithm>)

  F — Federated:   <PASS/GAP>  — <one line summary>
  I — Identity:    <PASS/GAP>  — <one line summary>
  E — Enforcement: <PASS/GAP>  — <one line summary>
  L — Ledger:      <PASS/GAP>  — <one line summary>
  D — Delegation:  <PASS/GAP>  — <one line summary>

  FORCE runtime: <enabled/disabled/absent> — preset <name>

  Gaps requiring resolution before deploy:
    - <bulleted list, or "None">

  Recommended reviewers:
    - Principal: <identity.principal>
    - Compliance / audit: <if jurisdiction requires>
```

Be terse. The user is auditing, not reading prose. After an audit, update `last_audit_at` in `~/.claude/state/field.json`.

## Templates

Four bootstrap templates ship with this skill in `templates/`:

| Template | Use case |
|---|---|
| `default` | Baseline general use. Fill in principal, kill switch, and delegation. |
| `financial-agent` | FP&A / audit-adjacent work. 7-year ledger retention. Cryptographic sealing required. Kill switch tied to spend cap. |
| `read-only-agent` | Retrieval / analysis. Zero write scope. No delegation of write actions. Reduced enforcement surface. |
| `client-facing-agent` | Draft-only outbound. Human review at every escalation. No autonomous send. |

Pick with `/field init <template>`.

## State file format

`field.json` schema:

```json
{
  "master": true,
  "preferred_template": "default",
  "working_manifest_path": null,
  "last_audit_at": null,
  "last_updated": "2026-06-25T14:30:00Z"
}
```

When writing `field.json`, always update `last_updated` to the current ISO 8601 timestamp.

## Limitations to flag if asked

- FIELD v1.1 is a manifest tool **plus a runtime enforcer inside Claude Code**. The plugin's Enforcement Gate (`hooks/`, a `PreToolUse` hook) enforces Enforcement and Ledger at runtime: E1 kill switch, E2 protected paths, E3 irreversible actions, E4 call budget, and L ledger — as listed in the gate README. The spend cap remains a tool-call proxy (E4 counts tool calls per session; it is not a dollar meter). Federated, Identity and Delegation remain declared, not enforced; outside Claude Code, or with hooks disabled (`--bare`, `disableAllHooks`), enforcement is still infrastructure the user builds around the manifest.
- Certification is not automated. `/field audit` produces an audit-ready report; independent verification is a separate service.
- The gate writes a sha-256 hash-chained ledger and `/field verify` checks it. The hash chain is **tamper-evident, not tamper-proof**: anyone with write access to the ledger file can rewrite the chain. Sealing beyond that (WORM storage, external anchoring) is still the ledger store the user configures.
- Composition with FORCE is asserted in the manifest but not runtime-wired. Actual application of FORCE at runtime is separate infrastructure.

For the full framework, methodology, and reference architectures, see [spinstatelabs.ca/field](https://spinstatelabs.ca/field).

## Companion files in this skill

- `framework.md` — The five-letter framework in operational detail. Read the relevant letters when generating/validating/auditing.
- `manifest-schema.json` — JSON Schema for FIELD manifests. Use this for `/field validate`.
- `field-defaults.json` — Default skill state, copied to `~/.claude/state/field.json` on first run.
- `templates/field-manifest-default.yaml` — Baseline manifest template.
- `templates/field-manifest-financial-agent.yaml` — FP&A / audit preset.
- `templates/field-manifest-read-only-agent.yaml` — Retrieval / read-only preset.
- `templates/field-manifest-client-facing-agent.yaml` — Draft-only outbound preset.

## Companion command (separate file in the plugin)

- `commands/field.md` — Slash command parser and state mutation logic.
- `hooks/hooks.json`, `hooks/field-gate.py`, `hooks/verify-ledger.py` — the Enforcement Gate (PreToolUse hook, auto-loaded by the plugin) and its ledger verifier; `hooks/test/` is the smoke test.
