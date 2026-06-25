# Force Field Framework — Roadmap

The **Force Field Framework** is Spin State Labs' approach to building AI that's defensible in production: aligned, auditable, and resistant to the two failure modes that have ended careers — sycophancy and hallucination.

Two complementary layers, two plugins, one marketplace.

```
┌──────────────────────────────────────────────────────────────────┐
│              FORCE FIELD FRAMEWORK                                │
│                                                                   │
│   ┌──────────────────────────┐    ┌──────────────────────────┐  │
│   │   FORCE                  │    │   FIELD                  │  │
│   │   Prompt protocol layer  │    │   Persona development     │  │
│   │                          │    │   layer                  │  │
│   │   Runtime constraints    │    │   Design-time methodology│  │
│   │   on individual          │    │   for agent personas,    │  │
│   │   responses.             │    │   boundaries, and        │  │
│   │                          │    │   alignment.             │  │
│   │   Status: SHIPPED v1.0   │    │   Status: TODO           │  │
│   └──────────────────────────┘    └──────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## ✅ FORCE — Shipped (v1.0.0, June 2026)

**Five-letter prompt protocol.** Toggleable runtime constraints applied to individual model responses.

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

- `force` plugin with the SKILL.md, `/force` slash command, and stable user-level state file
- Four presets: `analysis`, `brainstorm`, `draft`, `audit`
- Project-level state override for client-deliverable contexts
- Full kit at [spinstatelabs.ca/force](https://spinstatelabs.ca/force) — one-pager PDFs, Claude.ai-compatible system prompt, n8n workflow

### Next iterations

- v1.1: refinements based on real-world usage feedback
- v1.2: protocol additions if practitioner testing surfaces gaps

---

## 🔜 FIELD — In design (target: Q3 2026)

**AI persona development methodology.** Design-time framework for building agents that stay aligned, auditable, and production-ready over thousands of interactions — not just one response.

FORCE constrains *what an AI says*. FIELD constrains *who the AI is*.

### Design questions to resolve

1. **The five letters.** FIELD needs to decompose into five distinct dimensions, the way FORCE does. Candidates (placeholders, not commitments):
   - F — Functional scope (what the persona is allowed to do)
   - I — Identity & values (who the persona is, what it cares about)
   - E — Escalation protocols (when to defer to humans)
   - L — Limits & boundaries (what the persona refuses)
   - D — Decision rights (what the persona can act on autonomously)

   These are sketches. Final acronym lands when the framework is designed.

2. **Implementation pattern.** Unlike FORCE (runtime toggle), FIELD is a design-time methodology. The Claude Code plugin shape may differ:
   - A subagent generator? Walks a user through defining a new persona.
   - A template library? A set of FIELD-compliant persona templates.
   - A validator? Checks an existing persona against FIELD principles.
   - All three?

3. **Composition with FORCE.** Does a FIELD-defined persona auto-apply FORCE? Or is FORCE a runtime overlay that any persona can opt into?

4. **Audit surface.** How does a third party verify a persona is FIELD-compliant? Self-attestation? Generated audit log? Cryptographic attestation of persona spec?

### When FIELD ships

- A second plugin in this marketplace: `/plugin install field@force-field`
- A second branded artifact set: PDF, landing page section at `spinstatelabs.ca/force-field`
- Integration patterns documented for FORCE + FIELD composition

### Why this isn't built yet

FORCE earns trust by proving the protocol works in production. FIELD inherits that credibility. Shipping FIELD before FORCE has real-world validation would dilute both. **MEDIUM confidence** that the right ordering is FORCE first, then FIELD — based on standard product sequencing logic, not validated by user research.

---

## Future plugins under consideration

Not committed, just on the radar:

- **`nspb-analyst`** — NetSuite Planning & Budgeting analyst skill with built-in FORCE
- **`epm-audit`** — Audit-focused skill for EPM deliverables (Oracle EPBCS, NSPB)
- **`variance-narrator`** — Variance analysis with confidence-tagged commentary

These are downstream of FORCE + FIELD. Don't ship until the foundation is validated.

---

## Versioning policy

- Plugins follow [SemVer](https://semver.org/).
- Marketplace catalog (`marketplace.json`) version reflects the catalog itself, not the plugins inside it.
- Breaking changes to plugin behavior (e.g. changing state file location or schema) require a major version bump and a migration note in `CHANGELOG.md`.

---

## How to influence the roadmap

1. **Use FORCE in production.** Real practitioner feedback shapes v1.1+ and informs FIELD design.
2. **Open issues** on the [GitHub repo](https://github.com/SpinStateLabs/Force-Field) for bugs, gaps, or feature requests.
3. **Contact** Don directly: `don@spinstatelabs.ca` for substantive design input on FIELD.

---

*Spin State Labs · Force Field Framework Roadmap v1.0 · Updated June 2026*
