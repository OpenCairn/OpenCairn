#!/usr/bin/env bash
# PostToolUse (Write|Edit) hook: flag when a skill command file is edited, so the
# Stop hook (skill-edit-survey.sh) can prompt a cross-pollination survey before the
# turn ends. The marker is per-session so concurrent sessions don't interfere.
#
# Matches markdown files in any .claude/commands dir — a personal install
# (~/.claude/commands) or the template repo's working copy. Emits nothing to Claude.
#
# Platform: Linux, macOS, Windows (Git Bash). Requires jq.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE" ] && exit 0

case "$FILE" in
  *.claude/commands/*.md)
    SID=$(echo "$INPUT" | jq -r '.session_id // "nosession"')
    touch "/tmp/claude-skill-edit-${SID}.marker" 2>/dev/null
    ;;
esac

exit 0
