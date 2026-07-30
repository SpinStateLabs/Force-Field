# Force-Field

Spin State Labs' Claude Code plugin marketplace. The home of the **Force Field Framework** — Spin State's approach to building AI that's defensible in production.

## What's the Force Field Framework?

Two layers, two plugins, one marketplace:

| Layer | What it does | Plugin | Status |
|---|---|---|---|
| **FORCE** | Runtime prompt protocol. Constrains what an AI *says*. | `force` | ✅ v1.0 shipped |
| **FIELD** | Design-time governance for agentic AI. Constrains how an agent is *deployed and accountable*. | `field` | ✅ v1.0 shipped |

FORCE neutralizes sycophancy and hallucination on individual responses. FIELD governs how an autonomous agent is harnessed, who owns it, and how it federates — captured in a per-agent governance manifest (Federated / Identity / Enforcement / Ledger / Delegation). They compose: every FIELD-governed agent runs FORCE at runtime.

See [ROADMAP.md](ROADMAP.md) for the full picture.

## Install the marketplace

In any Claude Code session:

```
/plugin marketplace add SpinStateLabs/Force-Field
```

Then install plugins:

```
/plugin install force@force-field
/plugin install field@force-field
/reload-plugins
```

Verify with `/force` (current FORCE state) and `/field` (current FIELD state).

## What is FORCE?

A five-letter prompt protocol designed at Spin State Labs to neutralize the two failure modes of every modern LLM: **sycophancy** (blind agreement) and **hallucination** (confident fabrication).

- **F** — Forbid Flattery & Force Corrections
- **O** — Oppose the Premise
- **R** — Reference Verified Sources
- **C** — Chain-of-Thought
- **E** — Express Uncertainty

The full kit (one-pager PDF, Claude.ai system prompt, n8n workflow, this plugin) lives at [spinstatelabs.ca/force](https://spinstatelabs.ca/force).

## Repo structure

```
Force-Field/
├── .claude-plugin/
│   └── marketplace.json              # Marketplace catalog
├── plugins/
│   ├── force/                        # FORCE plugin (v1.0 shipped)
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── skills/
│   │   │   └── force/
│   │   │       ├── SKILL.md
│   │   │       ├── protocol.md
│   │   │       └── protocol-defaults.json
│   │   ├── commands/
│   │   │   └── force.md
│   │   └── README.md
│   └── field/                        # FIELD plugin (v1.0 shipped)
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── skills/
│       │   └── field/
│       │       ├── SKILL.md
│       │       ├── framework.md
│       │       ├── manifest-schema.json
│       │       ├── field-defaults.json
│       │       └── templates/        # 4 per-agent manifest templates
│       ├── commands/
│       │   └── field.md
│       ├── install.ps1 / install.sh
│       ├── INSTALL.md
│       └── README.md
├── .github/
│   └── workflows/
│       └── validate.yml              # JSON schema validation on push
├── LICENSE                           # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md                        # FORCE + FIELD shipped
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

Plugin versions follow [SemVer](https://semver.org/). To release a new version:

1. Update `version` in `plugins/<name>/.claude-plugin/plugin.json`
2. Update the matching plugin entry in `.claude-plugin/marketplace.json`
3. Add a section to `CHANGELOG.md`
4. Tag the commit: `git tag v1.x.x && git push --tags`

Users get the new version when they run `/plugin marketplace update force-field`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The marketplace is curated, not community-open — pull requests welcome for bug fixes and protocol refinements; new plugins by discussion only.

## License

MIT — see [LICENSE](LICENSE).

## About Spin State Labs

[Spin State Labs](https://spinstatelabs.ca) — a Waterloo-based AI and quantum company. We implement NetSuite Planning & Budgeting, Oracle EPBCS, and build AI-first Planning, Budgeting & Forecasting software. The Force Field Framework is the internal standard we apply to every client deliverable. We share it because the EPM industry needs higher AI hygiene, and frameworks travel faster than they spread by accident.
