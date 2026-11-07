# ssl-fp-builder-2 plan

Source backlog (principal's choice): ROADMAP.md "Enforcement Gate v1.2" bullets; builder-2 = EVEN (2, 4, 6), builder-1 = ODD.
Constraint (plugin-agent.md): no push, tag, release or portal action without an explicit "go" in chat;
do not edit LICENSE, CI workflows, the FIELD manifest or `.claude/state/`.

- [x] 2. `kill_switch.local_sentinel` -- already implemented (ADR-0072, schema 1.4.0). ROADMAP.md wording fixed on this branch (principal approved "apply", 2026-11-05).
- [x] 4. Ledger reference implementation -- `plugins/force-field/ledger/` (ledger_ship.py, schema.sql, README.md) and
      `plugins/force-field/hooks/test/test_ledger_ship.py`. Principal "go" 2026-11-05: build, scoped to tested sinks.
- [x] 6. n8n reference runtime -- not built by builder-2: deferred (2026-11-05), then skipped by the principal (2026-11-07). The bullet shipped separately in force-field 2.2.0 (PR #31).
- [x] Live S3 test of the ledger shipper -- skipped by the principal (2026-11-07). The S3 sink stays tested against moto only; recorded in CHANGELOG [Unreleased].

## Review
- 17 tests pass with deps (dir, S3 via moto, real Postgres 16); 8 pass, 9 skipped stdlib-only. Mutation check: disabling
  the HMAC comparison makes the tests fail.
- Not verified: live AWS S3, Windows, other Postgres versions. Not added to run_all.sh/CI (CI files are off limits).
- No change to gate code, schema, manifest or CHANGELOG. ROADMAP.md wording changed (see PR #20).
