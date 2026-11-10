# Privacy Policy: Force and Force-Field plugins

Spin State Labs publishes two Claude plugins from this repository: `force` and `force-field`.
Effective 2026-11-10.

## What we collect

Nothing. Spin State Labs does not collect, receive, store, sell or share any data from these plugins. They have no
analytics, telemetry or accounts, and no server of ours is contacted.

## What the plugins do on your machine

- **force**: Markdown instructions. It reads and writes one local file, `~/.claude/state/force.json`, which holds
  your FORCE toggle settings.
- **force-field**: the above, plus `~/.claude/state/field.json`, and the FIELD Enforcement Gate. The gate runs
  locally on tool calls and, in a project that has a `field-manifest.yaml`, appends each decision to a local
  hash-chained ledger at `.claude/state/field-ledger.jsonl` in that project. Nothing is sent anywhere.

## Optional estate mode (force-field only)

If you set `estate_mode=estate`, the plugin connects to the estate URL you configure, and sends the API key you
configure to that URL as a Bearer token. That estate is operated by you or your organization, not by Spin State
Labs. Its data handling is governed by whoever runs it. The default mode, `local`, makes no network calls.

## Your data and Claude

Your conversations with Claude are governed by Anthropic's own terms and privacy policy, not by this document.

## Children

These plugins are developer tools and are not directed at anyone under 18.

## Changes and contact

Changes to this policy are published in this repository and dated above. Questions:
https://github.com/SpinStateLabs/Force-Field/issues or don@spinstatelabs.ca.
