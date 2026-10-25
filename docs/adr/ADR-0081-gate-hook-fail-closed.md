# ADR-0081: The gate hook fails closed (`onFailure: "block"`)

- Status: Proposed (draft PR, independent review pending; the owner merges only after naming the PR)
- Date: 2026-10-25
- Deciders: Don (owner); engineer (this ADR)
- Repo: SpinStateLabs/Force-Field, `plugins/field/hooks/hooks.json`, branched from `main` 1679941
- Related: ADR-0080 (Windows path aliasing, the last ADR referenced in the CHANGELOG); the owner's 2026-10-25 decision that the gate must really enforce; the 2026-10-25 enforcement-boundary ADR (effect-layer track), which this does not change
- Numbering and location: ADRs up to 0080 are referenced by number in the CHANGELOG and the plugin README, but their texts are not in this repository. This is the first ADR file here; `docs/adr/` is where the field-platform ADR packs say this repository's ADRs belong.

Evidence tags: MEASURED (run on this machine, output recorded), TRACED (read from code or docs, not run), DECLARED (stated, not verified).

## 1. Context

The Enforcement Gate is a Claude Code `PreToolUse` command hook: `hooks.json` runs `sh "${CLAUDE_PLUGIN_ROOT}/hooks/field-gate.sh"` for every tool (`matcher: "*"`) with `timeout: 10`. The gate answers through its exit code: 0 allows, 2 denies.

