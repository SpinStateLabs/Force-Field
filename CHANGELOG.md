# Changelog

All notable changes to plugins in this marketplace are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Adherence to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned

- FORCE v1.1 refinements based on real-world usage feedback.
- FIELD refinements: manifest examples per pillar, reference architectures; possible reference implementation of runtime enforcement in n8n.
- Enforcement Gate, next: policy-driven verdicts (`irreversible_action_policy` → deny / ask / allow-with-ledger), a locked call counter, a `kill_switch.local_sentinel` alongside an estate endpoint.
- Sample ledger stores (s3, Postgres) with cryptographic sealing wired.
- FORCE + FIELD runtime composition — automatic FORCE application inside FIELD-declared agents.

---

## field — 1.2.1 / marketplace — 1.4.1 — 2026-10-02

### Changed

- Schema descriptions only (no new keys, no validation change): `$comment` records revision 1.2.0; `deny_patterns` now says it matches Bash and PowerShell commands (case-insensitive for PowerShell); `session_written_exec` notes that PowerShell commands naming a session-written file are denied, reads included. They described 1.1 behaviour.

---

## field — 1.2.0 / marketplace — 1.4.0 — 2026-10-02

### Added

- **E5 session-written execution** (opt-in): with `enforcement.irreversible_actions.session_written_exec: deny`, the Enforcement Gate denies a Bash command that names a file the same session was allowed to write with a file tool (Write, Edit, MultiEdit, NotebookEdit), unless the command is one of a short list of read-only tools (`cat`, `ls`, `head`, `tail`, `less`, `more`, `wc`, `grep`, `rg`, `diff`, `stat`, `file`, `git`, `sha256sum`, `md5sum`, `chmod`, `echo`, `printf`, `test`). If a shell, interpreter or wrapper (`sudo`, `env`, `nohup`, `exec`, ...) appears anywhere in the command, every token is checked, which covers pipes (`cat x.sh | bash`), redirects (`bash < x.sh`), `-c` strings, subshells, `$(...)` and backticks. `session_written_exec_allow[]` regexes exempt root-relative paths (e.g. `'^approved/'`). Default `allow`: manifests without the key behave exactly as in 1.1.
- **Ledger write paths**: file-tool records now carry `path`. Inside the project it is the root-relative path; outside it is `sha256:<hex>` of the normalised absolute path. E5 deny reasons name the same key, never the raw command token.
- Schema (additive; `schema_version` unchanged): optional `session_written_exec` (`allow` | `deny`) and `session_written_exec_allow[]` under `enforcement.irreversible_actions`. Templates carry them as commented examples; the test fixture enables them.
- **All-tools gating**: the hook matcher is now `*`. Every tool except Read, Glob, Grep, LS, NotebookRead and TodoWrite is gated, including Claude Code's PowerShell tool on Windows and MCP tools. E1 kill switch, E4 budget and L ledger apply to all of them. E2 checks every string in an MCP tool's input. E3 and E5 apply to PowerShell commands as well as Bash; PowerShell has no parser, so E5 denies any PowerShell command that names a session-written file (reads included) and E2 checks each token. PowerShell text is normalised first (smart quotes and dashes to ASCII, escape backticks removed) and E3 matches it case-insensitively.
- Templates carry a commented PowerShell deny pattern (`Remove-Item ... -Recurse`).
- `hooks/test/run_e5.sh` (111 cases) and a CI job that runs it with the existing smoke test.

### Changed

- The gate takes an exclusive lock (`.claude/state/field-gate.lock`) for each call and writes the call counter atomically. Without it, parallel tool calls raced on the counter and the ledger: in a 40-call test, 28 were falsely denied with `E0` and left no ledger record. This was latent in 1.1; gating every tool made it common.
- Hook input whose `tool_name` is not a string denies with `E0` (it exited 1, which Claude Code treats as non-blocking). `E0` reasons for I/O errors name the error, not the file.
- E4 now counts every gated tool, MCP tools included, so a budget is used up faster than in 1.1. Raise `max` if needed.
- E1 and E2 deny reasons no longer contain absolute paths: E1 names the sentinel by its ledger key, and E2 names the ledger and call counter by label. E0 reasons no longer echo the kill-switch endpoint.
- New ledger files are created owner-only (0600) on POSIX; existing ledgers keep their permissions; no effect on Windows.
- Fail-closed fix (all rules, not only E5): with a manifest present, hook input that is not a JSON object now denies with `E0`. In 1.1 it was treated as an empty call and allowed. Claude Code always sends valid JSON, so this only matters if something else invokes the hook.
- Fail-closed extended: with E5 enabled, an unreadable ledger, an invalid `session_written_exec` value, a non-list or invalid `session_written_exec_allow`, or a command that cannot be tokenised denies with `E0`. E0 reasons name the exception class only, not file paths.
- Paths are matched case-insensitively on Windows (keys are stored case-folded; exemption regexes match case-insensitively there). Git Bash `/c/...` paths map to `C:/...`. On POSIX, symlinked project roots are resolved.

