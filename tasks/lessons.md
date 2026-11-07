# Lessons (builder-2, ssl-fp build session, 2026-11-05 to 2026-11-07)

Format: pattern seen, then the rule that prevents it. Review at session start.

1. **A backlog can be stale.** ROADMAP v1.2 listed `local_sentinel` and policy verdicts as "next" after they had shipped (field 1.4.0, 1.3.0).
   Rule: before building a backlog item, grep CHANGELOG.md, the schema and the code for it. Report "already built" instead of rebuilding.

2. **The stop hook reports unpushed commits that are not unpushed.** It said "no remote branch" for branches that were on the remote.
   Rule: verify with `git ls-remote --heads origin <branch>` and `git status -sb` before acting on it. Never push on the hook's say-so.

3. **Pushes, merges and deletes need an explicit "go" in chat.** plugin-agent.md forbids pushing, tagging and branch deletion without one. A "go" for one push does not cover the next.
   Rule: commit locally, report the hash, ask for "go", push once, then re-verify the remote tip equals local HEAD.

4. **The permission classifier can deny a merge or a ready-for-review call that the user asked for.** Denial reasons seen: "Merge Without Review", "Unrequested Commit in a Connected App".
   Rule: do not retry or route around a denial. State what was blocked and offer the user's options (do it in the UI, repeat the request by name, add a permission rule). An explicit repeat by the user succeeded each time.

5. **The proxy blocks branch deletion (HTTP 403).** Both the REST API and `git push --delete` were refused.
   Rule: a 403 policy denial is final for the session. Report it and give the user the UI or local-command route.

6. **Two builders created the same file (`tasks/todo.md`) and conflicted.**
   Rule: use builder-specific file names from the start (`tasks/todo-builder-N.md`). Merge `main` into the branch (no rebase) to resolve a conflict, and re-run tests on the merged tree.

7. **Verify state before claiming it.** PRs turned out to be drafts, CI was still running, and the head had moved after a merge.
   Rule: fetch the PR state and check runs immediately before reporting or merging. Pin merges to the verified head SHA. Wait for all checks to finish.

8. **CI suites have conventions.** `run_all.sh` needs PASS lines, no FAIL lines, and a SKIP list equal to the allowlist. A docstring in a unittest broke the verbose line parsing.
   Rule: put a new suite behind a `run_*.sh` wrapper that prints PASS, FAIL and N/A lines. Report dependency-gated cases as N/A, not SKIP. Mutation-check that a real regression turns the wrapper red.

9. **Ambiguous requests deserve a question.** "Them", "take a card" and "move on to next task" each had more than one reading.
   Rule: ask one short question that names the readings. Do not guess when the action is outward-facing.

10. **Do not use credentials or accounts nobody pointed me at.** AWS keys were present in the environment, and the user had named no bucket.
    Rule: list env var names only, never values. Ask for the bucket and scope before any live write.

11. **Existing wording is protected.** plugin-agent.md says to preserve existing wording unless the user approves.
    Rule: propose a diff first and apply it only on "apply". Flag any edit that removes existing text.

12. **FORCE protocol applies to every reply** (user correction, 2026-11-07). The first dozen replies dropped the numbered structure and the O objections.
    Rule: use ASSUMPTIONS, REASONING (with O objections for proposals) and CONCLUSION, tag claims HIGH, MEDIUM or LOW, and keep each section minimal. The token and cost line says "not available" because this environment has no usage counters. Never invent figures.

13. **Standing delegation (user, 2026-11-07): "you have the authority except for money and features; do not stop and ask, take your best recommendation or ask an advisor."**
    Rule: act without asking on code, docs, PRs, pushes and merges of my own PRs, after verifying state. Still stop for money (paid or credentialed services such as a live AWS test) and for features (new capabilities or roadmap scope, such as the Conformance Sentinel or a new plugin). A tool or classifier denial is still final for that action: report it and move on.
