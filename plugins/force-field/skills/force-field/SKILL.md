---
name: force-field
description: Explain and apply the Force-Field Protocol from Spin State Labs — FORCE (runtime prompt protocol that constrains what an AI says) composed with FIELD (design-time governance that constrains how an agent is deployed and held accountable). Use when the user asks how FORCE and FIELD fit together, which one to use, wants to apply both to an agent, mentions the Force-Field Protocol, or asks which Force-Field plugins are installed. Defers to the companion force and field plugins for the full protocol and the /force and /field commands.
---

# Force-Field Protocol (umbrella skill)

The Force-Field Protocol is Spin State Labs' two-layer standard for AI that is defensible in production.
This skill is the map between the layers. It does not restate them: the full FORCE protocol lives in
the `force` plugin and the full FIELD framework lives in the `field` plugin.

## The two layers

| Layer | Question it answers | When it applies | Artifact | Command |
|---|---|---|---|---|
| **FORCE** | What does the agent *say*? | Runtime — every response | Session state (`~/.claude/state/force.json`) | `/force` |
| **FIELD** | How is the agent *deployed, controlled, and held accountable*? | Design time — before and around deployment | Per-agent manifest (`./field-manifest.yaml`) | `/field` |

- **FORCE** — Forbid flattery, Oppose the premise, Reference verified sources, Chain-of-thought,
  Express uncertainty. Neutralizes sycophancy and hallucination on individual responses.
- **FIELD** — Federated, Identity, Enforcement, Ledger, Delegation. Declares who owns an agent, what
  authority it holds, how it is stopped, and how its actions are recorded.

**How they compose:** FIELD wraps FORCE. Every FIELD-governed agent runs FORCE at runtime, and the
manifest declares it in a `runtime_protocol` block (`name: FORCE`, with a preset). Runtime and design
time never conflict: FORCE governs each answer, FIELD governs the agent that gives it.

## When to use which

- **FORCE only** — analysis, decision support, code review, audit-style review of a document, any
  single conversation where the output must be defensible. No autonomous agent is involved.
- **FIELD only** — rare. Scoping governance for an agent whose runtime behavior is not an LLM response
  (for example a tightly constrained single-purpose tool runner). FIELD will flag a missing FORCE
  declaration for review; it does not refuse.
- **Both** — designing, deploying, or auditing any autonomous agent that acts for a principal. This is
  the default for agentic work.
- **Neither** — casual conversation, creative writing, simple lookups.

If unsure, ask one question: "Will this run as an agent with authority to act, or is it a single
response?" Agent → both. Single response → FORCE.

## Status check — which companion plugins are present

Run this check first whenever this skill activates, and whenever the user asks for status.

1. Look at the skills and slash commands available in this session.
   - FORCE is present if a `force` skill (often shown as `force:force`) or a `/force` command is
     available.
   - FIELD is present if a `field` skill (often shown as `field:field`) or a `/field` command is
     available.
2. Report in this format, terse, no prose:

```
Force-Field Protocol status
  FORCE (force plugin): PRESENT / MISSING
  FIELD (field plugin): PRESENT / MISSING
  Enforcement Gate: run /field status  (or: N/A — FIELD missing / hooks not loaded in claude.ai chat)
```

Never report the Enforcement Gate as armed yourself. It is a `PreToolUse` hook shipped by the `field`
plugin; it loads in Claude Code and Cowork, not in claude.ai chat, and it only acts when a
`./field-manifest.yaml` exists. `/field status` is the authority on whether it is armed.

3. If either plugin is MISSING, say so plainly and give the install steps. Do not improvise the missing
   protocol from memory; point to the companion plugin.

In Claude Code:

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install force@force-field
/plugin install field@force-field
/reload-plugins
```

In claude.ai or Cowork: install `force` and `field` from the same place this plugin came from
(Customize > Plugins). Plugin dependencies are installed automatically only by Claude Code; other
surfaces may install this umbrella without its companions.

## Apply both — workflow

Use this when the user is building or reviewing an agent.

1. **Status check** (above). Both plugins must be present; if not, stop and give install steps.
2. **Set FORCE for the session.** Run `/force` to see state. For governance work the `analysis`
   preset (all five letters) is the default; `audit` suits review against source documents.
3. **Draft the manifest with FIELD.** Run `/field init <template>` (`default`, `financial-agent`,
   `read-only-agent`, `client-facing-agent`), then `/field assess` to walk F → I → E → L → D. Make sure
   the manifest's `runtime_protocol` block names FORCE and the preset chosen in step 2.
4. **Review the manifest's claims under FORCE.** Treat the manifest as a set of claims and apply the
   FORCE letters to it:
   - **O** — state the strongest objections to the agent's design before endorsing it.
   - **R** — every claim about a kill switch, ledger store, peer, or grantor must point to something
     real (an endpoint, a path, a named person). Mark anything else "not in source".
   - **E** — tag each control HIGH / MEDIUM / LOW confidence: does it exist and work today, or is it
     declared only? FIELD's own limitations apply — Federated, Identity, and Delegation are declared,
     not enforced; the call budget is a tool-call proxy, not a dollar meter.
   - **F** — do not soften gaps. A `REPLACE-ME` value is an unresolved gap, not a detail.
5. **Validate and audit.** Run `/field validate`, fix critical gaps, then `/field audit` for the
   audit-ready summary.
6. **Hand back to the human.** Once a manifest exists, the FIELD Enforcement Gate treats it as a
   protected path in Claude Code, so later governance changes are made by the human, outside the
   session (see the `field` plugin README).

## Boundaries

- This skill adds no commands, hooks, scripts, or MCP servers, and makes no network calls. All runtime
  behavior comes from the companion plugins.
- Do not duplicate or paraphrase the full FORCE protocol or FIELD framework here. Read the companion
  skills (`force` → `protocol.md`; `field` → `framework.md`) when depth is needed.
- Landing pages: https://spinstatelabs.ca/force and https://spinstatelabs.ca/field
