# Changelog

All notable changes to plugins in this marketplace are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Adherence to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned

- FORCE v1.1 refinements based on real-world usage feedback.
- FIELD refinements: manifest examples per pillar, reference architectures; possible reference implementation of runtime enforcement in n8n.
- Enforcement Gate v1.2: policy-driven verdicts (`irreversible_action_policy` → deny / ask / allow-with-ledger), a locked call counter, a `kill_switch.local_sentinel` alongside an estate endpoint.
- Sample ledger stores (s3, Postgres) with cryptographic sealing wired.
- FORCE + FIELD runtime composition — automatic FORCE application inside FIELD-declared agents.

---

## field — 1.1.0 / marketplace — 1.2.0 — 2026-09-12

### Added

- **Enforcement Gate** (`plugins/field/hooks/`): a Claude Code `PreToolUse` hook, auto-loaded from `hooks/hooks.json`, that reads `./field-manifest.yaml` and enforces it at runtime:
  - E1 kill switch — sentinel file (`enforcement.kill_switch.endpoint` when `method: file`, otherwise `.claude/state/KILL`); while it exists every gated tool call is denied.
  - E2 protected paths — built-in governance set (the manifest, `.claude/settings*.json`, `hooks.json`, the ledger, the call counter) plus `enforcement.protected_paths` regexes; Edit / Write / MultiEdit / NotebookEdit paths and Bash command text.
  - E3 irreversible actions — `enforcement.irreversible_actions.deny_patterns` regexes on Bash commands, denied outright regardless of `irreversible_action_policy`.
  - E4 call budget — the `enforcement.rate_limits` entry `{action: tool_call, period: session}`; a per-session tool-call ceiling that proxies the spend cap.
  - L ledger — every decision appended to `ledger.store` (when path-like) or `.claude/state/field-ledger.jsonl`, sha-256 hash-chained; `hooks/verify-ledger.py` checks the chain.
  - Fail-closed: an unreadable manifest, missing PyYAML, a misconfigured file kill switch, or an internal error denies with rule `E0` (exit 2). Without a manifest the hook does nothing.
- `/field kill`, `/field resume`, `/field verify`; `/field status` reports whether the gate is armed. `hooks/test/` ships a schema-valid fixture and a smoke test (`bash hooks/test/run.sh`).
- Schema (additive; `schema_version` unchanged, every v1 manifest stays valid): optional `enforcement.irreversible_actions.deny_patterns` and `enforcement.protected_paths`; `seal_algorithm` gains `sha-256-chain`; descriptions document the `file` kill-switch, `tool_call` rate-limit and path-like `ledger.store` conventions. All four templates carry a live `tool_call` budget, the `file` method hint, and commented gate examples.

### Changed

- Limitations rewritten (SKILL.md, README): Enforcement and Ledger are runtime-enforced in Claude Code (E1–E4, L); the spend cap remains a tool-call proxy; the ledger hash chain is tamper-evident, not tamper-proof. Federated, Identity and Delegation remain declared, not enforced.
- Once a manifest exists the gate treats it as a protected path, so `/field init` / `/field assess` write `field-manifest.draft.yaml` for the human to move into place; `/field resume` is out-of-band by design (the agent cannot remove its own sentinel).
- INSTALL.md: the gate ships only via the plugin install (Method A); `python3` + PyYAML required.

### Measured (Claude Code 2.1.269, headless `claude -p`, plugin loaded from source)

- In both `bypassPermissions` and `default` modes: Bash `rm -rf /tmp/x` denied (`[E3]`); Edit and Write of `.claude/settings.json` denied (`[E2]`); Edit of `field-manifest.yaml` denied (`[E2]`); every gated call denied while the sentinel exists (`[E1]`) and allowed again once removed. The hook's reason reached the model as the tool error, targets were untouched, and the ledger verified intact after every run.
- Caveat: Claude Code validates `.claude/settings.json` edits before hooks run — an edit producing invalid settings is rejected by Claude Code itself and never reaches the gate. Either way the file is not modified.
- E4 was exercised in the model-free layer only.

### Known limitations

