# field — Claude Code Plugin

FIELD is Spin State Labs' governance framework for agentic AI. Where **FORCE** constrains what an
AI *says* on a given response, **FIELD** constrains how an AI is *deployed, controlled, and held
accountable*. FORCE is runtime prompt hygiene; FIELD is design-time governance. They compose.

## The five letters

- **F** — Federated — trust protocols across ownership boundaries (which peers, on what basis)
- **I** — Identity — attribution and sovereignty (whose agent, what jurisdiction, what data scope)
- **E** — Enforcement — the brakes and rails (kill switch, spend cap, escalation, irreversible-action policy)
- **L** — Ledger — the immutable, cryptographically sealed audit trail
- **D** — Delegation — the authorization chain from a human principal to the agent

Every FIELD-governed agent carries one **manifest** (`field-manifest.yaml`) declaring its posture
across all five. The `/field` command generates, validates, and audits it.

## Install

```
/plugin marketplace add SpinStateLabs/Force-Field
/plugin install field@force-field
/reload-plugins
/field
```

Manual / air-gapped installs: see [INSTALL.md](INSTALL.md).

## Usage

```
/field                         show skill state + working manifest
/field on | off                toggle proactive assistance
/field init [template]         create ./field-manifest.yaml
/field validate                check the manifest against the schema
/field assess                  walk the five letters interactively
/field audit                   audit-ready summary of the manifest
/field export [json|yaml]      print the manifest in a format
/field template <name>         set the default template
/field reset                   restore skill defaults
/field kill                    trip the kill switch (create the sentinel file)
/field resume                  show how a human lifts the kill switch; confirm when lifted
/field verify                  check the ledger hash chain (tamper-evident)
```

## Templates

| Template | Use case |
|---|---|
| `default` | Baseline general use. Fill in principal, kill switch, and delegation. |
| `financial-agent` | FP&A / audit-adjacent. 7-year ledger retention, sealed, kill switch tied to spend cap. |
| `read-only-agent` | Retrieval / analysis. Zero write scope, no write delegation, reduced enforcement. |
| `client-facing-agent` | Draft-only outbound. Human review at every escalation, no autonomous send. |

Bootstrap with `/field init <template>`.

## The manifest lifecycle

```
/field init financial-agent     →  writes ./field-manifest.yaml from a template
   (walk F→I→E→L→D, fill REPLACE-ME)
/field validate                 →  VALID / INVALID + critical gaps + warnings
/field audit                    →  audit-ready block for external review
```

A manifest is **INVALID** if it lacks any of the five sections, or is missing a kill switch, a
delegation grantor, an identity principal, or a sealed ledger. Those are the non-negotiables.

## File structure

```
field/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── field/
│       ├── SKILL.md                    # when and how to apply
│       ├── framework.md                # the five letters in operational depth
│       ├── field-defaults.json         # seed state for first run
│       ├── manifest-schema.json        # JSON Schema for field-manifest.yaml
│       └── templates/
│           ├── field-manifest-default.yaml
│           ├── field-manifest-financial-agent.yaml
│           ├── field-manifest-read-only-agent.yaml
│           └── field-manifest-client-facing-agent.yaml
├── commands/
│   └── field.md                        # /field slash command logic
├── hooks/
│   ├── hooks.json                      # PreToolUse + PostToolUse registration (auto-loaded by Claude Code)
│   ├── field-gate.py                   # the Enforcement Gate (E1–E5, L)
│   ├── field-post.py / field-post.sh   # PostToolUse evidence hook: records that an asked call ran (1.5+)
│   ├── verify-ledger.py                # hash-chain verifier (/field verify)
│   └── test/                           # fixture + smoke test: bash hooks/test/run.sh
├── install.ps1 / install.sh            # manual installers
├── INSTALL.md
└── README.md
```

Skill state lives outside the plugin at `~/.claude/state/field.json` so it survives plugin updates.
Manifests live per-project at `./field-manifest.yaml` — one per agent.

## Composition with FORCE

Every FIELD-governed agent should apply FORCE at runtime. The manifest declares it:

```yaml
runtime_protocol:
  name: FORCE
  version: "1.0"
  preset: analysis
```

Install both: `/plugin install force@force-field` and `/plugin install field@force-field`.

