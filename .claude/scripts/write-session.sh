#!/bin/bash
# Write session content to session log file with flock-based locking
# Usage: write-session.sh <session-file> [--create]
#   Content is read from stdin
#   --create: Create new file (use > instead of >>), adds date header automatically
#
# Examples:
#   echo "## Session 5 - Topic (time)" | ~/.claude/scripts/write-session.sh "/path/to/2026-01-28.md"
#   echo "## Session 1 - Topic (time)" | ~/.claude/scripts/write-session.sh "/path/to/2026-01-28.md" --create

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session-file> [--create]"
    exit 1
fi

SESSION_FILE="$1"
CREATE_MODE=false

if [ "${2:-}" = "--create" ]; then
    CREATE_MODE=true
fi

# Read content from stdin into a variable (before acquiring lock)
CONTENT="$(cat)"

if [ -z "$CONTENT" ]; then
    echo "No content provided on stdin"
    exit 1
fi

# Derive lock file path (same directory as session file)
LOCK_DIR="$(dirname "$SESSION_FILE")"
LOCK_FILE="$LOCK_DIR/.lock"

# Ensure lock file and directory exist
mkdir -p "$LOCK_DIR"
touch "$LOCK_FILE"

# Export for subshell
export SESSION_FILE CONTENT CREATE_MODE

# Write with flock for atomicity
flock -w 10 "$LOCK_FILE" bash -c '
    if [ "$CREATE_MODE" = "true" ]; then
        # Extract date from filename for header (YYYY-MM-DD.md -> YYYY-MM-DD)
        DATE_PART="$(basename "$SESSION_FILE" .md)"
        printf "# Claude Session - %s\n\n%s\n" "$DATE_PART" "$CONTENT" > "$SESSION_FILE"
    else
        printf "\n%s\n" "$CONTENT" >> "$SESSION_FILE"
    fi
'

echo "Session written to: $SESSION_FILE"
