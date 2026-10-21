# Changelog

All notable changes to plugins in this marketplace are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Adherence to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned

- FORCE v1.1 refinements based on real-world usage feedback.
- FIELD refinements: manifest examples per pillar, reference architectures; possible reference implementation of runtime enforcement in n8n.
- Enforcement Gate, next: policy-driven verdicts (`irreversible_action_policy` → deny / ask / allow-with-ledger), a `kill_switch.local_sentinel` alongside an estate endpoint. (The locked call counter shipped in 1.2.0.)
- Sample ledger stores (s3, Postgres) with cryptographic sealing wired.
- FORCE + FIELD runtime composition — automatic FORCE application inside FIELD-declared agents.

---

## field — 1.2.4 / marketplace — 1.4.4 — 2026-10-18

### Fixed

- **The gate failed open when Python could not start (high).** `hooks.json` ran `python3` directly. Claude Code treats a hook exit other than 0 or 2 as a non-blocking error and runs the tool, so with no `python3` on PATH (exit 127), or with only the Windows Store alias stub (exit 9009; a python.org install provides `python` and `py`, not `python3`), nothing was enforced and nothing was ledgered, silently. `hooks.json` now runs `sh "${CLAUDE_PLUGIN_ROOT}/hooks/field-gate.sh"`, a POSIX launcher that tries `python3`, then `py -3`, then `python`, with the hook input replayed to each. Exit 0 or 2 is the gate's verdict and passes through; an exit of 1-127 means that interpreter never ran the gate, so the next is tried; 128 or more means the gate was killed mid-run, so nothing is retried (a retry could count the call twice). With no verdict, the call is denied with E0 when the project has a manifest and allowed when it has none, so a missing Python does not block projects that are not FIELD-governed. A missing `field-gate.py` (Python exits 2 for it) is no longer taken as a deny verdict. Decision record: force-field-agentic-harness ADR-0070.
- **The gate could exit 1 after it ran (medium).** An exception outside `main()`'s handlers (for example in the manifest lookup) exited 1, which is non-blocking: fail-open in a governed project. A deny whose stdout write failed (Claude Code gone, the hook timed out) also exited 1, after the ledger record was written. `field-gate.py` now exits only 0 or 2 once it runs: a `__main__` guard maps anything else to 2, and `emit_deny` survives a closed stdout or stderr. The launcher's retry rule depends on this.
- `.gitattributes` keeps `*.sh` at LF on every checkout: a CRLF `field-gate.sh` is a syntax error (exit 2) under `sh` and would block every gated call in every project.

### Known limits

- An E0 denial from the launcher leaves no ledger record (nothing could write it).
- Claude Code on Windows without Git Bash runs hooks in PowerShell, where `sh` does not start: still a non-blocking error, nothing enforced. Install Git for Windows. Claude Code 2.1.295+ documents `"onFailure": "block"` for this case, but on any host where the hook cannot start it would also block every project without a manifest; not adopted (ADR-0070).
- The launcher looks for the manifest under `$CLAUDE_PROJECT_DIR`, else its working directory; unlike `field-gate.py` it does not read the hook input's `cwd`. `FIELD_MANIFEST` starting with `/`, `\` or `\\`, or a drive letter, is taken as absolute.
- A program named `py` or `python` that is not Python and happens to exit 0 or 2 would be trusted.

### Verification

- `bash hooks/test/run_launcher.sh`: 25/25. Covers: no interpreter with and without a manifest; `FIELD_MANIFEST` relative, absolute and missing; a Store-style stub that consumes stdin and exits 49 plus a broken `py`, then `python` runs the gate with the input intact and one ledger record per call; `py -3`; pass-through of allow and deny; a 200 KB input; a deny whose stdout reader is gone (exit 2, one ledger record, no retry); a gate killed after it ran (E0, one record, no retry); a missing `field-gate.py`; an exception outside `main()`'s handlers (exit 2). Without the `field-gate.py` change, the closed-stdout case writes two ledger records and the exception case exits 1. `run.sh` and `run_e5.sh` unchanged and passing. Python 3.13, dash, Linux.
- Live, headless Claude Code 2.1.302 on Linux (`--plugin-dir`, `bypassPermissions`), final build: with Python, a destructive command is denied and `echo hi` is allowed and ledgered; with Python removed from PATH, `echo hi` is denied with E0 in a project with a manifest and allowed in one without. The 1.2.3 `hooks.json` under the same Python-free PATH ran `echo hi` with no ledger: the failure reproduced. In 2.1.302 a hook denial also appears in `permission_denials`.
- Windows 10 (build 19045), rog-command, Git Bash (MINGW64 3.6.5), Microsoft Store Python 3.14.2 with PyYAML 6.0.3 as `python3` and `py`, python.org 3.14.5 as `python`:
  - The PR branch cloned with `.gitattributes` honoured (`i/lf w/lf`).
  - `check_host.sh`: ENFORCED (allow 0, `rm -rf build` denied E3).
  - Live headless Claude Code, `--plugin-dir`, `bypassPermissions`:
    - Bash `echo hi` ran.
    - Bash `rm -rf build` denied E3.
    - **PowerShell** `Remove-Item -Recurse -Force build` denied E3. This was the first live Windows run of all-tools gating.
    - PowerShell `Get-Date` with the kill sentinel present denied E1.
    - Four ledger records.
  - The first suite run there failed 4 allow cases with E0 "PyYAML missing". The tests' `env -i` had removed `LOCALAPPDATA`, where the Store Python keeps per-user packages. The gate failed closed correctly; the test was wrong. The tests now keep HOME, USERPROFILE, LOCALAPPDATA, APPDATA, SYSTEMROOT, WINDIR, TEMP and TMP, and strip only PATH. The suite has not been re-run on Windows after that change.

