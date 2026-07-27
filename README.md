# Force-Field

Spin State Labs' Claude Code plugin marketplace. The home of the **Force Field Protocol** — Spin State's approach to building AI that's defensible in production.

## What's the Force Field Protocol?

Two layers, two plugins, one marketplace:

| Layer | What it does | Plugin | Status |
|---|---|---|---|
| **FORCE** | Runtime prompt protocol. Constrains what an AI *says*. | `force` | ✅ v1.0 shipped |
| **FIELD** | Design-time persona methodology. Constrains who the AI *is*. | `field` | 🔜 in design |

FORCE neutralizes sycophancy and hallucination on individual responses. FIELD defines the persona — boundaries, identity, escalation rules — that the agent maintains across thousands of interactions. They compose.

See [ROADMAP.md](ROADMAP.md) for the full picture.

## Install the marketplace

In any Claude Code session:

```
/plugin marketplace add SpinStateLabs/Force-Field
```

Then install plugins:

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

The full kit (one-pager PDF, Claude.ai system prompt, n8n workflow, this plugin) lives at [spinstatelabs.ca/force](https://spinstatelabs.ca/force).

## Repo structure

```
Force-Field/
├── .claude-plugin/
│   └── marketplace.json              # Marketplace catalog
├── plugins/
│   └── force/                        # FORCE plugin (v1.0 shipped)
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
│       └── validate.yml              # JSON schema validation on push
├── LICENSE                           # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── ROADMAP.md                        # FORCE shipped, FIELD next
└── README.md
```

FIELD will live at `plugins/field/` when it ships.

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

[Spin State Labs](https://spinstatelabs.ca) — a Waterloo-based AI and quantum company. We implement NetSuite Planning & Budgeting, Oracle EPBCS, and build AI-first Planning, Budgeting & Forecasting software. The Force Field Protocol is the internal standard we apply to every client deliverable. We share it because the EPM industry needs higher AI hygiene, and frameworks travel faster than they spread by accident.

## The prompt, directly

No install needed — the canonical FORCE system prompt (plus inline variant) is a text file:
**[docs/FORCE_PROMPT.txt](docs/FORCE_PROMPT.txt)** — paste into custom instructions on Claude, GPT, Gemini, or any capable model.

## Assets

One-pagers (also served from the landing pages):

- FORCE one-pager: [dark](docs/assets/SpinStateLabs_FORCE_OnePager.pdf) · [light](docs/assets/SpinStateLabs_FORCE_OnePager_Light.pdf)
- FIELD one-pager: [dark](docs/assets/SpinStateLabs_FIELD_OnePager.pdf) · [light](docs/assets/SpinStateLabs_FIELD_OnePager_Light.pdf)

Landing pages: [spinstatelabs.ca/force](https://spinstatelabs.ca/force) · [spinstatelabs.ca/field](https://spinstatelabs.ca/field)
