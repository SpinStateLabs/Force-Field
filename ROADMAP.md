# Force Field Protocol — Roadmap

The **Force Field Protocol** is Spin State Labs' approach to building agentic AI that's defensible in production: aligned, auditable, sovereign, and resistant to the two failure modes that have ended careers — sycophancy and hallucination.

Two complementary layers, two plugins, one marketplace. **Both shipped.**

```
┌──────────────────────────────────────────────────────────────────┐
│              FORCE FIELD PROTOCOL                                 │
│                                                                   │
│   ┌──────────────────────────┐    ┌──────────────────────────┐  │
│   │   FORCE                  │    │   FIELD                  │  │
│   │   Runtime prompt         │    │   Governance layer for   │  │
│   │   protocol.              │    │   agentic AI systems.    │  │
│   │                          │    │                          │  │
│   │   Constrains what        │    │   Constrains how agents  │  │
│   │   an AI says on any      │    │   are harnessed, who     │  │
│   │   individual response.   │    │   owns them, and how     │  │
│   │                          │    │   they federate.         │  │
│   │                          │    │                          │  │
│   │   Status: SHIPPED v1.0   │    │   Status: SHIPPED v1.1   │  │
│   └──────────────────────────┘    └──────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## ✅ FORCE — Shipped (v1.0.0, June 2026)

**Five-letter runtime prompt protocol.** Toggleable constraints applied to individual model responses.

- **F** — Forbid Flattery & Force Corrections
- **O** — Oppose the Premise
- **R** — Reference Verified Sources
- **C** — Chain-of-Thought
- **E** — Express Uncertainty

### Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install force@force-field
```

### v1.0 highlights

