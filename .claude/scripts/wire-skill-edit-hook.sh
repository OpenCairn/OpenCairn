#!/usr/bin/env bash
# Wire (or remove) the skill-edit cross-pollination hook into the user's Claude Code
# settings. Invoked by the /setup-hooks command; safe to run directly.
#
# Why settings.json (NOT settings.local.json): settings.local.json is where Claude
# Code auto-writes permission grants — merging hooks there risks clobbering and is
# machine-local. User-level hooks belong in settings.json. Do not redirect this.
#
# Usage:
#   wire-skill-edit-hook.sh            # add the hooks (idempotent)
#   wire-skill-edit-hook.sh --remove   # remove them
#
# Honours CLAUDE_CONFIG_DIR (defaults to ~/.claude). Requires jq.
# Platform: Linux, macOS, Windows (Git Bash).

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not found." >&2
  echo "Install: Debian/Ubuntu 'sudo apt install jq' | macOS 'brew install jq' | Fedora 'sudo dnf install jq'" >&2
  exit 1
fi

MODE="add"
if [ "${1:-}" = "--remove" ]; then
  MODE="remove"
elif [ -n "${1:-}" ]; then
  echo "Usage: $0 [--remove]" >&2
  exit 1
fi

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SETTINGS="$CONFIG_DIR/settings.json"
MARKER_CMD="$CONFIG_DIR/scripts/skill-edit-marker.sh"
SURVEY_CMD="$CONFIG_DIR/scripts/skill-edit-survey.sh"

# Ensure a settings file exists to merge into.
if [ ! -f "$SETTINGS" ]; then
  if [ "$MODE" = "remove" ]; then
    echo "No settings file at $SETTINGS — nothing to remove."
    exit 0
  fi
  mkdir -p "$CONFIG_DIR"
  echo '{}' > "$SETTINGS"
  chmod 600 "$SETTINGS"
fi

# Refuse to touch settings that don't already parse.
if ! jq -e . "$SETTINGS" >/dev/null 2>&1; then
  echo "Error: $SETTINGS is not valid JSON. Fix it before wiring hooks." >&2
  exit 1
fi

TMP=$(mktemp "${SETTINGS}.tmp.XXXXXX")
trap 'rm -f "$TMP"' EXIT

if [ "$MODE" = "add" ]; then
  jq --arg marker "$MARKER_CMD" --arg survey "$SURVEY_CMD" '
    # Add {type,command,timeout} under .hooks[event] for the given matcher.
    # Idempotent: keyed on the command STRING, so a future timeout change does not
    # create a duplicate. Appends to an existing matcher block; creates one if absent.
    def add_hook($event; $matcher; $cmd; $timeout):
      .hooks //= {}
      | .hooks[$event] //= []
      | if any(.hooks[$event][]; .matcher == $matcher and any(.hooks[]?; .command == $cmd))
        then .
        elif any(.hooks[$event][]; .matcher == $matcher)
        then .hooks[$event] |= map(if .matcher == $matcher
              then .hooks += [{type:"command", command:$cmd, timeout:$timeout}] else . end)
        else .hooks[$event] += [{matcher:$matcher, hooks:[{type:"command", command:$cmd, timeout:$timeout}]}]
        end;
    add_hook("PostToolUse"; "Write|Edit"; $marker; 5)
    | add_hook("Stop"; ".*"; $survey; 5)
  ' "$SETTINGS" > "$TMP"
else
  jq --arg marker "$MARKER_CMD" --arg survey "$SURVEY_CMD" '
    # Remove the command from every matcher block in the event, then drop any matcher
    # block left with an empty hooks array (inert — safe regardless of who created it).
    def strip($event; $cmd):
      if (.hooks[$event]? | type) == "array"
      then .hooks[$event] |= ( map(.hooks |= map(select(.command != $cmd)))
                               | map(select((.hooks | length) > 0)) )
      else . end;
    strip("PostToolUse"; $marker)
    | strip("Stop"; $survey)
  ' "$SETTINGS" > "$TMP"
fi

# Refuse to install a broken file.
if ! jq -e . "$TMP" >/dev/null 2>&1; then
  echo "Error: produced invalid JSON; settings left unchanged." >&2
  exit 1
fi

# Semantic no-op detection (ignore formatting/key-order differences).
if [ "$(jq -S . "$SETTINGS")" = "$(jq -S . "$TMP")" ]; then
  echo "No changes — hooks already in their target state ($MODE)."
  exit 0
fi

# Timestamped backup (never overwrites a prior recovery point), preserve mode, atomic replace.
BACKUP="${SETTINGS}.bak-$(date +%Y%m%d-%H%M%S)"
cp -p "$SETTINGS" "$BACKUP"
chmod 600 "$TMP"
mv "$TMP" "$SETTINGS"
trap - EXIT

echo "Updated $SETTINGS ($MODE). Backup: $BACKUP"
echo "--- hooks now: ---"
jq '.hooks' "$SETTINGS"
