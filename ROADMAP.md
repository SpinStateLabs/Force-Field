# Force Field Framework — Roadmap

The **Force Field Framework** is Spin State Labs' approach to building agentic AI that's defensible in production: aligned, auditable, sovereign, and resistant to the two failure modes that have ended careers — sycophancy and hallucination.

Two complementary layers, two plugins, one marketplace.

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

### What v1.0 includes

- `force` plugin with SKILL.md, `/force` slash command, stable user-level state file
- Four presets: `analysis`, `brainstorm`, `draft`, `audit`
- Project-level state override for client-deliverable contexts
- Full kit at [spinstatelabs.ca/force](https://spinstatelabs.ca/force) — one-pager PDFs, Claude.ai system prompt, n8n workflow

### Next iterations

- v1.1: refinements based on real-world usage feedback
- v1.2: protocol additions if practitioner testing surfaces gaps

---

## ✅ FIELD — Governance layer for agentic AI (v1.0.0, July 2026)

**Not a persona designer. Not a prompt protocol. A governance framework for agentic AI systems.**

### Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install field@force-field
```

### What v1.0 includes

- `field` plugin with SKILL.md, `framework.md`, the `/field` slash command, and stable user-level state.
- Five governance letters: **F**ederation · **I**dentity · **E**nforcement · **L**edger · **D**elegation.
- A per-agent governance manifest (`field-manifest.yaml`) with a JSON Schema that enforces the non-negotiables (kill switch, delegation grantor, identity principal, sealed ledger).
- Four bootstrap templates: `default`, `financial-agent`, `read-only-agent`, `client-facing-agent`.
- Composition with FORCE: every FIELD-governed agent declares FORCE as its runtime protocol.

Three pillars:

### 1. Agentic AI Harnessing
Runtime and structural constraints on autonomous agents. Kill switches, action boundaries, escalation triggers, human-in-the-loop enforcement points. The "brakes and rails" of agentic operation.

### 2. AI Sovereignty
Enterprise-level control over AI systems: who owns the agent, what data it can access, what authority it holds, in what jurisdiction it operates. Attribution, authorization, and boundaries of decision rights.

### 3. AI Federation
Rules for multi-agent systems where agents from different organizations, ownership structures, or trust domains must interoperate. Trust protocols, contract semantics, and the equivalent of border controls between agent populations.

### Letter mapping (committed, v1.0)

| Letter | Word | Pillar served |
|---|---|---|
| **F** | Federation | Federation |
| **I** | Identity | Sovereignty |
| **E** | Enforcement | Harnessing |
| **L** | Ledger | Crosscutting (audit / accountability) |
| **D** | Delegation | Sovereignty |

### Why this framing (vs. persona development)

The original placeholder positioned FIELD as "AI persona development." That framing was too narrow. Persona is one output of governance — but governance covers ownership, accountability, and multi-agent interoperation that persona alone doesn't address. Governance is also the register enterprise buyers understand: CFOs and Controllers already think about audit, control, delegation. FIELD in governance terms sells itself.

### Positioning vs. existing frameworks

FIELD is **not**:
- A replacement for NIST AI RMF, ISO/IEC 42001, or the EU AI Act
- A political statement about national AI sovereignty
- An academic ethics framework

FIELD **is**:
- Practitioner-implementable governance specifically for agentic systems
- Complementary to broad governance frameworks (a company using ISO 42001 can also adopt FIELD)
- Focused on the specific problem of AI agents acting autonomously on behalf of principals

### Design decisions (resolved in v1.0)

1. **Letter mapping** — committed: Federation · Identity · Enforcement · Ledger · Delegation.
2. **Implementation pattern** — shipped as a Claude Code plugin: the `/field` skill generates, validates, and audits a per-agent governance manifest, with a JSON Schema and four bootstrap templates. Methodology one-pager and reference architectures are the v1.1 follow-on.
3. **Composition with FORCE** — resolved: every FIELD-governed agent declares FORCE as its `runtime_protocol` in the manifest. Design-time wraps runtime.
4. **Audit surface** — self-attestation via `/field audit` against a cryptographically sealed ledger declared in the manifest. Third-party certification remains a separate service.

### Still open (post-v1.0)

- **Business model** — open framework vs. certified assessment service. Both remain on the table.
- **Runtime enforcement** — v1.0 is a manifest tool. Wiring kill switches, ledger writes, and spend caps to live infrastructure is a v1.1+ question.
- **Landing page** — `spinstatelabs.ca/field` methodology document and self-assessment.

---

## Future plugins under consideration

Not committed. On the radar for after FORCE + FIELD are stable:

- **`nspb-analyst`** — NetSuite Planning & Budgeting analyst skill with FORCE + FIELD compliance
- **`epm-audit`** — Audit-focused skill for EPM deliverables (Oracle EPBCS, NSPB)
- **`variance-narrator`** — Variance analysis with confidence-tagged commentary

---

## Versioning policy

- Plugins follow [SemVer](https://semver.org/).
- Marketplace catalog version reflects the catalog itself, not the plugins inside it.
- Breaking changes require a major version bump and a migration note in `CHANGELOG.md`.

---

## How to influence the roadmap

1. **Use FORCE in production.** Real practitioner feedback shapes v1.1+ and informs FIELD design.
2. **Open issues** on the [GitHub repo](https://github.com/SpinStateLabs/Force-Field) for bugs, gaps, or feature requests.
3. **Contact** Don: `don@spinstatelabs.ca` for substantive input on FIELD governance framework design.

---

*Spin State Labs · Force Field Framework Roadmap v1.2 · Updated July 2026*