### Why

- Write-then-execute got past E3: an agent writes `cleanup.sh`, then runs `bash ./cleanup.sh`, which matches no deny pattern. Raised in public review of the 1.1 launch by Ridzwan Gigih Herdyantha, who also proposed the approach used here: have the ledger record the write path so Enforcement can answer "did this session create this file" with no new state (L feeding E).
- A live test in Claude Code 2.1.220 on Windows found that the PowerShell tool was not gated at all (1.1 and the first 1.2 draft): a command denied through Bash ran through PowerShell, with no ledger record, and the kill switch did not stop it. The all-tools change closes that.
- A second adversarial review of the all-tools change found PowerShell evasions (backtick escapes, smart quotes, en-dashes, `-Param:value`, `$PWD/x.sh`, upper-case `RM -RF`), E2 misses on MCP strings that did not end in the protected path, the parallel-call race, and a non-string `tool_name` that did not fail closed. All are fixed and covered by tests.
- A pre-merge adversarial review found eight issues in the first E5 draft (flag arguments hiding the script, quoted names, pipes/redirects/subshells, path-key mismatches on Windows and symlinked roots, a string exemption that exempted everything, a path in an E0 reason, `~` handling, a test-script platform check). All are fixed and covered by tests.

### Known limitations

- E5 matches command text, not process execution. Indirection gets through: a variable holding the path (`F=x.sh; bash $F`), `eval`, encoded payloads.
- Implicit execution gets through: programs that load a written file without naming it (`make` with a written Makefile, `npm test`, `pytest` with no arguments, git hooks).
- Only files written with file tools are tracked. Files created by Bash itself (`echo > x.sh`, `curl -o x.sh`) are not. This is the next gap.
- E5 is deliberately strict: any command outside the read-only list that names a written file is denied, including `cp`, `mv`, `sed -i`, `pytest test_x.py` and `python3 tool.py x.sh`. Use `session_written_exec_allow` for intended workflows.
- Paths resolve against the project root, not the shell's working directory (`cd sub && ./x.sh` is not matched to `sub/x.sh`).
- On Windows, Git Bash mount paths other than `/<drive>/...` (for example `/tmp/...`, `/home/...`) are not mapped to Windows paths, so a command naming a written file in that form is not matched.
- PreToolUse records a permitted write, not a completed one, so E5 can deny a file whose write failed (the safe direction).
- Records written by field 1.1.x carry no path, so writes made before the upgrade are not tracked.
- `sha256:` keys are unsalted: they keep plaintext out of the ledger but a guessed path can be confirmed against them.
- Deleting ledger lines hides a write from E5; `/field verify` detects the broken chain.
- MCP tools that run commands (for example a desktop shell server) get E1, E2, E4 and L, not E3 or E5: the gate cannot tell which input is a command.
- PowerShell checks are token-based, not parsed: string building (`"x" + ".sh"`), wildcards (`x.s?`), `-EncodedCommand`, variables, aliases and parameter abbreviations (`rm -r -fo`) get past E3 and E5. E5 over-blocks reads such as `Get-Content x.sh`, and any PowerShell input string (the description included) is checked.
- E2 on MCP tools checks every token of every input string, so an MCP call whose text merely mentions a governance file name (`hooks.json`) is denied (the safe direction).
- Read, Glob and Grep remain ungated, including while the kill switch is set.
- The ledger is read on every Bash call while E5 is on (linear in ledger size).

### Measured

- `bash hooks/test/run_e5.sh`: 111/111 pass; `bash hooks/test/run.sh`: unchanged (allow / E3 / E2 / E1, ledger intact). With E5 off, 16 edge-case inputs give identical exit codes, output and ledger records to 1.1.1 apart from the new `path` field (malformed hook input aside, which now denies). Python 3.12 on Linux, and Python 3.13 under Git Bash on Windows 11. Live, headless Claude Code 2.1.220 on Windows 11 (`--plugin-dir`, `bypassPermissions` and `default` modes) on the pre-all-tools build: E3, E5 (7 commands), E2, exemption, ledger paths and verify all as expected; the PowerShell gap above was found there. The all-tools build has not yet been run live.

---

## force — 1.0.2 / field — 1.1.1 / force-field — 1.0.0 / marketplace — 1.3.0 — 2026-09-30

### Added

- **`force-field` plugin (1.0.0)** (`plugins/force-field/`): umbrella for the Force-Field Protocol. Declares `force` and `field` as dependencies (Claude Code installs both with it) and adds a `force-field` skill explaining how the two layers compose. Instructions only: no hooks, scripts, MCP servers or network calls. On claude.ai and Cowork, plugin dependencies are not installed automatically; install `force` and `field` separately there.
- Listing icons for the Anthropic plugin directory: `.claude-plugin/icon.png` (1024×1024 PNG) in `force`, `field` and `force-field`.

### Changed

- `force` 1.0.1 → 1.0.2 and `field` 1.1.0 → 1.1.1: icon only, no functional change. Versions raised so the directory and `claude plugin update` pick up the new commit.

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
