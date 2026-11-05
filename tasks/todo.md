# ssl-fp-builder-2 plan

Source backlog (changed by the principal): ROADMAP.md "Enforcement Gate v1.2" bullets, in listed order.
Split: builder-2 takes EVEN bullets (2, 4, 6); builder-1 takes ODD (1, 3, 5).
Constraint (plugin-agent.md): no push, tag, release or portal action without an explicit "go" in chat;
do not edit LICENSE, CI workflows, the FIELD manifest or `.claude/state/`.

## Status of each bullet (verified in repo at main 4a382bc)
- [x] 2. `kill_switch.local_sentinel` -- ALREADY IMPLEMENTED (CHANGELOG [Unreleased], ADR-0072; schema 1.4.0;
      `plugins/force-field/hooks/field-gate.py` `kill_switch_path` and its local_sentinel helper;
      framework.md lines 94-97). ROADMAP.md still lists it as "next": stale. Needed: a ROADMAP wording fix
      (proposal only, plugin-agent.md says do not change existing wording unasked) -- no code.
- [ ] 4. Ledger reference implementations (s3, Postgres, cryptographic sealing wired) -- NOT started in repo
      (CHANGELOG lines 93-94 list it as planned). New feature surface; needs principal decision on scope.
- [ ] 6. n8n reference runtime enforcement (marked "possible" in ROADMAP) -- NOT started. Same.

## Review
(pending)
