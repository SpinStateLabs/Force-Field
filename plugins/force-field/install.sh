#!/usr/bin/env bash
#
# FIELD Skill Installer — Spin State Labs (macOS / Linux / WSL)
#
# Idempotent. Skill and command files are refreshed on every run (updates apply).
# The state file (~/.claude/state/field.json) is CREATE-ONLY — your toggles and
# last-audit timestamp are never overwritten.
#
# Usage:
#   ./install.sh            # user-level (default, all projects)
#   ./install.sh project    # project-level (current directory only)

set -euo pipefail

LEVEL="${1:-user}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skills/field"
COMMAND_SRC="$SCRIPT_DIR/commands/field.md"

if [ "$LEVEL" = "project" ]; then
  ROOT="$(pwd)/.claude"
else
  ROOT="$HOME/.claude"
fi

SKILL_DIR="$ROOT/skills/field"
CMD_DIR="$ROOT/commands"
STATE_DIR="$ROOT/state"
STATE_FILE="$STATE_DIR/field.json"

echo ""
echo "FIELD Skill Installer"
echo "  Source: $SCRIPT_DIR"
echo "  Target: $ROOT"
echo ""

mkdir -p "$SKILL_DIR/templates" "$CMD_DIR" "$STATE_DIR"

copy_refresh() {
  local src="$1" dst="$2"
  if [ ! -f "$src" ]; then
    echo "  [warn] source missing: $src"
    return
  fi
  cp -f "$src" "$dst"
  echo "  [ok]   $dst"
}

copy_refresh "$SKILL_SRC/SKILL.md"             "$SKILL_DIR/SKILL.md"
copy_refresh "$SKILL_SRC/framework.md"         "$SKILL_DIR/framework.md"
copy_refresh "$SKILL_SRC/manifest-schema.json" "$SKILL_DIR/manifest-schema.json"
copy_refresh "$SKILL_SRC/field-defaults.json"  "$SKILL_DIR/field-defaults.json"

for f in "$SKILL_SRC"/templates/*.yaml; do
  [ -e "$f" ] || continue
  copy_refresh "$f" "$SKILL_DIR/templates/$(basename "$f")"
done

# Install the /field command at the discoverable command path
copy_refresh "$COMMAND_SRC" "$CMD_DIR/field.md"

# Seed state — CREATE ONLY, never overwrite
if [ -f "$STATE_FILE" ]; then
  echo "  [skip] $STATE_FILE already exists (state preserved)"
else
  cp -f "$SKILL_SRC/field-defaults.json" "$STATE_FILE"
  echo "  [ok]   $STATE_FILE (seeded from defaults)"
fi

echo ""
echo "Done."
echo "Test with:  /field"
echo "Bootstrap a manifest:  /field init financial-agent"
echo ""
