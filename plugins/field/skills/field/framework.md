# FIELD Framework Reference

The governance layer of the Force Field Protocol. Each letter constrains a distinct dimension of agentic AI deployment.

---

## [F] FEDERATION

**What it constrains:** how agents from different organizations, ownership structures, or trust domains interoperate.

**Concrete concerns:**
- Which peers is this agent allowed to communicate with?
- What contract schema governs those interactions?
- How does this agent verify the identity of a peer?
- What data crosses trust boundaries; what stays sovereign?

**Manifest section:**

```yaml
federation:
  trust_boundary: "spin-state-labs"          # the org this agent belongs to
  allowed_peers:                              # explicit allowlist — empty means isolated
    - "stripe.com"
    - "anthropic.com"
  contract_schema: "agent-mcp-v1"             # how peers negotiate scope
  peer_verification: "mtls"                   # mtls | oauth | api_key | none
  data_crossing:                              # what can leave the sovereign domain
    allowed: ["transaction_ids", "amounts"]
    forbidden: ["pii", "raw_documents"]
```

---

## [I] IDENTITY

**What it constrains:** attribution. Every autonomous agent represents a principal — a human or organization whose interests it serves. Identity nails down who that is.

**Concrete concerns:**
- Who is the principal this agent acts on behalf of?
- What organization does it belong to?
- What jurisdiction governs its operation?
- What data scope is it authorized to touch?

**Manifest section:**

```yaml
identity:
  principal: "don@spinstatelabs.ca"           # the human or role the agent represents
  org: "spin-state-labs"                      # the org that operates the agent
  jurisdiction: "CA-ON"                       # regulatory regime (ISO 3166-2)
  data_scope: "client-tier-A"                 # which classification of data it can touch
  agent_id: "fp-analyst-2026-06"              # stable identifier for the agent
  version: "1.0.0"                            # version of the agent's spec
```

---

## [E] ENFORCEMENT

**What it constrains:** runtime harnessing. Autonomous agents need brakes and rails. Enforcement defines what stops the agent, what pauses it, and what it structurally cannot do.

**Concrete concerns:**
- What is the kill switch endpoint?
- What is the maximum spend before the agent halts?
- Which actions trigger mandatory human escalation?
- Which actions are irreversible and require confirmation?

**Manifest section:**

```yaml
enforcement:
  kill_switch: "/admin/halt/fp-analyst-2026-06"    # URL to halt the agent immediately
  spend_cap_usd: 500                                # max cumulative spend before halt
  spend_reset: "monthly"                            # daily | weekly | monthly | never
  escalation_triggers:                              # any of these pause for human review
    - "pii_access"
    - "external_send"
    - "amount_gt_10000"
  irreversible_actions:                             # explicit confirmation required
    - "deploy"
    - "delete"
    - "post_je"
  rate_limits:
    requests_per_minute: 60
    actions_per_hour: 200
```

---

## [L] LEDGER

**What it constrains:** the cryptographic immutable audit trail. If it isn't logged, it didn't happen — and if the record can be edited after the fact, the audit is theatre. Ledger writes tamper-evident, cryptographically sealed records that neither the agent nor the operator can rewrite.

**Concrete concerns:**
- Where does the ledger live?
- How long is it retained?
- Which cryptographic sealing algorithm secures it? (No longer "is it sealed?" — sealing is baseline in v1.0.)
- What events get logged?
- Who holds the verification keys, and how is tampering detected?

**Manifest section:**

```yaml
ledger:
  store: "s3://spin-state-audit/prod/fp-analyst-2026-06"
  retention_days: 2555                              # 7 years for financial audit
  cryptographic_seal: true                          # tamper-evident hashing
  seal_algorithm: "sha256-chained"                  # sha256-chained | merkle
  includes:                                          # what gets logged
    - "decisions"
    - "actions"
    - "delegations"
    - "refusals"
    - "escalations"
  excludes:                                          # explicitly not logged
    - "raw_prompts"                                  # for privacy — decisions only
  external_verifier: "https://audit.spinstatelabs.ca/verify"
```

