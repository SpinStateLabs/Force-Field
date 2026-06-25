# Force-Field

Spin State Labs' Claude Code plugin marketplace. AI hygiene and analytical skills for production-grade work.

## What's inside

| Plugin | Purpose | Install |
|---|---|---|
| **`force`** | The FORCE protocol — toggleable AI hygiene constraints | `/plugin install force@force-field` |

More plugins to follow.

## Install the marketplace

In any Claude Code session:

```
/plugin marketplace add SpinStateLabs/Force-Field
```

Then install individual plugins:

```
/plugin install force@force-field
/reload-plugins
```

Verify with `/force` — you should see the current FORCE state.

## What is FORCE?

A five-letter prompt protocol designed at Spin State Labs to neutralize the two failure modes of every modern LLM: **sycophancy** (blind agreement) and **hallucination** (confident fabrication).

- **F** — Forbid Flattery & Force Corrections
- **O** — Oppose the Premise
- **R** — Reference Verified Sources
- **C** — Chain-of-Thought
- **E** — Express Uncertainty

The full kit (one-pager PDF, system prompt, n8n workflow, this plugin) lives at [spinstatelabs.ca/force](https://spinstatelabs.ca/force).

## Why Force-Field?

The marketplace name reflects the broader Spin State Labs framework — *Force Field* — for AI persona development and boundary-setting in agentic systems. The FORCE prompt protocol is the first surface of that work; more skills (FP&A analyst, audit, agentic financial planning) will follow as plugins under this same marketplace.

## Repo structure

```
Force-Field/
├── .claude-plugin/
│   └── marketplace.json           # Marketplace catalog
├── plugins/
│   └── force/                     # The FORCE plugin
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── skills/
│       │   └── force/
│       │       ├── SKILL.md
│       │       ├── protocol.md
│       │       └── protocol-defaults.json
│       ├── commands/
│       │   └── force.md
│       └── README.md
├── .github/
│   └── workflows/
│       └── validate.yml           # JSON schema validation on push
├── LICENSE
├── CHANGELOG.md
├── CONTRIBUTING.md
└── README.md
```

## Development

To test changes locally before pushing:

```
/plugin marketplace add ./path/to/Force-Field
/plugin install force@force-field
```

The local path version lets you iterate without pushing every change.

## Versioning

Plugin versions follow [SemVer](https://semver.org/). Update `version` in:
1. `plugins/<name>/.claude-plugin/plugin.json`
2. `.claude-plugin/marketplace.json` (matching plugin entry)
3. `CHANGELOG.md`

Users get the new version when they run `/plugin marketplace update force-field`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Pull requests welcome for bug fixes and protocol refinements. New plugins are accepted only if they align with Spin State Labs' positioning (AI hygiene, FP&A, agentic systems).

## License

MIT — see [LICENSE](LICENSE).

## About Spin State Labs

[Spin State Labs](https://spinstatelabs.ca) — a Waterloo-based AI and quantum company. We implement NetSuite Planning & Budgeting, Oracle EPBCS, and build AI-first Planning, Budgeting & Forecasting software. FORCE is the internal prompt standard we apply to every client deliverable. We're sharing it because the EPM industry needs higher AI hygiene, and frameworks travel faster than they spread by accident.
