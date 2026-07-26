# Changelog

All notable changes to plugins in this marketplace are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Adherence to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## marketplace — 1.1.0 — 2026-06-25

### Added

- FIELD plugin (v1.0.0) added to catalog.
- Marketplace description updated to reflect both FORCE (runtime) and FIELD (governance) layers.

---

## field — 1.0.0 — 2026-06-25

### Added

- Initial release of the FIELD governance framework plugin.
- Five constraints for agentic AI deployment:
  - **F** — Federation (multi-agent trust protocols)
  - **I** — Identity (attribution, jurisdiction, data scope)
  - **E** — Enforcement (kill switches, spend caps, escalation triggers)
  - **L** — Ledger (cryptographic immutable audit trail)
  - **D** — Delegation (authorization chain from principal to agent)
- `/field` slash command:
  - `/field` / `/field status` — display current manifest
  - `/field init [template]` — bootstrap manifest from template
  - `/field validate` — check manifest against JSON schema
  - `/field assess` — interactive five-letter compliance walkthrough
  - `/field audit` — generate audit-ready summary for external review
  - `/field export` — convert manifest to JSON
- Four manifest templates:
  - `default` — baseline for general use
  - `financial-agent` — FP&A, audit-adjacent, 7-year ledger retention
  - `read-only-agent` — retrieval and analysis with zero write scope
  - `client-facing-agent` — customer interactions with draft-only outbound
- JSON Schema (`manifest-schema.json`) for validation.
- Full framework reference (`framework.md`) with detailed manifest examples.
- FORCE composition — every FIELD manifest declares a `runtime_protocol` block; defaults to FORCE preset "analysis".

### Known limitations

- v1.0 is a manifest tool, not a runtime enforcer. Actual enforcement (kill switches firing, spend caps deducting, ledger writes) requires infrastructure the user builds around the manifest.
- Cryptographic sealing is declared in manifests but not implemented by this plugin — the configured ledger store must handle it.
- FORCE composition is asserted in v1.0 but not automatically wired — runtime application of FORCE alongside a FIELD-governed agent is separate infrastructure.
- Third-party audit format is `/field audit` output; independent verification is a separate service.

---

## [Unreleased] — Planned

- FIELD v1.1 — refinements based on real-world use; possible reference implementation of runtime enforcement in n8n.
- FORCE v1.1 — usage-driven refinements.
- Sample ledger stores (s3, Postgres) with cryptographic sealing wired.
- FORCE + FIELD runtime composition — automatic FORCE application inside FIELD-declared agents.

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

[Unreleased]: https://github.com/SpinStateLabs/Force-Field/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/SpinStateLabs/Force-Field/releases/tag/v1.1.0
[1.0.0]: https://github.com/SpinStateLabs/Force-Field/releases/tag/v1.0.0
