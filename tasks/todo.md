# ssl-fp-builder-1 plan (odd items of ROADMAP.md "Enforcement Gate v1.2")

Numbering (approved by Don) = ROADMAP.md bullet order:
Order is ROADMAP.md bullet order: 1 Policy verdicts | 2 local_sentinel | 3 FORCE+FIELD composition |
4 Ledger reference impls | 5 Additional FIELD templates | 6 n8n reference enforcement.
Builder-1 = 1, 3, 5. Builder-2 = 2, 4, 6.

## Status at HEAD 4a382bc (verified by grep of CHANGELOG.md, manifest-schema.json, field-gate.py, hooks.json)
- [x] 1 Policy-driven verdicts: ALREADY BUILT (schema 1.3.0 deny_patterns_verdict, gate E3 ask/allow-with-ledger, run_e3_policy.sh). No work; ROADMAP.md is stale.
- [x] 3 FORCE+FIELD runtime composition: BUILT on this branch (was NOT BUILT at HEAD). runtime_protocol is declared only; hooks.json has no SessionStart hook; CHANGELOG states "not automatically wired".
- [x] 5 Additional FIELD templates (done on this branch): 4 exist (default, financial, read-only, client-facing). Which new agent types clients ask about: not in source -> needs Don's call.

## Work
- [x] 3a Design: SessionStart hook reads ./field-manifest.yaml runtime_protocol, injects FORCE preset as additionalContext. Fail-open for context injection (gate stays fail-closed). Touches hooks.json, new hooks/field-force-compose.*, tests; avoid field-gate.py (shared with builder-2).
- [x] 3b Tests in hooks/test (run_compose.sh), add to run_all.sh
- [x] 3c CHANGELOG [Unreleased] + ROADMAP.md refresh (item 1 shipped)
- [x] 5a Templates: ssl-fp-builder, ssl-fp-reviewer, ssl-fp-coordinator (types named by Don). Schema-valid (jsonschema Draft 2020-12); deny patterns tested against allow/deny command samples.

## Review
- run_all.sh: ALL GATE SUITES PASSED on posix (incl. new run_compose.sh, 13 PASS). Windows leg runs in CI only (not run here).
- run_post_hook.sh registration assertion updated for the SessionStart event (it failed until then; baseline passed).
- Not verified: live Claude Code SessionStart injection (no claude CLI session here); only the hook contract is tested.

## Item 6 (n8n reference enforcement) -- deferred 2026-11-05, taken by the principal 2026-11-06
- [x] Core decision logic (field-gate-core.js): E1, E3 + policy, E4, ledger; fail-closed
- [x] build_workflow.py / manifest_to_json.py / generated workflow (6 nodes, header-auth webhooks)
- [x] Tests: decisions, differential vs field-gate.py, known-gap assertions, ledger parity, workflow sync + stubbed Code-node run
- [x] Mutation checks: disabling E1 or E3 makes tests fail
- [x] README with limits; CHANGELOG [Unreleased]; ROADMAP; CI step (Linux job)
- [x] Live n8n 2.46.6: import OK; Field Gate Code node executed via `n8n execute` (4 decisions correct; crypto builtin must be allowed)
- [ ] Not done: webhook activation + HTTP calls (starting a local n8n server was denied by the session classifier)

## Estate Connector (2026-11-07, branch claude/epic-pasteur-ccfdgv)
- [x] userConfig: estate_mode (local|estate, default local), estate_url, field_api_key (sensitive)
- [x] .mcp.json + connector/estate_connector.py (local: no network, estate_status tool; estate: Streamable-HTTP proxy, Bearer key)
- [x] Tests: connector/test/run_connector.sh (13 PASS) + CI step; run_all.sh ALL GATE SUITES PASSED; plugin validate --strict passed
- [x] Live check, Claude Code 2.1.319: both modes connected in `claude mcp list`; wrong key -> -32002 auth error; key stored in ~/.claude/.credentials.json
- [ ] Not done: test against the real FIELD platform estate (endpoint path, auth scheme, tool names not in this repo; Bearer assumed)
- [ ] Not done: release (version bump; the plugin cache is keyed by version, so existing 2.2.0 installs will not see this until a bump) -- plugin-agent release, principal's call
