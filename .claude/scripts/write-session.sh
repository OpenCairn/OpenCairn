#!/usr/bin/env bash
# Write session content to session log file with file locking
# Usage: write-session.sh <session-file> [--create]
#   Content is read from stdin
#   --create: Create new file (use > instead of >>), adds date header automatically
#
# Examples:
#   echo "## Session 5 - Topic (time)" | ~/.claude/scripts/write-session.sh "/path/to/2026-01-28.md"
#   echo "## Session 1 - Topic (time)" | ~/.claude/scripts/write-session.sh "/path/to/2026-01-28.md" --create
#
# Platform: Linux, macOS, Windows (Git Bash). Uses flock where available, mkdir-based fallback otherwise.

set -euo pipefail

# --- Portable file locking ---
_lock() {
    _LOCK_FILE="$1"
    local timeout="${2:-10}"
    if command -v flock &>/dev/null; then
        exec 9>"$_LOCK_FILE"
        flock -w "$timeout" 9 || { echo "Lock timeout after ${timeout}s" >&2; return 1; }
    else
        _LOCK_DIR="${_LOCK_FILE}.d"
        local waited=0
        while ! mkdir "$_LOCK_DIR" 2>/dev/null; do
            if [ "$waited" -ge "$timeout" ]; then
                echo "Lock timeout after ${timeout}s" >&2
                return 1
            fi
            sleep 1
            waited=$((waited + 1))
        done
        trap '_unlock' EXIT
    fi
}

_unlock() {
    if command -v flock &>/dev/null; then
        exec 9>&- 2>/dev/null || true
    else
        rm -rf "${_LOCK_DIR:-}" 2>/dev/null || true
        trap - EXIT
    fi
}
# --- End portable locking ---

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

# Ensure directory exists
mkdir -p "$LOCK_DIR"

# Acquire lock and write
_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock" >&2; exit 1; }

if [ "$CREATE_MODE" = "true" ]; then
    DATE_PART="$(basename "$SESSION_FILE" .md)"
    printf "# Claude Session - %s\n\n%s\n" "$DATE_PART" "$CONTENT" > "$SESSION_FILE"
else
    printf "\n%s\n" "$CONTENT" >> "$SESSION_FILE"
fi

_unlock

echo "Session written to: $SESSION_FILE"