- `force` plugin with SKILL.md, `/force` slash command, stable user-level state file
- Four presets: `analysis`, `brainstorm`, `draft`, `audit`
- Project-level state override for client-deliverable contexts
- Full kit at [spinstatelabs.ca/force](https://spinstatelabs.ca/force) — one-pager PDFs, Claude.ai system prompt, n8n workflow

### Production validation

- Successfully applied to a large client design project (June 2026) — the trigger for shipping FIELD alongside.

---

## ✅ FIELD — Shipped (v1.0.0, July 2026)

**Governance layer for agentic AI systems.** Not a persona designer. Not a prompt protocol. A governance framework covering three concerns FORCE alone cannot address.

### Three pillars

1. **Agentic AI Harnessing** — runtime brakes and rails: kill switches, action boundaries, escalation triggers, spend caps.
2. **AI Sovereignty** — enterprise-level control: who owns the agent, what data it can access, in what jurisdiction it operates, what authority has been delegated.
3. **AI Federated Operation** — rules for multi-agent systems where agents from different organizations, ownership structures, or trust domains must interoperate.

### The five letters

- **F** — Federated. Multi-agent trust protocols across ownership boundaries.
- **I** — Identity. Attribution: who owns the agent, whose interests it represents.
- **E** — Enforcement. Runtime harnessing — kill switches, spend caps, escalation.
- **L** — Ledger. Cryptographic immutable audit trail of every decision and action.
- **D** — Delegation. Authorization chain from human principal to autonomous agent.

### Letter mapping (committed, v1.0)

| Letter | Word | Pillar served |
|---|---|---|
| **F** | Federated | Federated operation |
| **I** | Identity | Sovereignty |
| **E** | Enforcement | Harnessing |
| **L** | Ledger | Crosscutting (audit / accountability) |
| **D** | Delegation | Sovereignty |

### Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install field@force-field
```

### What v1.0 includes

- `field` plugin with SKILL.md, `framework.md`, the `/field` slash command, and stable user-level state.
- Five governance letters: **F**ederated · **I**dentity · **E**nforcement · **L**edger · **D**elegation.
- A per-agent governance manifest (`field-manifest.yaml`) with a JSON Schema that enforces the non-negotiables (kill switch, delegation grantor, identity principal, sealed ledger).
- Four bootstrap templates: `default`, `financial-agent`, `read-only-agent`, `client-facing-agent`.
- Composition with FORCE: every FIELD-governed agent declares FORCE as its runtime protocol.
- Manual installers (`install.ps1`, `install.sh`) and `INSTALL.md` for air-gapped / pre-publish deployment.

### What v1.0 is NOT (scope honesty)

- **Not a runtime enforcer.** v1.0 generates and validates the governance spec. Runtime enforcement of the E and L letters inside Claude Code arrived with the v1.1 Enforcement Gate (below); estate-level enforcement across many agents is the Conformance Sentinel (What's next).
- **Not automated certification.** `/field audit` produces an audit-ready report; independent verification is separate.
- **Not cryptographic sealing.** Declared in manifests; the configured ledger store must implement it.

### Positioning vs. existing governance frameworks

FIELD is **not**:
- A replacement for NIST AI RMF, ISO/IEC 42001, or the EU AI Act
- A political statement about national AI sovereignty
- An academic ethics framework

FIELD **is**:
- Practitioner-implementable governance specifically for agentic systems
- Complementary to broad governance frameworks
- Focused on the specific problem of AI agents acting autonomously on behalf of principals

### Design decisions (resolved in v1.0)

1. **Letter mapping** — committed: Federated · Identity · Enforcement · Ledger · Delegation.
2. **Implementation pattern** — shipped as a Claude Code plugin: the `/field` skill generates, validates, and audits a per-agent governance manifest, with a JSON Schema and four bootstrap templates. Methodology one-pager and reference architectures are the v1.1 follow-on.
3. **Composition with FORCE** — resolved: every FIELD-governed agent declares FORCE as its `runtime_protocol` in the manifest. Design-time wraps runtime.
4. **Audit surface** — self-attestation via `/field audit` against a cryptographically sealed ledger declared in the manifest. Third-party certification remains a separate service.

### Still open (post-v1.0)

- **Business model** — open framework vs. certified assessment service. Both remain on the table.
- **Runtime enforcement** — resolved for Claude Code in v1.1 (Enforcement Gate: kill switch, protected paths, irreversible-action deny patterns, tool-call budget, hash-chained ledger). Estate-level enforcement across agents and hosts is the Conformance Sentinel, in blocking-mode burn-in since August 2026.
- **Landing page** — `spinstatelabs.ca/field` methodology document and self-assessment.

---

## ✅ FIELD v1.1 — Enforcement Gate (field 1.1.0 / marketplace 1.2.0, September 12, 2026)

The public commitment in v1.0 was "enforcement in v1.1". v1.1 delivers it inside Claude Code: a `PreToolUse` hook, auto-loaded from `hooks/hooks.json`, that reads `./field-manifest.yaml` and enforces it at runtime.

- **E1 kill switch** — a sentinel file; while it exists every gated tool call is denied.
- **E2 protected paths** — the manifest, Claude settings, hooks, the ledger and the call counter, plus `enforcement.protected_paths` regexes.
- **E3 irreversible actions** — `enforcement.irreversible_actions.deny_patterns` on Bash commands, denied outright.
- **E4 call budget** — a per-session tool-call ceiling (`{action: tool_call, period: session}`) that proxies the spend cap.
- **L ledger** — every decision appended to the ledger store, sha-256 hash-chained; `hooks/verify-ledger.py` checks the chain.
- **Fail-closed** — an unreadable manifest, missing PyYAML, a misconfigured kill switch, or an internal error denies with rule `E0`.
- `/field kill`, `/field resume`, `/field verify`; `/field status` reports whether the gate is armed.
- Schema changes are additive — every v1.0 manifest stays valid.

### What v1.1 is NOT (scope honesty)

- **Federated, Identity and Delegation remain declared, not enforced.**
- The spend cap is a tool-call proxy, not metered spend.
- The ledger hash chain is tamper-evident, not tamper-proof.
- The gate protects one Claude Code session. Enforcement across an estate of agents — with a semantic judge for natural-language scopes — is the Conformance Sentinel (below).

---

## 🔜 What's next

### Enforcement Gate v1.2 (next plugin release)

- **Policy-driven verdicts** — `irreversible_action_policy` → deny / ask / allow-with-ledger.
- **A locked call counter** and a `kill_switch.local_sentinel` alongside an estate endpoint.
- **FORCE + FIELD runtime composition** — automatic FORCE application inside FIELD-declared agents.
- **Ledger reference implementations** — sample stores (s3, Postgres) with cryptographic sealing wired.
- **Additional FIELD templates** — for agents Spin State clients ask about.
- **Reference runtime enforcement in n8n** (possible) — a sample workflow that reads a FIELD manifest and applies its constraints outside Claude Code.

### Conformance Sentinel — estate-level enforcement (general release target: November 2026)

An enforcement agent that continuously audits deployed agents against their FIELD manifests and blocks non-conforming actions — scope breaches, expired authority, missing ledger writes — at the policy-enforcement point, before they execute. A deterministic policy engine decides structural conformance; a narrowly scoped LLM judge, grounded by retrieval over the estate's manifests, handles natural-language scopes and fails to escalate, never to silent allow.

- **Proof of concept (August 2026, complete)** — 21 days of blocking-mode operation on Spin State's own estate: 136 verdicts, zero false blocks; seeded-violation catch 40/40; kill drill passed.
- **Pilot (targeted from September 14, 2026)** — a scoped client pilot, conditional on a signed sponsor; continuation gates: false-block rate below 1.6% over 30 consecutive days, no escalation unresolved past 48 hours.
- **General release (target November 2026)** — injection-corpus pass, pricing, support runbook. The gates, not the calendar, are the go condition.

### Future plugins under consideration

Not committed. On the radar once FORCE + FIELD have production validation:

- **`nspb-analyst`** — NetSuite Planning & Budgeting analyst skill with FORCE + FIELD compliance
- **`epm-audit`** — Audit-focused skill for EPM deliverables
- **`variance-narrator`** — Variance analysis with confidence-tagged commentary

---

## Versioning policy

- Plugins follow [SemVer](https://semver.org/).
- Marketplace catalog version reflects the catalog itself, not the plugins inside.
- Breaking changes to plugin behavior require a major version bump and a migration note in `CHANGELOG.md`.

---

## How to influence the roadmap

1. **Use FORCE and FIELD in production.** Real practitioner feedback shapes v1.1+.
2. **Open issues** on the [GitHub repo](https://github.com/SpinStateLabs/Force-Field) for bugs, gaps, or feature requests.
3. **Contact** Don: `don@spinstatelabs.ca` for substantive design input.

---

*Spin State Labs · Force Field Protocol Roadmap v2.2 · Updated September 2026*