- Regex matching is a tripwire, not a sandbox (`/bin/rm`, `python -c`, heredocs evade E3; Bash redirects evade E2's file-tool protection). Read, Glob and Grep are not gated.
- One `kill_switch` per manifest: an agent registered with an HTTP kill switch keeps it and gets the default local sentinel, not a manifest-chosen one.
- The per-session call counter is not locked against parallel tool calls.
- `hooks.json` invokes `python3`; on Windows make sure `python3` resolves, or the hook cannot start and nothing is enforced.

---

## field — 1.0.3 / marketplace — 1.1.3 — 2026-08-29

### Added

- `framework.md`: restored the "Full manifest example" (client-facing FP&A analyst agent), ported from the pre-merge apiVersion/kind dialect to the schema_version dialect and validated against `manifest-schema.json` (draft 2020-12). Notable translations: `federation` → `federated` with per-peer `trust_basis` and per-contract scopes; old `sha256-chained` seal → schema-enumerated `sha-256-merkle`; flat rate limits → per-action entries; `scope_forbidden` folded into comments (not a schema field).

### Fixed

- `marketplace.json`: the `field` catalog entry's per-plugin version had been left at 1.0.1 in the 1.1.2 release; now synchronized.

---

## field — 1.0.2 / marketplace — 1.1.2 — 2026-08-29

### Changed

- Version bump so `claude plugin update` delivers the reconciled content merged in ef17048: the Federated-dialect FIELD skill (schema_version manifests, `federated` key, updated templates and schema) replaced the pre-merge plugin content, and the obsolete apiVersion/kind-dialect `templates/` directory was removed. No functional change beyond what ef17048 already shipped — 1.0.1 installs predating the merge were stale.

---

## marketplace — 1.1.0 — 2026-06-25

### Added

- FIELD plugin (v1.0.0) added to catalog.
- Marketplace description updated to reflect both FORCE (runtime) and FIELD (governance) layers.

---

## field — 1.0.0 — 2026-07-29

### Added

- Initial release of the FIELD governance framework skill for agentic AI.
- Five governance letters: **F**ederated, **I**dentity, **E**nforcement, **L**edger, **D**elegation.
- `/field` slash command:
  - `/field` / `/field status` — skill state + working manifest
  - `/field on` / `/field off` — master toggle (proactive vs passive)
  - `/field init [template]` — bootstrap a `./field-manifest.yaml`
  - `/field validate` — check the manifest against `manifest-schema.json` + critical-gap rules
  - `/field assess` — walk the five letters interactively
  - `/field audit` — audit-ready summary for external review
  - `/field export [json|yaml]`, `/field template <name>`, `/field reset`
- JSON Schema (`manifest-schema.json`, draft 2020-12) enforcing the non-negotiables: a kill switch, a delegation grantor, an identity principal, and a cryptographically sealed ledger.
- Four bootstrap manifest templates: `default`, `financial-agent` (7-year sealed ledger, spend-cap-tied kill switch), `read-only-agent` (zero write scope), `client-facing-agent` (draft-only, no autonomous send).
- Stable skill state at `~/.claude/state/field.json` with a `./.claude/state/field.json` project override — same convention as FORCE.
- Composition with FORCE: manifests declare a `runtime_protocol` block; FIELD (design-time) wraps FORCE (runtime).
- Manual installers (`install.ps1`, `install.sh`) and `INSTALL.md` for air-gapped / pre-publish deployment.

### Known limitations

- FIELD v1.0 is a manifest tool, not a runtime enforcer. It generates and validates the governance spec; kill switches, ledger writes, and spend caps require infrastructure built around the manifest.
- Cryptographic sealing is declared in manifests but not implemented by this plugin — the configured ledger store must handle it.
- FORCE composition is asserted in v1.0 but not automatically wired — runtime application of FORCE alongside a FIELD-governed agent is separate infrastructure.
- `/field audit` produces an audit-ready report; independent certification is a separate service.

---

## force — 1.0.0 — 2026-06-25

### Added

- Initial release of the FORCE protocol skill.
- Five toggleable components: Forbid Flattery (F), Oppose Premise (O), Reference Sources (R), Chain-of-Thought (C), Express Uncertainty (E).
- `/force` slash command for state management:
  - `/force` / `/force status` — display current state
  - `/force on` / `/force off` — master toggle
  - `/force {F|O|R|C|E} {on|off}` — individual component toggle
  - `/force preset {analysis|brainstorm|draft|audit}` — apply preset configurations
  - `/force reset` — restore defaults
- Stable state file at `~/.claude/state/force.json` (survives plugin updates).
- Project-level state override via `./.claude/state/force.json` (takes precedence over user state when present).
- Auto-activation for analytical work when master is ON.

### Known limitations

- State management depends on the skill correctly reading/writing the state file. If the file path is inaccessible or permissions are wrong, toggles silently fail. The slash command confirms state after every change — verify the confirmation matches what was set.
- Claude.ai compatibility: this plugin is Claude Code only. For Claude.ai, use the system prompt template from [spinstatelabs.ca/force](https://spinstatelabs.ca/force).

---

[Unreleased]: https://github.com/SpinStateLabs/Force-Field/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/SpinStateLabs/Force-Field/releases/tag/v1.2.0
[1.1.0]: https://github.com/SpinStateLabs/Force-Field/releases/tag/v1.1.0
[1.0.0]: https://github.com/SpinStateLabs/Force-Field/releases/tag/v1.0.0
