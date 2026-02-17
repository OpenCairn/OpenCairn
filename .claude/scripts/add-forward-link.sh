#!/usr/bin/env bash
# Add forward link ("Next session:") to a previous session's Pickup Context
# Usage: add-forward-link.sh <session-file> <prev-session-num> <new-session-num> <new-session-topic> [<target-date-file>]
#
# <target-date-file> is the session file where the NEW session lives (for cross-day links).
# If omitted, assumes same file as <session-file> (same-day link).
#
# Examples:
#   # Same-day link:
#   add-forward-link.sh "06 Archive/Claude Sessions/2025-03-15.md" 5 6 "API Refactor"
#   # Cross-day link (prev session on Mar 15, new session on Mar 16):
#   add-forward-link.sh "06 Archive/Claude Sessions/2025-03-15.md" 5 1 "Morning Check-in" "2025-03-16.md"
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

if [ $# -lt 4 ]; then
    echo "Usage: $0 <session-file> <prev-session-num> <new-session-num> <new-session-topic>"
    exit 1
fi

SESSION_FILE="$1"
PREV_NUM="$2"
NEW_NUM="$3"
NEW_TOPIC="$4"
TARGET_DATE_FILE="${5:-}"

# Validate file exists
if [ ! -f "$SESSION_FILE" ]; then
    echo "Session file not found: $SESSION_FILE"
    exit 1
fi

# Derive the lock file path (same directory as session file)
LOCK_DIR="$(dirname "$SESSION_FILE")"
LOCK_FILE="$LOCK_DIR/.lock"

# Build the link text
# If target date file provided (cross-day link), use that for the date part.
# Otherwise derive from the source file (same-day link).
if [ -n "$TARGET_DATE_FILE" ]; then
    DATE_PART="$(basename "$TARGET_DATE_FILE" .md)"
else
    DATE_PART="$(basename "$SESSION_FILE" .md)"
fi
NEW_SESSION_LINK="**Next session:** [[06 Archive/Claude Sessions/${DATE_PART}#Session ${NEW_NUM} - ${NEW_TOPIC}]]"

# Acquire lock
_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock" >&2; exit 1; }

# Find previous session heading
PREV_HEADING=$({ grep -n "^## Session ${PREV_NUM} - " "$SESSION_FILE" || true; } | head -1 | cut -d: -f1)
if [ -z "$PREV_HEADING" ]; then
    echo "Could not find Session ${PREV_NUM} heading"
    _unlock
    exit 1
fi

# Find session block boundaries
NEXT_HEADING=$(tail -n +$((PREV_HEADING + 1)) "$SESSION_FILE" | { grep -n "^## Session " || true; } | head -1 | cut -d: -f1)
if [ -n "$NEXT_HEADING" ]; then
    END_LINE=$((PREV_HEADING + NEXT_HEADING - 1))
else
    END_LINE=$(wc -l < "$SESSION_FILE")
fi

# Guard: Check if this session already has ANY "Next session:" link
if sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | grep -q "^\*\*Next session:\*\*"; then
    echo "Session ${PREV_NUM} already has a Next session link, skipping"
    _unlock
    exit 0
fi

# Check if this is a Quick session (single line with [Q] marker)
SESSION_LINE=$(sed -n "${PREV_HEADING}p" "$SESSION_FILE")
if echo "$SESSION_LINE" | grep -q "\[Q\]$"; then
    # Quick session format:
    #   Line N:   ## Session X - Topic (time) [Q]
    #   Line N+1: (blank)
    #   Line N+2: Summary text
    #   Line N+3: **Previous session:** ... (optional)
    #
    # Find the last metadata line or insert after summary if no metadata
    INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | \
        { grep -n "^\*\*\(Project\|Continues\|Previous session\):\*\*" || true; } | tail -1 | cut -d: -f1)

    if [ -n "$INSERT_AFTER" ]; then
        INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))
    else
        INSERT_LINE=$((PREV_HEADING + 2))
    fi
else
    # Full session: find the last Pickup Context metadata line
    INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | \
        { grep -n "^\*\*\(Project\|Continues\|Previous session\):\*\*" || true; } | tail -1 | cut -d: -f1)

    if [ -z "$INSERT_AFTER" ]; then
        echo "Could not find insertion point in Session ${PREV_NUM}"
        _unlock
        exit 1
    fi
    INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))
fi

# Preserve original file permissions (GNU stat on Linux/Git Bash, BSD stat on macOS)
ORIG_PERMS=$(stat -c '%a' "$SESSION_FILE" 2>/dev/null || stat -f '%Lp' "$SESSION_FILE")

# Insert the forward link using awk (more robust than sed append)
# Use ENVIRON instead of -v to avoid backslash interpretation in topic names
export _AWK_LINE="$INSERT_LINE"
export _AWK_TEXT="$NEW_SESSION_LINK"
awk '
    NR == ENVIRON["_AWK_LINE"]+0 { print; print ENVIRON["_AWK_TEXT"]; next }
    { print }
' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
unset _AWK_LINE _AWK_TEXT

# Restore permissions if they changed
chmod "$ORIG_PERMS" "$SESSION_FILE"

_unlock

echo "Forward link added to Session ${PREV_NUM} -> Session ${NEW_NUM}"
