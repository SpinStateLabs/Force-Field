# ssl-fp-builder-1 plan (odd items of ROADMAP.md "Enforcement Gate v1.2")

Numbering (approved by Don) = ROADMAP.md bullet order:
Order is ROADMAP.md bullet order: 1 Policy verdicts | 2 local_sentinel | 3 FORCE+FIELD composition |
4 Ledger reference impls | 5 Additional FIELD templates | 6 n8n reference enforcement.
Builder-1 = 1, 3, 5. Builder-2 = 2, 4, 6.

## Status at HEAD 4a382bc (verified by grep of CHANGELOG.md, manifest-schema.json, field-gate.py, hooks.json)
- [x] 1 Policy-driven verdicts: ALREADY BUILT (schema 1.3.0 deny_patterns_verdict, gate E3 ask/allow-with-ledger, run_e3_policy.sh). No work; ROADMAP.md is stale.
- [ ] 3 FORCE+FIELD runtime composition: NOT BUILT. runtime_protocol is declared only; hooks.json has no SessionStart hook; CHANGELOG states "not automatically wired".
- [ ] 5 Additional FIELD templates: 4 exist (default, financial, read-only, client-facing). Which new agent types clients ask about: not in source -> needs Don's call.

## Work
- [ ] 3a Design: SessionStart hook reads ./field-manifest.yaml runtime_protocol, injects FORCE preset as additionalContext. Fail-open for context injection (gate stays fail-closed). Touches hooks.json, new hooks/field-force-compose.*, tests; avoid field-gate.py (shared with builder-2).
- [ ] 3b Tests in hooks/test (run_compose.sh), add to run_all.sh
- [ ] 3c CHANGELOG [Unreleased] + ROADMAP.md refresh (item 1 shipped)
- [ ] 5a Templates: pending Don's list of agent types
