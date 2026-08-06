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
    MARKER="/tmp/claude-skill-edit-${SID}.marker"
    # The marker carries the count of THIS session's `outcome` log lines at the
    # moment the batch opened. skill-edit-survey.sh fires unless the count has
    # risen since — i.e. unless the model already surveyed this batch.
    #
    # Only the FIRST edit of a batch sets it; later edits in the same open batch
    # must not move the baseline, or a survey already done would look outstanding.
    # Capturing it here rather than at fire time means the value is created with
    # the batch itself, so it cannot drift or be lost independently of the marker.
    if [ ! -f "$MARKER" ]; then
      CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
      LOG="$CONFIG_DIR/cross-pollination.log"
      awk -F'\t' -v s="session=${SID}" \
        '$2=="outcome" && $3==s {n++} END{print n+0}' "$LOG" 2>/dev/null > "$MARKER" \
        || echo 0 > "$MARKER" 2>/dev/null
    fi
    ;;
esac

exit 0
