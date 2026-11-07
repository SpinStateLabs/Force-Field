# Lessons (ssl-fp-builder-1)

Rules written after corrections or surprises in this build. Review at session start.

1. **Match the user's shell.** A PowerShell 5.1 prompt does not accept `&&`. Give one command per line, and say which
   directory to run them in (`cd` first). A command that assumes a clone must say where the clone is.
2. **Check a version number against the changelog before cutting a release.** "1.6.0" had already been used and was behind the
   current 2.0.0. Read `CHANGELOG.md` and the manifests first, state the conflict, and propose the next valid version.
3. **A backlog without numbers is not a backlog split.** Before taking "odd items", confirm the numbering with the principal
   and check which items are already built (grep the changelog and code) so no work is duplicated or invented.
4. **Test the real runtime, not only a stub.** The n8n stub run passed while a live n8n showed lost ledger records and an
   undone kill under concurrent calls. When a design leans on a platform behaviour (locking, concurrency, persistence),
   run it on the platform before documenting an assumption as advice.
5. **A hook's "unpushed commits" message can be stale.** Check `git ls-remote` against HEAD before acting; refresh the
   remote-tracking ref (`git fetch origin branch:refs/remotes/origin/branch`) in shallow clones.
6. **Session limits are not bugs to route around.** Tag pushes, branch deletes and local servers were blocked at times; report
   the block and hand the user the exact command instead of trying another path. Retry only when the user explicitly asks
   and the safer variant (for example binding a server to 127.0.0.1) fits the block's reason.
7. **Verify merge preconditions every time.** Re-read the PR's checks and merge state at the head SHA immediately before merging;
   wait for a pending required check instead of merging on "unstable".
