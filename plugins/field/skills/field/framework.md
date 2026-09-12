# FIELD Framework — the five letters

FIELD is Spin State Labs' governance framework for agentic AI. Where FORCE constrains what an
AI *says* on a given response, FIELD constrains how an AI is *deployed, controlled, and held
accountable*. FORCE is runtime; FIELD is design-time. Every FIELD-governed agent carries one
**manifest** (`field-manifest.yaml`) declaring its posture across all five letters.

Each section below is the operational definition of one letter: what it constrains, the manifest
fields it maps to, the validation rules, and the **critical gaps** that force an `INVALID`
verdict. When generating, validating, or auditing a manifest, read the relevant letters here.

---

## [F] FEDERATED — trust across ownership boundaries

**Pillar: Federated operation.** Rules for multi-agent systems where agents from different
organizations, ownership structures, or trust domains interoperate. Not federated learning —
the F here is closer to federated *identity* for autonomous agents.

**Constrains:** which external peers this agent may talk to, how those peers are authenticated,
and what contracts govern each exchange.

**Manifest fields:** `federated.isolated`, `federated.allowed_peers[]`, `federated.contracts[]`.

**Rules:**
- `isolated` is mandatory and explicit. `isolated: true` declares an agent with no external peers.
  Do not leave federated posture undeclared — silence is not a valid answer.
- If `isolated: false`, `allowed_peers` MUST be non-empty. An agent that federates must name whom.
- Every peer needs a `trust_basis` — how Agent A knows Agent B is authentic and authorized
  (mTLS cert, signed capability token, shared registry entry). "We trust them" is not a trust basis.
- Contracts declare the *scope* of each cross-boundary exchange: what leaves the sovereign domain,
  what stays.

**Critical gap:** none from isolation itself — an isolated agent is fully valid. But every declared
peer MUST carry a `trust_basis` (schema-enforced); a named peer without one is **INVALID**.
**Warning** if a named peer has no governing entry in `contracts`.

---

## [I] IDENTITY — attribution and sovereignty

