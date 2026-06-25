# Contributing to Force-Field

Thanks for the interest. A few ground rules.

## Scope

This marketplace is curated. It is not a community catalog. Plugins here align with Spin State Labs' areas of practice:

- AI hygiene and prompt protocols
- Financial planning & analysis (NetSuite, Oracle EPM, AI-first FP&A)
- Agentic systems and workflow design
- Audit-style and decision-support tooling

If you're proposing a plugin outside those domains, consider one of the community marketplaces ([anthropics/claude-plugins-community](https://github.com/anthropics/claude-plugins-community), or open marketplaces like [agensi.io](https://agensi.io)) instead.

## Reporting issues

For bugs, behavior questions, or feature requests on existing plugins:

1. Check the [issues tracker](https://github.com/SpinStateLabs/Force-Field/issues) for an open thread first.
2. If none exists, open a new issue. Include:
   - Which plugin and version
   - Claude Code version (`claude --version`)
   - What you ran (full slash command)
   - What you expected
   - What actually happened (paste the full output)

## Proposing protocol changes

The FORCE protocol itself is treated as a living specification. If you have a refinement to the protocol logic (not just the plugin implementation), open an issue tagged `protocol-proposal` with:

- The component(s) affected (F/O/R/C/E)
- The current behavior
- The proposed behavior
- Why (with at least one concrete example)

Don will respond. Substantive protocol changes ship as a minor version bump and update the canonical PDF at [spinstatelabs.ca/force](https://spinstatelabs.ca/force).

## Pull requests

Pull requests welcome for:

- Bug fixes
- Documentation improvements
- Schema/manifest corrections
- Tooling improvements (CI, validation)

Pull requests less welcome for:

- New plugins (open an issue first to discuss scope alignment)
- Stylistic preferences disagreeing with existing conventions
- Behavioral changes to the FORCE protocol without prior issue discussion

### Before submitting

1. Fork and create a feature branch from `main`.
2. Test locally:
   ```
   /plugin marketplace add ./path/to/your-fork
   /plugin install force@force-field
   ```
3. Verify JSON schemas validate (the CI will check, but local check saves a round trip).
4. Update `CHANGELOG.md` under `[Unreleased]`.
5. Open the PR with a clear description of what changed and why.

### Review criteria

- Does it serve the stated scope of the marketplace?
- Does it preserve backward compatibility unless intentionally not? (Version bump must reflect this.)
- Is the documentation updated alongside the code?
- Does it pass CI validation?

## Code of conduct

Be direct, be specific, be technically rigorous. Disagreement is welcome — defensiveness isn't. This marketplace was built under the FORCE protocol; contributions should be evaluated under it too. No flattery, no filler, no pretending uncertainty is certainty.

## Maintainer

Don Hagell · [don@spinstatelabs.ca](mailto:don@spinstatelabs.ca) · [@dhagell](https://www.linkedin.com/in/dhagell/)