---

## field — 1.2.3 / marketplace — 1.4.3 — 2026-10-12

### Fixed

- **E2 tokenises shell commands (F1, high).** For Bash, E2 matched the protected-path regexes (all anchored with `$`) against the whole command text only, so `rm field-manifest.yaml; true`, `echo x > field-manifest.yaml; true`, `mv field-manifest.yaml /tmp/m && ls` and `rm -f .claude/state/field-ledger.jsonl; ls` were allowed; with the manifest gone the gate no-ops. E2 now parses the command (shlex, quotes and escapes resolved, redirection operators split off, pipelines kept) and checks every unquoted word, keeps the whole-string match, and checks quoted words where they can reach a file: arguments of a mutating command (`rm`, `rmdir`, `unlink`, `shred`, `mv`, `ln`, `tee`, `truncate`, `chmod`, `chown`, `chattr`, `cp`/`install` destination, sources too when the destination is a governance path, `dd of=`, `sed -i`/`perl -i`), redirect targets, and command strings that a shell `-c`, `eval`, `su -c`, or a wrapper (`sudo`, `env`, `timeout`, `xargs`, ...) runs, re-analysed as commands three levels deep (`sh -c 'rm field-manifest.yaml;true'`, `sudo sh -c "..."`, `bash -lc "..."`). Glob and brace words in those same positions are expanded against the real governance paths (`rm *.yaml`, `rm field-manifest.*`, `rm {field-manifest,x}.yaml`, `rm -r .claude/*`, `rm *` at the project root, `mv *.yaml /tmp`, `chmod 600 *.yaml`, `sed -i s/a/b/ *.yaml`, `ls *.yaml | xargs rm`, `find . -name '*.yaml' -delete` or `-exec rm`), and a Bash `rm`/`rmdir`/`mv`/`shred`/`unlink` aimed at the project directory, one of its parents or `.claude/` is denied. A command shlex cannot parse (an apostrophe in a heredoc) falls back to crude tokens for E2 (no glob check) instead of failing closed, so E2 stays usable with E5 off.
- **E2 normalises paths and protects the whole state directory (F2, high).** File-tool targets (Write/Edit/MultiEdit/NotebookEdit) and MCP strings were matched as given, so `Write ./.claude/state/../state/field-ledger.jsonl` was allowed. Every path-like value is now also matched in normalised absolute and root-relative form (`~`, `.`, `..`, backslashes, and symlinks on POSIX, through the same canonicalisation `path_key` uses for the ledger), the resolved manifest (a `FIELD_MANIFEST` override included), ledger and call-counter paths are normalised before escaping, and the project's whole `.claude/state/` directory is protected (ledger, counter, lock, anything added later) rather than two file names. Two exceptions keep documented commands working: the kill sentinel (`/field kill` creates it; E1 already stops its removal) and the skill's `.claude/state/field.json`. Another root's `~/.claude/state/` is not affected.
- **Input-size and time caps (F3, medium).** The E2 built-in patterns began with `.*`, which under `re.search` is a no-op that makes a miss quadratic in the text: a 5000-segment command (58 KB) took 10.8 s, past the 10 s `hooks.json` timeout, and a hook killed by the timeout fails open. The `.*` is dropped (a leading `.*` on a user `protected_paths` pattern is dropped at compile time too), E5 tokens are de-duplicated before `path_key`, and three fail-closed caps are added: hook input over 4 MiB, a shell command over 64 KiB, or an E2/E3/E5 check running past 5 s denies with `E0`. The 58 KB command now takes 0.6 s.
- **E2 is case-insensitive everywhere (F4, medium).** Only Windows roots were case-folded, so `Write FIELD-MANIFEST.YAML` was allowed on POSIX although a case-insensitive file system (macOS default, some Linux mounts) would hit the manifest. All E2 patterns, `protected_paths` included, now compile with `re.IGNORECASE`. E3 is unchanged (case-insensitive for PowerShell only).
- Docstring: the call counter and ledger have been serialised by the gate lock since 1.2.0; the limits paragraph said the counter was not locked.
- `verify-ledger.py` and the README say what the chain does and does not detect: an edit that breaks a link, not a ledger re-chained after the edit, which verifies INTACT. The gate implements no keyed or signed scheme.
- `hooks/test/run_e5.sh` gains 143 cases (310 total): every finding above with controls showing `echo x > notes.md; true`, `Write ./docs/../README.md`, `git add .claude/commands/x.md`, `rm *.py`, `ls *`, `for f in *`, `find . -name '*.yaml'`, `cat *.md`, `grep -r x .`, `wc -l *`, `cp *.yaml backup/`, `git commit -m "update field-manifest.yaml"`, `echo "see field-manifest.yaml"`, `grep "field-manifest.yaml" README.md`, an MCP write whose content has `*` bullets, `Write .claude/state/KILL` and `Write .claude/state/field.json` still allowed; E5 cases with `..` in the path and a symlinked project root (removing `realpath` from the canonicalisation now fails 2 cases; it passed all 167 before); a 70 KB command and a 5 MB input denied with `E0`, a 3 MB `Write` and the 5000-segment command allowed within budget, and the time budget forced to zero denying `E0`.