**Pillar: AI Sovereignty.** Enterprise-level control over the agent: who owns it, what data it
touches, what authority it holds, in what jurisdiction it operates. FIELD targets **enterprise**
sovereignty (an organization's control over its systems), not national or personal sovereignty.

**Constrains:** the principal the agent represents, the org and jurisdiction that govern it, and
the data it may access, retain, and transmit.

**Manifest fields:** `identity.principal`, `identity.org`, `identity.jurisdiction[]`,
`identity.data_scope`, `identity.model_provider`.

**Rules:**
- `principal` is mandatory. It names the human or organizational principal whose interests the
  agent serves. An agent that represents no one has no legitimate standing.
- `jurisdiction` declares the regulatory regimes in force (SOX, GDPR, PIPEDA, EU-AI-Act). It drives
  ledger retention and reviewer requirements at audit time.
- `data_scope` is least-privilege: `may_access`, `may_retain`, `may_transmit` are declared
  separately. An empty `may_transmit` means the agent exfiltrates nothing.
- `model_provider` records model sovereignty — which provider, so a terms change is a known risk.

**Critical gap:** missing `identity.principal` → **INVALID** (sovereignty violation).

---

## [E] ENFORCEMENT — the brakes and rails

**Pillar: Agentic AI Harnessing.** Structural and runtime constraints that stop an autonomous
agent operating outside its authorized envelope. The parallels are industrial safety interlocks,
trading circuit breakers, and aviation autopilot handoff logic.

**Constrains:** how a human halts the agent, what it structurally cannot do, when it must stop and
defer, and how much it may spend.

**Manifest fields:** `enforcement.kill_switch{endpoint, method, authorized_operators}`,
`enforcement.spend_cap`, `enforcement.escalation_triggers[]`, `enforcement.rate_limits[]`,
`enforcement.irreversible_action_policy`, `enforcement.irreversible_actions{deny_patterns[]}`,
`enforcement.protected_paths[]`.

**Rules:**
- `kill_switch` is mandatory and must specify a reachable `endpoint` and a `method` (how the halt
  is triggered). A kill switch nobody can reach is not a kill switch.
- `irreversible_action_policy` is mandatory: `forbid`, `require_human_approval`, or
  `allow_with_ledger`. One-way actions (transfers, deletes, sends) are governed here.
- `spend_cap`, when present, declares `on_breach` behavior. For regulated agents, tie the cap to
  the kill switch (`on_breach: halt`).
- `escalation_triggers` name the conditions under which the agent stops and defers to a human.
  Be concrete: "any journal entry", "before any outbound send" — not "risky actions".
- **Runtime enforcement (Claude Code Enforcement Gate, plugin v1.1+).** The gate reads the
  conventions below; everything else in this section is declared, not enforced:
  - `kill_switch.method: file` makes `endpoint` a sentinel-file path (relative to the manifest
    directory); while the file exists every gated tool call is denied (E1). Any other method
    keeps its meaning for your infrastructure and the gate uses the default sentinel
    `.claude/state/KILL`.
  - The `rate_limits` entry `{action: tool_call, max: N, period: session}` is the per-session
    tool-call budget (E4) — a runtime proxy for `spend_cap`, not a currency meter.
  - `irreversible_actions.deny_patterns[]` are Python regexes matched against Bash commands;
    a match is denied outright (E3) **regardless of** `irreversible_action_policy`, which
    governs everything the patterns do not name.
  - `protected_paths[]` are Python regexes matched against file-tool paths and Bash command
    text (E2), in addition to the built-in set (the manifest, `.claude/settings*.json`,
    `hooks.json`, the ledger, the call counter). Regex matching is a tripwire, not a sandbox.

**Critical gap:** missing `enforcement.kill_switch` (or a kill switch without `endpoint`/`method`)
→ **INVALID**. An agent that cannot be stopped must never be marked valid.

---

## [L] LEDGER — the immutable audit trail

**Crosscutting.** Accountability and transparency. The ledger is how any FIELD claim is verified
after the fact: what the agent did, when, under whose authority, at what cost.

**Constrains:** what is recorded, how it is made tamper-evident, and how long it is kept.

**Manifest fields:** `ledger.cryptographic_seal`, `ledger.seal_algorithm`, `ledger.retention_days`,
`ledger.logged_events[]`, `ledger.store`.

**Rules:**
- `cryptographic_seal` MUST be `true`. The schema pins it as a `const`. An unsealed ledger can be
  edited after the fact, which defeats the point.
- `seal_algorithm` names the tamper-evidence scheme (`sha-256-merkle`, `blake3-merkle`,
  `ed25519-signed-chain`, `sha-512-merkle`, `sha-256-chain`). `none` is not permitted.
- `retention_days` is set by jurisdiction. Financial/SOX work is typically 2555 days (7 years).
- `logged_events` is least-surprise: at minimum every action, every escalation, every delegation
  use, and (if a spend cap exists) every spend.
- `store` doubles as the Enforcement Gate's ledger location when it is path-like (`file://…`, a
  path containing a separator, `~/…`, or a bare `*.jsonl`); prose or a bucket/service description
  keeps its descriptive meaning and the gate falls back to `.claude/state/field-ledger.jsonl`.
  The gate's chain (`sha-256-chain`) is tamper-evident, not tamper-proof; `/field verify` checks it.

**Critical gap:** `cryptographic_seal` not `true`, or `seal_algorithm` of `none`/absent →
**INVALID**.

---

## [D] DELEGATION — the authorization chain

**Pillar: AI Sovereignty.** The chain of authority from a human principal down to the autonomous
agent. Governance treats the agent like a deputy with delegated authority — closer to how a
company governs an employee than how it governs software.

**Constrains:** what the agent was authorized to do, by whom, in what scope, until when, and how
that authority is revoked.

**Manifest fields:** `delegation.granted_by`, `delegation.scope[]`, `delegation.expiry`,
`delegation.revocation`.

**Rules:**
- `granted_by` is mandatory. It names who authorized the agent to act. Without it the agent has no
  legitimate authority — it is acting on its own account.
- `scope` enumerates the *specific* authorized actions. Broad grants ("do finance stuff") are a
  warning; enumerate concrete actions.
- `expiry` is mandatory. Standing grants use a far-future date but must be reviewed on a cadence;
  flag any expiry inside 30 days as a warning.
- `revocation` declares how the grant is pulled before expiry. Delegation you cannot revoke is
  delegation you cannot control.

