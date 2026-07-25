# FIELD Design Brief

Working document for the FIELD sprint. Not for public release. Captures scope, constraints, open questions, and design candidates as of 2026-06-25 so the sprint can pick up cleanly when FORCE has been in market for 2-4 weeks.

**Status:** SCOPED · design sprint has not started

---

## Positioning statement (draft)

> FIELD is Spin State Labs' governance framework for agentic AI. It addresses three concerns that runtime prompt protocols (FORCE) alone cannot: how autonomous agents are harnessed, who has sovereign authority over them, and how they federate across trust boundaries. Where FORCE constrains what an AI says, FIELD constrains how an AI is deployed, controlled, and accountable.

**Confidence: MEDIUM.** Positioning statement is a first draft. Refine when the sprint starts.

---

## Three pillars (founder-specified)

### 1. Agentic AI Harnessing

**What it means.** Structural and runtime constraints that prevent an autonomous agent from operating outside its authorized scope. The "brakes and rails" of agentic operation.

**Concrete concerns:**
- Kill switches — how does a human halt an autonomous agent mid-action?
- Action boundaries — what operations is the agent structurally incapable of performing?
- Escalation triggers — under what conditions does the agent stop and defer to a human?
- Rate limits and cost ceilings — spend caps, action frequency caps
- Reversibility — which agent actions must be reversible, which are one-way

**Analog in existing frameworks:** parallels to industrial safety systems, financial trading circuit breakers, aviation autopilot handoff logic.

**Confidence: HIGH** that this is a real, addressable concern. **MEDIUM** that Spin State can differentiate here vs. built-in vendor safety features.

---

### 2. AI Sovereignty

**What it means.** Enterprise-level control over AI systems: who owns the agent, what data it can access, what authority it holds, in what jurisdiction it operates.

**Concrete concerns:**
- Attribution — which principal (person, org, department) does the agent represent
- Authorization chain — what actions has the agent been delegated authority to perform, by whom, under what scope
- Data sovereignty — what data can the agent access, retain, transmit, and to whom
- Jurisdictional constraints — what regulatory regime governs the agent's operation (SOX, GDPR, PIPEDA, etc.)
- Model sovereignty — which underlying model provider, what happens if that provider changes terms

**Positioning caution:** "AI sovereignty" has three common meanings in public discourse:
- **National sovereignty** — a country's control over its AI capabilities (France, EU, China, Canada)
- **Enterprise sovereignty** — an organization's control over its AI systems
- **Personal sovereignty** — individual control over AI acting on their behalf

FIELD targets **enterprise sovereignty** primarily. Framing should make this explicit to avoid being pulled into geopolitical debates that don't serve Spin State's buyer.

**Confidence: HIGH** on the concern. **MEDIUM** on Spin State's ability to position without ambiguity.

---

### 3. AI Federation

**What it means.** Rules for multi-agent systems where agents from different organizations, ownership structures, or trust domains must interoperate.

**Concrete concerns:**
- Trust protocols — how does Agent A know Agent B is authentic and authorized
- Contract semantics — how do agents from different orgs agree on what they're doing
- Data sharing across trust boundaries — what leaves the sovereign domain, what stays
- Dispute resolution — when agents disagree, whose authority prevails
- Discovery — how does Agent A find Agent B in the first place

**Terminology caution:** "Federation" has a specific technical meaning in ML (federated learning). FIELD uses it in the multi-agent sense — like federated identity, but for autonomous agents. Documentation must be explicit to avoid confusion.

**Confidence: HIGH** on the concern being real. **LOW** on maturity of solutions — this space is emerging.

---

## First-draft letter mapping

Three pillars, five letters. Some pillars split; one letter (Ledger) is crosscutting.

| Letter | Word | Pillar served | What it constrains |
|---|---|---|---|
| **F** | Federation | Federation | Rules for agents operating across trust boundaries |
| **I** | Identity | Sovereignty | Attribution — who owns this agent, whose interests it represents |
| **E** | Enforcement | Harnessing | Runtime constraints, kill switches, boundary enforcement |
| **L** | Ledger | Crosscutting | Audit trail, accountability, transparency |
| **D** | Delegation | Sovereignty | Authorization chain from human principal to autonomous agent |

**Alternative mappings to consider:**

Version B (harder emphasis on control):
| Letter | Word |
|---|---|
| F | Federation |
| I | Identity |
| E | Enforcement |
| L | Limits |
| D | Delegation |

Version C (audit-first framing):
| Letter | Word |
|---|---|
| F | Federation |
| I | Integrity |
| E | Enforcement |
| L | Ledger |
| D | Deputation |

**Confidence on letter mapping: LOW.** Not committed. Pick during Sprint 2 kickoff.

---

## Positioning vs. existing governance frameworks

### What FIELD is NOT

- Not a replacement for NIST AI RMF (broad, government-oriented)
- Not competing with ISO/IEC 42001 (AI management systems, org-wide)
- Not an EU AI Act compliance framework (regulatory, jurisdiction-specific)
- Not Anthropic's Responsible Scaling Policy (model-provider policy)
- Not a political statement about national AI sovereignty
- Not a persona designer (my earlier mischaracterization)

### What FIELD IS