## Runtime enforcement (v1.1+)

The plugin ships an **Enforcement Gate**: a Claude Code `PreToolUse` hook (`hooks/`) that reads
`./field-manifest.yaml` and enforces it while you work.

| Rule | Manifest key | Effect |
|---|---|---|
| E1 kill switch | `enforcement.kill_switch.endpoint` with `method: file` (else `.claude/state/KILL`); `kill_switch.local_sentinel` (+ opt-in `sentinel_max_age_s`) for an estate kill, 1.4+ | sentinel file present → every gated tool call denied. `local_sentinel` is created and removed by a host watcher that polls the estate kill switch (field-platform `tools/estate_kill_watcher.py`); the gate makes no network call. With `sentinel_max_age_s` a missing or stale `<local_sentinel>.alive` stamp also denies. Put it under `.claude/state/` (already E2-protected as a directory) |
| E2 protected paths | built-in set + `enforcement.protected_paths` (regexes) | edits/commands touching the manifest, `.claude/settings*.json`, `hooks.json`, the ledger, the call counter or anything else in `.claude/state/` denied (1.2.3: every unquoted shell word is checked, not only the command's end, plus quoted words given to a mutating command, a redirect, `sh -c`/`eval`/`xargs`; paths are normalised and matched case-insensitively; globs in those positions such as `rm *.yaml` or `ls *.yaml | xargs rm` are expanded against the real paths, while `ls *` and `grep "x"` are not; `rm`/`mv` of the project directory or `.claude/` denied). The kill sentinel and `.claude/state/field.json` stay writable so `/field kill` and the skill work |
| E3 irreversible actions | `enforcement.irreversible_actions.deny_patterns` (regexes); opt-in `deny_patterns_verdict: policy` (1.3+) | matching Bash or PowerShell commands denied. With `deny_patterns_verdict: policy` the verdict follows `irreversible_action_policy`: `forbid` denies, `require_human_approval` asks (Claude Code's permission prompt; denied when headless), `allow_with_ledger` allows with a ledger record. Default `deny` |
| E4 call budget | `enforcement.rate_limits` entry `{action: tool_call, period: session}` | per-session tool-call ceiling (a proxy, not a dollar spend cap) |
| E5 session-written execution (opt-in, 1.2+) | `enforcement.irreversible_actions.session_written_exec: deny` (+ `session_written_exec_allow` regexes) | a Bash command that names a file this session wrote with a file tool is denied, unless it is a read-only tool (`cat`, `ls`, `git`, ...); covers `bash x.sh`, `./x.sh`, `python3 x.py`, `cat x.sh \| bash`, `-c` strings, wrappers like `sudo` |
| L ledger | `ledger.store` when path-like, else `.claude/state/field-ledger.jsonl` | every decision appended, sha-256 hash-chained; `/field verify` checks it. File-tool records carry `path`: root-relative inside the project, `sha256:<hex>` outside it |

Post-call evidence (1.5+): a `PostToolUse` hook (`hooks/field-post.py`) appends one ledger record, `rule: "E3-policy-executed"`,
when a call the gate answered with an ask (`E3-policy`) ran. It is evidence only (always exit 0, no verdict) and it records that the
call ran, with `human_approval: "not_evidenced"` and `approver: null`; it does not say who approved. See the CHANGELOG, field 1.5.0.

`require_human_approval` under `deny_patterns_verdict: policy` is **not** P-25 named-approver approval. The gate answers "ask", which is a
prompt to whoever holds the terminal. The ledger records only that the call ran (`E3-policy-executed`, `human_approval: "not_evidenced"`,
`approver: null`). No estate may cite it as P-25 or named-approver evidence.

Where "ask" is verified (ADR-0071 Implementation, ADR-0075): Linux CLI 2.1.306 (the prompt held the call in every `permission_mode` tried, HIGH)
and Windows CLI 2.1.307 in `default` mode (PASS-ask, MEDIUM: inferred from logs, prompt text not captured). Under a `permission_mode` other than
`default` an ask can run without a person: on Windows 2.1.307, in every logged `auto` run the ask did not hold the command (MEDIUM). IDE,
desktop and Agent SDK hosts were not run (UNVERIFIED; an SDK host that auto-approves a permission request would turn an ask into an allow, which the
gate cannot see). Estates on any other host, or with any session that may run in `auto` mode, set `deny_patterns_verdict: deny`.

Gated tools (1.2+): every tool except Read, Glob, Grep, LS, NotebookRead and TodoWrite, including
PowerShell and MCP tools. E1, E2, E4 and L apply to all of them; E3 and E5 read shell commands (Bash and
PowerShell). PowerShell has no parser, so E5 denies any PowerShell command that names a written file,
reads included. In 1.1 only Bash, Edit, Write, MultiEdit and NotebookEdit were gated. Requires a POSIX `sh` (Git Bash on
Windows) and Python 3 with PyYAML; the launcher tries `python3`, `py -3`, then `python` (1.2.4+), and when none runs the gate
in a project with a manifest it denies with E0. Without PyYAML the gate fails closed. The gate loads only with the plugin install (Method A);
`--bare` and `disableAllHooks` turn it off. Once a manifest exists the agent cannot edit it —
governance changes are made by the human, outside the session.

## Limitations

Enforcement and Ledger are runtime-enforced in Claude Code (E1–E5, L above); Federated, Identity
and Delegation remain declared, not enforced. The spend cap remains a tool-call proxy. The ledger
hash chain is tamper-evident, not tamper-proof: `/field verify` detects an edit that breaks a
link, not a ledger re-chained from scratch after the edit, which verifies INTACT. The chain is
unkeyed (`sha-256-chain`); the gate implements no signed or keyed scheme, so the chain's value
rests on who can write the file. E2 denies the agent's own tools every write to the ledger and to
the rest of `.claude/state/`; a process outside the gate (or the human) can still rewrite it. Regex
matching is a guardrail, not a sandbox. E2 and E5 match command text: indirection (`F=x.sh; bash $F`,
`eval`, variables), programs that load or delete a file without naming it (`make`, `npm test`,
`git clean`, `find -delete`) and files created by Bash itself (`echo > x.sh`, `curl -o`) are not
caught, and paths resolve against the project root rather than the shell's working directory
(`cd .claude && rm -r state`). E5 is strict on purpose: non-read-only commands naming a written file
(`cp`, `mv`, `pytest x.py`) are denied unless exempted. Hook input over 4 MiB, a shell command over
64 KiB, or a check that runs past 5 s denies with E0 rather than risk the 10 s hook timeout, which
fails open. `/field audit` produces an audit-ready report; independent certification is a separate
service.

### Known-bypass register (E2 and E5 are text-scanning controls, not a sandbox)

Windows path handling (ADR-0080) resolves symlinks, junctions and 8.3 short names, strips `\\?\` prefixes, NTFS streams and trailing dots, and refuses (E0) any path it cannot map to a drive letter: UNC and admin-share (`\\localhost\C$\...`, `//localhost/C$/...`), `\\?\Volume{GUID}\`, `\\?\GLOBALROOT\Device\...`, `\\.\` device paths and drive-relative `C:x`. Local admin-share access is denied by design; a project that itself lives on a UNC share keeps working because paths under the identically cleaned root are allowed. Not covered, and not fixable by this mechanism:

- **Hard links** to a protected or session-written file: `realpath` cannot see them (identical on POSIX). A hard link made by the agent through Bash is a file created by Bash itself.
- **Shell expansion**: `$PWD`, `$(pwd)`, `${CLAUDE_PROJECT_DIR}`, `%CD%`, `$env:...`, and Git Bash `/proc/self/cwd/...` spell the path in a form the gate does not evaluate.
- **A program that opens the path itself**: `python -c "open(...)"`, `node -e`, an editor macro.
- **Unknown**: network drives mapped with `net use` (untested); whether Claude Code ever passes a `\\?\Volume{}`, GLOBALROOT, UNC or drive-relative path to the OS at all (the gate refuses them either way); Python versions other than 3.12 and 3.14.
- **Refusals that can be false denies**: a word that starts with two slashes (`cat //etc/passwd`, `git diff -- //foo/bar`) is a UNC path on Windows (`\\etc\passwd`), so the gate denies E0 for it even in a read-only command; use a single slash. A path the OS cannot open to resolve (Win32 error 5, access denied, or 1920, a Store app-execution alias such as `WindowsApps/python.exe`) is kept as written rather than denied: nothing can be followed through it, and the agent could not write through it either. A directory with more than 20000 entries is not listed (the listing only saves failed opens); the path then goes to the OS directly.
- Words of a Bash command are link-resolved when they contain a slash, start with `~`, or name an entry of the project root (`echo x >> link`). A bare word that names an entry of the current directory when that is not the project root is not resolved (the gate resolves against the project root, as above).
- A symlink or junction **loop**, or any resolution error other than "does not exist", denies E0 on Windows. On POSIX a loop is not detected (unchanged: `realpath` returns the path as is).
- **Bare-word link names with special characters.** Fixed on POSIX in PR 15; still open on Windows (a name starting with `-`). A link whose name begins with `-` or contains `?`, `*`, `"`, `<`, `>` or `|` is never resolved as a bare word: `echo x >> -lnk` (link `-lnk` to `.claude/state/f`) writes through it unseen. Name such a link with a slash (`./-lnk`) and it is caught.
- **Globs that match a root link.** Fixed in PR 15 for the first path component (no brace expansion). `echo x >> led?` or `echo x >> led*` where `ledger` is a link into `.claude/state`: the shell expands the glob after the gate has looked at the text.
- **A link created in the same command or in a parallel call is invisible at check time.** The gate resolves links as they exist when it runs. `ln -s .claude/state l && echo x > l/f`, or PowerShell `cmd /c mklink /D l .claude\state; echo x > l\f` / `New-Item -ItemType SymbolicLink`, creates the link and writes through it in one call, so the link protection (ADR-0080) does not apply to it. This defeats the link feature in a single call; treat link resolution as covering links that already exist.
- **cmd forms not followed (open).** `%COMSPEC% /c ...`, `winpty cmd /c ...`, `cmd /c 'set A=.claude&& echo x > %A%\x'` (shell expansion), and a bare name after a `cd` in the same command (the gate does not track the working directory); also `cmd /c a.bat` and `cmd < file` (the command line is in a file the gate does not read), `%COMSPEC% /c`, `"%COMSPEC%"` and `start /b cmd` in the Bash tool, `replace` and `wmic ... delete` (cmd file commands that are not mapped), and `python -c` inside a cmd line. This parser is an accident guard, not a security boundary. Pre-existing and still open: the wipe check (project directory, parents, `.claude`) looks at the top-level command and, since this PR, at `bash -c`/`sh -c`/`-Command` and cmd payloads (three levels), but not at `env`/`sudo` wrapped commands, `eval`, `xargs rm -r`, `find -exec rm -r`, or `python -c` rmtree; `rm -rf` is also caught by the manifest's E3 pattern, so forms without `-f` are the ones the E2 check alone must stop; the PowerShell tool has no wipe check for its own cmdlets and aliases (`rm -r -fo .claude`, `ri -Recurse .claude`, `del .claude -r`, `Move-Item .claude ..\x`, `[IO.Directory]::Delete`, `rd /s /q` as a bare PowerShell command, `robocopy empty . /mir`); `robocopy`, `attrib`, `icacls` and `mklink` inside a cmd line are not judged; `%CD%`, `%~dp0` and other cmd variable expansion, `..\` traversal out of the project and `.cla*` patterns in a directory name are not resolved.
- **PowerShell colon-bound parameters.** Fixed in PR 15. Only path-valued parameters are split. `Set-Content -Path:.claude\state\x` binds the value to the flag with a colon; the state-directory pattern is anchored at the start of a token, so it does not match after the `-Path:` prefix.
- **False deny (fixed in PR 15 unless that drive letter exists): single-letter prefix with two or more colons.** `echo a:b:c` (also `Write-Output a:b:c`) reads as a drive-relative path `a:` and gives E0 UnresolvablePath although it is not a path. Quote-free workaround: put the text in a file or quote it so it is not a bare word.

## Related

- Landing page: [spinstatelabs.ca/field](https://spinstatelabs.ca/field)
- Companion plugin: [`force`](../force/README.md) — the runtime protocol FIELD wraps
- Author: Don Hagell · [Spin State Labs](https://spinstatelabs.ca)

## License

MIT — see [LICENSE](../../LICENSE)