**Critical gap:** missing `delegation.granted_by` → **INVALID** (no legitimate authority).

---

## Verdict rules (used by `/field validate`)

- **INVALID** if any critical gap is present: any of the five sections absent; no `identity.principal`;
  no `enforcement.kill_switch` (or missing `endpoint`/`method`); no `enforcement.irreversible_action_policy`;
  `ledger.cryptographic_seal ≠ true` or `seal_algorithm` of `none`; no `delegation.granted_by`;
  or a named federated peer with no `trust_basis`.
- **VALID_WITH_WARNINGS** — all five sections present and every critical rule passes, but non-blocking
  issues remain: unresolved `REPLACE-ME` placeholders, a missing `runtime_protocol`, a past or near-term
  `delegation.expiry`, or a named peer with no governing `contracts` entry. Warnings never downgrade a
  structurally valid manifest to INVALID.
- **VALID** — all five sections present, all critical rules pass, and no warnings remain.

---

## Composition with FORCE

FIELD wraps FORCE. A FIELD-governed agent declares its runtime protocol in the manifest:

```yaml
runtime_protocol:
  name: FORCE
  version: "1.0"
  preset: analysis   # analysis | brainstorm | draft | audit
```

Design-time (FIELD) and runtime (FORCE) compose and never conflict. If `runtime_protocol` is
absent, warn but do not fail — some single-purpose agents legitimately omit it.

---

## Full manifest example

A client-facing FP&A analyst agent, fully specified. Validates as **VALID** against
`manifest-schema.json`.

```yaml
# FIELD manifest — client-facing FP&A analyst agent
schema_version: field.spinstatelabs.ca/v1

agent:
  name: fp-analyst-client-alpha
  description: FP&A analyst agent producing variance narratives for Client Alpha
  version: "1.0.0"

# F — Federated. Not isolated: two authenticated peers, each under an explicit contract.
federated:
  isolated: false
  allowed_peers:
    - agent_id: anthropic.com
      org: Anthropic
      trust_basis: mTLS cert
    - agent_id: netsuite.com
      org: Oracle NetSuite
      trust_basis: mTLS cert
  contracts:
    - peer: anthropic.com
      contract_ref: agent-mcp-v1
      scope: model inference only — no client data retention
    - peer: netsuite.com
      contract_ref: agent-mcp-v1
      scope: variance metadata only — PII and raw documents never cross

identity:
  principal: don@spinstatelabs.ca
  org: spin-state-labs
  jurisdiction:
    - CA-ON
  data_scope:
    may_access:
      - client-alpha tier-A financial data (read)
    may_retain:
      - working analysis
    may_transmit:
      - variance metadata          # PII and raw documents are forbidden to cross
  model_provider: Anthropic

# E — Enforcement. Irreversible actions (posting a JE, emailing externally) need a human.
enforcement:
  kill_switch:
    endpoint: /admin/halt/fp-analyst-client-alpha
    method: HTTP POST
  spend_cap:
    currency: USD
    limit: 250
    period: monthly
    on_breach: halt
  escalation_triggers:
    - pii_access
    - external_send
    - amount_gt_10000
  rate_limits:
    - action: requests
      max: 30
      period: per-minute
    - action: actions
      max: 100
      period: per-hour
  irreversible_action_policy: require_human_approval

ledger:
  cryptographic_seal: true
  seal_algorithm: sha-256-merkle
  retention_days: 2555             # 7 years
  logged_events:
    - decisions
    - actions
    - delegations
    - refusals
    - escalations                  # raw prompts deliberately excluded
  store: s3://spin-state-audit/prod/client-alpha

# D — Delegation. Granted by the client's CFO; posting JEs and external email stay out of scope.
delegation:
  granted_by: cfo@client-alpha.com
  scope:
    - read_gl
    - generate_variance_narrative
    - email_to_cfo
  expiry: "2026-12-31T23:59:59Z"
  revocation:
    method: HTTP POST
    endpoint: /admin/revoke/fp-analyst-client-alpha

runtime_protocol:
  name: FORCE
  version: "1.0"
  preset: audit
```

---

*Spin State Labs · FIELD Framework v1.0 · field.spinstatelabs.ca/v1*