- **Practitioner-implementable** governance specifically for agentic systems
- **Complementary** to broad frameworks — a company on ISO 42001 can adopt FIELD without conflict
- **Agentic-first** — designed for AI that takes actions, not just answers questions
- **Composable with FORCE** — every FIELD-governed agent applies FORCE at runtime

### Differentiation thesis (draft)

> Existing governance frameworks treat AI as a system to be managed. FIELD treats AI agents as actors with delegated authority — closer to how a company governs its employees than its software. That mental model reframes harnessing, sovereignty, and federation as the actual load-bearing concerns for autonomous AI in production.

**Confidence on this thesis being differentiated enough to matter: MEDIUM.** Needs validation with a handful of enterprise AI buyers before commit.

---

## Implementation options (not decided)

FIELD is a governance framework. Governance frameworks ship as multiple artifact types. Options:

### Option A: Methodology-only

- One-pager PDF (matching FORCE style)
- Landing page section at spinstatelabs.ca/field or merged into /force
- Detailed methodology document (10-20 pages, PDF)
- No code, no plugin

**Pro:** fastest to ship, lowest maintenance, highest reach.  
**Con:** hard to enforce, no lock-in, doesn't create Spin State revenue directly.

### Option B: Methodology + assessment tooling

- Everything in Option A
- Self-assessment questionnaire (interactive on landing page)
- Compliance scoring template
- Reference architectures for common patterns

**Pro:** creates practitioner engagement, generates leads for Spin State services.  
**Con:** more maintenance, requires ongoing content updates.

### Option C: Methodology + Claude Code plugin

- Everything in Option A
- `field` plugin at `plugins/field/` in Force-Field marketplace
- Slash commands: `/field-assess`, `/field-manifest`, `/field-audit`
- Sub-agent templates for common governance patterns
- Governance manifest schema (YAML/JSON) that describes agent's FIELD compliance

**Pro:** fits the marketplace pattern, technical enforcement, developer adoption.  
**Con:** technical scope creep — governance is fundamentally organizational, not code.

### Option D: Certified assessment as a service

- Methodology + Spin State performs FIELD assessments as a paid service
- Certification mark for compliant deployments
- Ongoing audit relationship

**Pro:** direct revenue path, positions Spin State as authoritative source.  
**Con:** consulting-heavy business model, doesn't scale like software.

### Recommended for Sprint 2 kickoff

**Combine A + B first.** Ship the methodology and assessment tooling as the MVP. Add C (plugin) only if there's technical enforcement value that the methodology can't capture. D (certification) is a business model decision for later, not a launch decision.

**Confidence: MEDIUM.** Founder decision. This is a business-model choice as much as a technical one.

---

## Open design questions

Consolidated. Answer these during Sprint 2 kickoff:

1. **Final letter mapping** for FIELD acronym (see three candidates above)
2. **Primary buyer** for FIELD — CFO / Chief Compliance Officer / CIO / CTO / Head of AI?
3. **Primary implementation shape** — methodology only, methodology + tooling, methodology + plugin, methodology + certification (see options A-D)
4. **Composition rules with FORCE** — is FORCE mandatory in FIELD-compliant agents, or one of several acceptable runtime protocols?
5. **Audit surface** — self-attestation, third-party assessment, or cryptographic attestation
6. **Certification model** — open framework only, or Spin State-certified compliant?
7. **Naming strategy** — do we announce FIELD publicly before Q3 2026, or design in stealth?
8. **Landing page architecture** — separate `/field` page, merged into `/force`, or new umbrella `/force-field`?

---

## Success criteria for FIELD v1.0

For the initial launch to be considered successful, at least three of the following should be true 90 days after launch:

- [ ] 3+ Spin State clients have adopted FIELD as their internal agent governance framework
- [ ] 1+ industry publication or standards body has cited FIELD
- [ ] The FIELD assessment tool (if built) has been used by 50+ organizations
- [ ] FIELD has generated at least one qualified sales lead for Spin State's advisory services
- [ ] The framework has been refined at least once based on practitioner feedback (v1.1 shipped)

**Confidence: MEDIUM** these are the right success metrics. Refine when the sprint starts.

---

## Related reading (pre-sprint prep)

Before Sprint 2 kicks off, review the current state of:

- NIST AI Risk Management Framework (AI RMF 1.0 + 2.0 if available)
- ISO/IEC 42001:2023 AI management systems
- EU AI Act — final adopted text, especially agent-specific provisions
- Anthropic Responsible Scaling Policy — most recent version
- Any recent (2025-2026) publications on multi-agent governance
- Enterprise agent deployment case studies

Objective: know what already exists so FIELD doesn't reinvent.

---

## Sprint 2 kickoff prerequisites

Do NOT start FIELD until all of the following are true:

- [ ] FORCE has been in market at least 2 weeks post-launch
- [ ] FORCE has real usage data (at least 100 landing page conversions or 10 active plugin installs)
- [ ] Spin State has spoken to at least 3 enterprise AI decision-makers about their governance needs
- [ ] Founder has resolved the 8 design questions above (or set explicit "punt to sprint" markers for a few)
- [ ] Positioning statement has been sharpened and pressure-tested

---

## Change log for this brief

- 2026-06-25: Initial scoping. Reframed from "AI persona development" (my earlier placeholder) to "governance layer for agentic AI" (founder direction).

---

*Spin State Labs · FIELD Design Brief v0.1 (pre-sprint) · Internal document*