---

## [D] DELEGATION

**What it constrains:** the authorization chain from human principal to autonomous agent. Without a clear delegation chain, there is no sovereignty — the agent is a black box acting in someone's name.

**Concrete concerns:**
- Who granted this agent authority?
- What is the scope of that authority?
- When does the delegation expire?
- How is it revoked?

**Manifest section:**

```yaml
delegation:
  granted_by: "cfo@client.com"                      # the human principal
  granted_at: "2026-06-25T09:00:00Z"                # when authority was granted
  scope:                                             # explicit list of authorized actions
    - "read_gl"
    - "post_je_amount_lt_10000"
    - "generate_variance_narrative"
    - "email_to_designated_recipients"
  scope_forbidden:                                   # explicit deny — belt and suspenders
    - "modify_coa"
    - "post_je_amount_gte_10000"
    - "email_external"
  valid_until: "2026-12-31T23:59:59Z"                # explicit expiry
  revocation_url: "/admin/revoke/fp-analyst-2026-06" # how to kill delegation
  chain_of_authority:                                # transitive delegations
    - principal: "cfo@client.com"
      delegated_to: "don@spinstatelabs.ca"
      via: "client-msa-v1"
    - principal: "don@spinstatelabs.ca"
      delegated_to: "fp-analyst-2026-06"
      via: "spin-state-internal"
```

---

## Composition with FORCE

FIELD manifests SHOULD declare which runtime prompt protocol the agent applies. Default: FORCE.

```yaml
runtime_protocol:
  name: FORCE
  version: 1.0
  preset: "analysis"                                # analysis | brainstorm | draft | audit
  components:                                       # override individual components if needed
    F: true
    O: true
    R: true
    C: true
    E: true
```

Absence of `runtime_protocol` is a WARNING but not a FAILURE — some agents (single-purpose, highly constrained) may not need FORCE.

---

## Full manifest example

```yaml
# Example: FIELD manifest for a client-facing FP&A analyst agent
apiVersion: field.spinstatelabs.ca/v1
kind: FieldManifest
metadata:
  name: "fp-analyst-client-alpha"
  created: "2026-06-25T09:00:00Z"
  updated: "2026-06-25T09:00:00Z"

federation:
  trust_boundary: "spin-state-labs"
  allowed_peers: ["anthropic.com", "netsuite.com"]
  contract_schema: "agent-mcp-v1"
  peer_verification: "mtls"
  data_crossing:
    allowed: ["variance_metadata"]
    forbidden: ["pii", "raw_documents"]

identity:
  principal: "don@spinstatelabs.ca"
  org: "spin-state-labs"
  jurisdiction: "CA-ON"
  data_scope: "client-alpha-tier-A"
  agent_id: "fp-analyst-client-alpha"
  version: "1.0.0"

enforcement:
  kill_switch: "/admin/halt/fp-analyst-client-alpha"
  spend_cap_usd: 250
  spend_reset: "monthly"
  escalation_triggers: ["pii_access", "external_send", "amount_gt_10000"]
  irreversible_actions: ["post_je", "email_external"]
  rate_limits:
    requests_per_minute: 30
    actions_per_hour: 100

ledger:
  store: "s3://spin-state-audit/prod/client-alpha"
  retention_days: 2555
  cryptographic_seal: true
  seal_algorithm: "sha256-chained"
  includes: ["decisions", "actions", "delegations", "refusals", "escalations"]
  excludes: ["raw_prompts"]

delegation:
  granted_by: "cfo@client-alpha.com"
  granted_at: "2026-06-25T09:00:00Z"
  scope: ["read_gl", "generate_variance_narrative", "email_to_cfo"]
  scope_forbidden: ["modify_coa", "post_je", "email_external"]
  valid_until: "2026-12-31T23:59:59Z"
  revocation_url: "/admin/revoke/fp-analyst-client-alpha"

runtime_protocol:
  name: FORCE
  version: 1.0
  preset: "audit"
```

---

*Spin State Labs · FIELD Framework Reference v1.0*