Found in an independent review commissioned 2026-10-12.

### Changed

- E2 deny reasons for the built-in patterns no longer start with `.*` (`'field-manifest\.ya?ml$'`); glob and directory denials say `shell glob/brace pattern expands to the manifest` and `destructive command aimed at the project directory` without echoing the word, so no absolute path reaches the ledger.
- Legitimate commands that are now denied (the safe direction, consistent with E2 denying reads that name a governance file): an unquoted Bash word naming a governance file anywhere in the command (`cat field-manifest.yaml`, `find . -name field-manifest.yaml`; 1.2.2 caught only the last word), `ls .claude/state`, `cd .claude/state`, `Write .claude/state/<anything but KILL or field.json>`, and `mkdir -p ~/.claude/state` only when the project root is the home directory. A governance name inside a quoted argument of a non-command-carrying, non-mutating word stays allowed (`git commit -m "update field-manifest.yaml"`, `echo "see field-manifest.yaml"`, `grep "field-manifest.yaml" README.md`, `cat "field-manifest.yaml"`), as do read-only globs (`ls *`, `for f in *`, `cat *.md`, `find . -name '*.yaml'` without `-delete`/`-exec`). Hook input that cannot be parsed because it is over 4 MiB is denied without a ledger record, like malformed input.

### Known limitations

- A command word with no path separator is resolved through `PATH` and keeps the E5 read-only exemption (unchanged from 1.2.2).
- E2 and E5 match command text, not process execution: variables (`F=field-manifest.yaml; rm $F`, `eval "$CMD"`), encoded payloads, programs that delete without naming the target (`git clean -fdx`, `rsync --delete`; `find . -delete` with no name filter is caught as a wipe of its start directory, `find . -mtime +7 -delete` likewise), files created by Bash itself, and paths relative to a changed working directory (`cd .claude && rm -r state`) are not caught. Globs are matched only against the built-in governance paths, not against `protected_paths` regexes, and only as arguments of the mutating commands listed above, redirect targets, `xargs`/`find -exec` pipelines; a mutating program outside that list (`rsync --delete`, `zip -m`, `git rm *.yaml`) is not covered. Quoted text is re-analysed as a shell command only in the contexts listed above plus a pipeline that ends in a shell or interpreter (`echo "rm field-manifest.yaml" | sh` is caught); code for another language piped to its interpreter (`echo 'os.remove("field-manifest.yaml")' | python3`) is parsed as shell, where the quoted name is an argument of a non-mutating word, and is not caught. Regex matching is a tripwire, not a sandbox.
- The time budget is checked between patterns and tokens, not inside a single regex match: a catastrophically backtracking `protected_paths` or `deny_patterns` regex can still outlive the hook timeout on a 64 KiB command.
- Windows run of the extended suite not performed for this release (POSIX symlink cases are skipped there by design).

---

## field — 1.2.2 / marketplace — 1.4.2 — 2026-10-03

### Fixed

- **E5 no longer exempts a file named after a read-only tool.** The read-only check compared the basename of the command word, so once a session had written a file called `git` or `cat`, running it as `./git` or `tools/cat` was allowed. A command word that contains a path separator and resolves to a file the session wrote is now checked like any other command. The real `cat`, `git` and the rest of the read-only list are unaffected. Reported by Ridzwan Gigih Herdyantha in review of #2.
- `hooks/test/run_e5.sh` gains 56 cases: every read-only name run as `./name`, a nested path, `chmod` then run, wrappers and subshells, and controls showing the real `cat`, `git` and `ls` stay allowed after a same-named file is written.

### Known limitations

- A command word with no path separator is resolved through `PATH` and keeps the read-only exemption. A `PATH` that includes the project directory is outside E5's model.

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
