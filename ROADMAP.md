# Force Field Protocol — Roadmap

The **Force Field Protocol** is Spin State Labs' approach to building agentic AI that's defensible in production: aligned, auditable, sovereign, and resistant to the two failure modes that have ended careers — sycophancy and hallucination.

Two complementary layers, two plugins, one marketplace. **Both shipped.**

```
┌──────────────────────────────────────────────────────────────────┐
│              FORCE FIELD FRAMEWORK                                │
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
│   │   Status: SHIPPED v1.0   │    │   Status: SHIPPED v1.0   │  │
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

## ✅ FIELD — Shipped (v1.0.0, June 2026)

**Governance layer for agentic AI systems.** Not a persona designer. Not a prompt protocol. A governance framework covering three concerns FORCE alone cannot address.

### Three pillars

1. **Agentic AI Harnessing** — runtime brakes and rails: kill switches, action boundaries, escalation triggers, spend caps.
2. **AI Sovereignty** — enterprise-level control: who owns the agent, what data it can access, in what jurisdiction it operates, what authority has been delegated.
3. **AI Federation** — rules for multi-agent systems where agents from different organizations or trust domains interoperate.

### The five letters

- **F** — Federation. Multi-agent trust protocols across ownership boundaries.
- **I** — Identity. Attribution: who owns the agent, whose interests it represents.
- **E** — Enforcement. Runtime harnessing — kill switches, spend caps, escalation.
- **L** — Ledger. Cryptographic immutable audit trail of every decision and action.
- **D** — Delegation. Authorization chain from human principal to autonomous agent.

### Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install field@force-field
```

### v1.0 highlights

- `field` plugin with SKILL.md and `/field` slash command
- Four manifest templates: `default`, `financial-agent`, `read-only-agent`, `client-facing-agent`
- JSON Schema for validation (`skills/field/manifest-schema.json`)
- Full framework reference (`skills/field/framework.md`) with detailed manifest examples
- FORCE composition — every FIELD manifest declares a `runtime_protocol` block; defaults to FORCE preset "analysis"

### What v1.0 is NOT (scope honesty)

- **Not a runtime enforcer.** Generates and validates the governance spec. Actual enforcement (halting agents, deducting from caps, ledger writes) requires infrastructure the user builds around the manifest.
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

---

## 🔜 What's next

### Force Field Protocol v1.1 (target: Q3 2026)

Usage-driven refinements to both FORCE and FIELD based on real-world feedback.

Likely additions:

- **Reference runtime enforcement in n8n** — sample workflow that reads a FIELD manifest and actually applies the constraints
- **FORCE + FIELD runtime composition** — automatic FORCE application inside FIELD-declared agents
- **Ledger reference implementations** — sample stores (s3, Postgres) with cryptographic sealing wired
- **Additional FIELD templates** — for agents Spin State clients ask about

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

*Spin State Labs · Force Field Protocol Roadmap v2.0 · Updated June 2026*
