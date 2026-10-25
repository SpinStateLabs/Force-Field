# Force Field — local-session handoff (2026-10-21)

Scope decided by Don: everything in ROADMAP "What's next". Run locally, not cloud.

## State at handoff
- main = 838b766 (field 1.2.4, marketplace 1.4.4). FORCE 1.0.2 and umbrella 1.0.0 are shipped.
- Open draft PR #7 (ci: ajv manifest validation) awaits Don's approval (ADR-0073, Proposed).
- Stale-prompt check: docs/FORCE_PROMPT.txt matches the shipped protocol; manifest schema_version
  `field.spinstatelabs.ca/v1` is consistent across templates; no stale version refs in READMEs/SKILL.md.
- Unmerged remote branches are all pre-1.2.4 fixes already on main or superseded; verify with
  `git cherry origin/main <branch>` before deleting:
  claude/field-gate-launcher-fail-closed, claude/field-gate-v1-1-integration-7u50hv (0 ahead),
  docs/e5-strictness-throttle-proposal (1 ahead: keep, a proposal), feat/field-gate-e5-session-exec,
  fix/e2-shell-tokens-path-normalise, fix/e5-path-qualified-command-word, fix/field-schema-1.2-text.

## Work order (one PR each, per CONTRIBUTING.md; bump versions + CHANGELOG)
1. Gate policy verdicts: `irreversible_action_policy` deny / ask / allow-with-ledger (field 1.3.0). Extend schema additively, tests in plugins/field/hooks/test.
2. `kill_switch.local_sentinel` alongside estate endpoint (same release).
3. FORCE+FIELD runtime composition: auto-apply FORCE inside FIELD-declared agents (reads `runtime_protocol`).
4. Ledger reference stores: s3 and Postgres with sealing wired; verify via verify-ledger.py.
5. Additional FIELD templates (ask Don which client agent types).
6. n8n reference enforcement workflow (optional per roadmap).
7. Landing page spinstatelabs.ca/field is outside this repo.
8. Close-out: sync ROADMAP (v2.3) and CHANGELOG Unreleased.

## Open decisions for Don
- Merge #7? Template list for item 5? n8n item in or out?
- Conformance Sentinel (Nov 2026 GA) lives in field-platform, not here.

## Local start
git fetch origin && git checkout claude/upbeat-carson-2wqhg5 (or main), read this file, then CHANGELOG [Unreleased].