Claude Code treats every other outcome of a command hook as a non-blocking error and lets the tool call continue through the normal permission flow: a hook that times out, crashes (exit code other than 0 or 2), cannot start, or prints invalid JSON (TRACED: [hooks reference](https://code.claude.com/docs/en/hooks), sections "Block the action when a hook fails" and the PreToolUse timeout note). So a gate that stalled past 10 s, for example on a large ledger or a saturated machine, allowed the call. The launcher (`field-gate.sh`) and `field-gate.py` already turn the errors they can see into a deny (exit 2, rule E0), and the gate denies with E0 when a check runs past its own 5 s budget; neither can act when the hook is killed by the timeout or never starts.

Claude Code 2.1.295 (2026-10-08) added a per-hook field `onFailure` for `command` and `http` hooks, values `"continue"` (default) and `"block"`; a timeout counts as a failure (TRACED: [changelog](https://code.claude.com/docs/en/changelog.md), 2.1.295; hooks reference). With `"block"`, a failure does what exit code 2 does on that event; for PreToolUse the hooks reference says "a `PreToolUse` failure blocks the tool call". The field has no effect on `Stop`, `SubagentStop`, `TaskCompleted`, `TeammateIdle` or background (`async`, `asyncRewake`) command hooks (TRACED: hooks reference); the gate is none of these.

## 2. Decision

Set `"onFailure": "block"` on the PreToolUse gate hook in `plugins/field/hooks/hooks.json`; keep `"timeout": 10`. Leave the PostToolUse evidence hook at the default (`"continue"`, key unset). Pin both with a static test that runs in CI, and keep a live test for real builds outside CI.

```json
{ "type": "command", "command": "sh \"${CLAUDE_PLUGIN_ROOT}/hooks/field-gate.sh\"", "timeout": 10, "onFailure": "block" }
```

## 3. Measured results

Machine: rog-command, Windows 10 Home 10.0.19045, Claude Code 2.1.308 (`claude --version`), logged in through claude.ai, model `sonnet`, Git for Windows at `D:\Apps\Git`. Each run: `claude -p --plugin-dir <dir> --max-turns 2 --output-format stream-json --verbose --include-hook-events --no-session-persistence --permission-prompts none` from a new empty project directory (no `field-manifest.yaml`), with every `CLAUDE_*`, `ANTHROPIC_*` and credential-like variable removed from the child environment. The stand-in gate (cases A and B) is a copy of `plugins/field` whose `hooks/field-gate.sh` writes a marker line, then sleeps 20 s. Script: `plugins/field/hooks/test/run_timeout_live.sh`. Transcripts are outside the repository.

| Case | Hook shell | hooks.json | Result (MEASURED) | Timing (MEASURED) |
|---|---|---|---|---|
| A | Git Bash (`CLAUDE_CODE_GIT_BASH_PATH=D:\Apps\Git\bin\bash.exe`) | branch file, verbatim | Bash call **blocked**: tool_result is an error, `PreToolUse:Bash hook error: [sh "${CLAUDE_PLUGIN_ROOT}/hooks/field-gate.sh"]: timed out; blocking because onFailure is "block"`; no tool_result holds the echo's output; stub marker shows the stub ran; run ended `success` after 2 turns with 1 permission denial. 13:50:25Z | tool_use to tool_result 10.8 s; hook started to hook cancelled 10.80 s; stub's first line 0.47 s after the hook started |
| A | PowerShell (Claude Code: Git Bash not found; no `CLAUDE_CODE_GIT_BASH_PATH`) | branch file, verbatim | PowerShell call **blocked**, same reason (`onFailure is "block"`). 13:43:58Z | 10.8 s; hook started to cancelled 10.78 s; stub's first line +0.69 s |
| B (control) | PowerShell (Git Bash not found) | key removed | **blocked anyway**: reason given is that Git Bash was not found and the hook sets no `"shell"`, so only exit code 0 or 2 counts as a verdict (the Windows rule from 2.1.299/2.1.310). The control is therefore inconclusive in this configuration. | 10.9 s; hook started to cancelled 10.88 s; stub's first line +0.65 s |
| C (sanity) | PowerShell (Git Bash not found) | branch plugin unmodified (real gate) | **allowed**: `FIELD-LIVE-OK` returned, PreToolUse and PostToolUse hooks both `success` exit 0, run `success` | PowerShell call 6.4 s, of which PreToolUse hook 1.7 s and PostToolUse hook 1.6 s |
| B, C | Git Bash | | **not run** | |

Model-free checks (MEASURED): `claude plugin validate` (2.1.308) accepts the shipped plugin; with `"onFailure": "Blokk"` it fails, naming `onFailure` and the allowed values `continue` and `block`, and warns that a PreToolUse entry that cannot be loaded leaves what it guards unapplied; with an extra made-up hook key it passes. In all three stub runs no `end` line was written to the stub marker within 21 s of its start, so Claude Code ended the hook process on the timeout; no stub process was left running.

Model calls: four `claude -p` invocations made a model call (A, B, C without Git Bash; A with Git Bash). One further invocation stopped at argument parsing (a missing space in the script, fixed) before any model request.

Installed copy of the gate: the user config lists `field@force-field` 1.5.1, but `claude plugin list` reports it disabled and every run's init event listed only the `--plugin-dir` copy (`field@inline`) plus built-ins, so the installed gate took no part in these runs.

## 4. PostToolUse evidence hook: leave it at "continue"

With `"block"`, a PostToolUse failure would do what exit code 2 does on PostToolUse: show stderr to Claude, after the tool already ran (TRACED: hooks reference, exit-code table). It cannot stop anything. The evidence hook (`field-post.sh`, `field-post.py`) is designed to exit 0 with no output and to be a no-op without a manifest; turning its failures into stderr shown to the model would add noise that could prompt the model to retry or work around a hook, with no enforcement gained. No documented benefit was found. The static test asserts the evidence hook does not set `"block"`; changing that needs a new ADR.

## 5. Caveats

1. **Plugin `hooks.json` shape (was inferred, now MEASURED on 2.1.308).** The docs describe plugin hooks with the same nesting as settings hooks but do not list `onFailure` for plugins explicitly. On 2.1.308 the key is read from a plugin `hooks.json`: Claude Code cited it as the reason for the block, and `claude plugin validate` checks its value.
2. **Versions before 2.1.295 (DECLARED).** Such builds do not know the key. 2.1.308 ignores an unknown hook key, so older builds are expected to ignore `onFailure` and keep letting a failed gate through; no older build was run. If an older build rejected the entry instead, the gate would not load there at all; this was not tested.
3. **Control with Git Bash not run (DECLARED).** That 2.1.308 with Git Bash lets a timed-out gate through when the key is absent rests on the hooks reference. 2.1.299 also changed plugin hooks to refuse actions when the hook cannot hand back its answer; whether that covers a timeout is not stated. `FIELD_LIVE_CASES=B bash plugins/field/hooks/test/run_timeout_live.sh` settles it (one model call).
4. **Timeout clock (TRACED from three runs).** The block came 10.78 to 10.88 s after Claude Code reported the hook started, while the stand-in's first line ran 0.47 to 0.69 s after that. The constant offset from hook start, not from the script's first line, suggests the 10 s clock starts at launch, so start-up time counts. The docs do not say whether lock waits or start-up count.
5. **Windows.** In a clean environment Claude Code 2.1.308 did not find Git for Windows at `D:\Apps\Git` and ran hooks through PowerShell (`sh` still resolved through PATH). In that mode it blocked a timed-out gate with or without the key. The changelog shows this behaviour moved recently: 2.1.299 (hooks that set no shell no longer fail open without Git for Windows), 2.1.309 (PowerShell hooks), 2.1.310 (a command made only of quoted strings). Before 2.1.310, Windows without Git Bash behaves differently. Users with Git in a non-standard place should set `CLAUDE_CODE_GIT_BASH_PATH`.
6. **Other failure kinds (DECLARED).** Only the timeout was run. Crash (exit other than 0/2), cannot start, and invalid JSON are covered by the same documented setting.

## 6. Consequences

- A gate hook that stalls or cannot start now stops tool use until the hook recovers. This is the intended fail-closed behaviour (owner decision 2026-10-25: the gate must really enforce).
- It applies in every project where the plugin is enabled, including projects without a manifest: the gate does nothing there, but a hook that never answers cannot report that. Before this change a missing Python in such a project was allowed by design (`field-gate.sh`), and it still is, because the launcher answers 0; only a launcher that cannot start or does not answer within 10 s blocks.
- The block carries Claude Code's notice (hook command, "timed out", `onFailure`), not a FIELD rule. The gate's own 5 s budget still denies first with E0 and a reason where it can.
- On Claude Code before 2.1.295 nothing changes (DECLARED). Plugin users should check `claude --version`.
- New tests: `hooks/test/run_hooks_config.sh` + `test_hooks_config.py` (static, in `run_all.sh` and CI); `hooks/test/run_timeout_live.sh` (live, not in CI).

## 7. Alternatives considered

| Option | Why not |
|---|---|
| Leave the default (`continue`) | A stalled gate is no gate; contradicts the owner's decision. |
| Rely on the gate's internal 5 s budget | Covers slow checks the gate can see; cannot cover a hook killed by the timeout, a Python that starts too slowly, or a shell that does not start. Kept as the first line. |
| Exec-form hook (`command: python3`, `args`) without `sh` | Removes one process; does not address timeouts or start failures. Independent of this change. |
| `"block"` on the PostToolUse hook too | No effect on the call (the tool already ran); noise for the model. See section 4. |
| Longer or shorter timeout | 10 s with an internal 5 s budget leaves margin; unchanged. |
