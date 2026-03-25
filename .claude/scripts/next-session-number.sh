#!/usr/bin/env bash
# Get the next session number for a session log file.
# Usage: next-session-number.sh <session-file>
# Output: integer (next session number)
#   If file doesn't exist or has no sessions, outputs 1.
#
# Examples:
#   NUM=$("$VAULT_PATH/.claude/scripts/next-session-number.sh" "$VAULT_PATH/06 Archive/Claude/Session Logs/2026-03-15.md")
#   echo "Next session: $NUM"
#
# Platform: Linux, macOS, Windows (Git Bash).

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session-file>" >&2
    exit 1
fi

SESSION_FILE="$1"

if [ -f "$SESSION_FILE" ]; then
    LAST_NUM=$(grep -o "^## Session [0-9]*" "$SESSION_FILE" | tail -1 | grep -o "[0-9]*" || echo 0)
    echo $((LAST_NUM + 1))
else
    echo 1
fi
