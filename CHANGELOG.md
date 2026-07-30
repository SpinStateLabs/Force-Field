# Changelog

All notable changes to plugins in this marketplace are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Adherence to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned

- FORCE v1.1 refinements based on real-world usage feedback.
- FIELD v1.1 refinements: manifest examples per pillar, reference architectures, optional runtime-enforcement hooks.

---

## field — 1.0.0 — 2026-07-29

### Added

- Initial release of the FIELD governance framework skill for agentic AI.
- Five governance letters: **F**ederation, **I**dentity, **E**nforcement, **L**edger, **D**elegation.
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

[Unreleased]: https://github.com/SpinStateLabs/Force-Field/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SpinStateLabs/Force-Field/releases/tag/v1.0.0
