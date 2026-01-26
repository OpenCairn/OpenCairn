#!/bin/bash
# Add forward link ("Next session:") to a previous session's Pickup Context
# Usage: add-forward-link.sh <session-file> <prev-session-num> <new-session-num> <new-session-topic>
#
# Example:
#   add-forward-link.sh "06 Archive/Claude Sessions/2025-03-15.md" 5 6 "API Refactor"

set -euo pipefail

if [ $# -lt 4 ]; then
    echo "Usage: $0 <session-file> <prev-session-num> <new-session-num> <new-session-topic>"
    exit 1
fi

SESSION_FILE="$1"
PREV_NUM="$2"
NEW_NUM="$3"
NEW_TOPIC="$4"

# Validate file exists
if [ ! -f "$SESSION_FILE" ]; then
    echo "Session file not found: $SESSION_FILE"
    exit 1
fi

# Derive the lock file path (same directory as session file)
LOCK_DIR="$(dirname "$SESSION_FILE")"
LOCK_FILE="$LOCK_DIR/.lock"

# Build the link text
# Extract just the date portion for the wikilink (YYYY-MM-DD.md -> YYYY-MM-DD)
DATE_PART="$(basename "$SESSION_FILE" .md)"
NEW_SESSION_LINK="**Next session:** [[06 Archive/Claude Sessions/${DATE_PART}#Session ${NEW_NUM} - ${NEW_TOPIC}]]"

# Ensure lock file exists
touch "$LOCK_FILE"

# Export variables for subshell (avoids quote injection vulnerabilities)
export SESSION_FILE PREV_NUM NEW_NUM NEW_SESSION_LINK

# All operations inside flock for atomicity
flock -w 10 "$LOCK_FILE" bash -c '
    # Find previous session heading first (needed for scoped checks)
    PREV_HEADING=$(grep -n "^## Session ${PREV_NUM} - " "$SESSION_FILE" | head -1 | cut -d: -f1)
    if [ -z "$PREV_HEADING" ]; then
        echo "Could not find Session ${PREV_NUM} heading"
        exit 1
    fi

    # Find session block boundaries
    NEXT_HEADING=$(tail -n +$((PREV_HEADING + 1)) "$SESSION_FILE" | grep -n "^## Session " | head -1 | cut -d: -f1)
    if [ -n "$NEXT_HEADING" ]; then
        END_LINE=$((PREV_HEADING + NEXT_HEADING - 1))
    else
        END_LINE=$(wc -l < "$SESSION_FILE")
    fi

    # Guard: Check if this session already has ANY "Next session:" link
    if sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | grep -q "^\*\*Next session:\*\*"; then
        echo "Session ${PREV_NUM} already has a Next session link, skipping"
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
            grep -n "^\*\*\(Project\|Continues\|Previous session\):\*\*" | tail -1 | cut -d: -f1)

        if [ -n "$INSERT_AFTER" ]; then
            # Has metadata - insert after last metadata line
            INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))
        else
            # No metadata - insert after the summary line (N+2)
            INSERT_LINE=$((PREV_HEADING + 2))
        fi
    else
        # Full session: find the last Pickup Context metadata line
        INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | \
            grep -n "^\*\*\(Project\|Continues\|Previous session\):\*\*" | tail -1 | cut -d: -f1)

        if [ -z "$INSERT_AFTER" ]; then
            echo "Could not find insertion point in Session ${PREV_NUM}"
            exit 1
        fi
        INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))
    fi

    # Insert the forward link (escape backslashes for sed)
    ESCAPED_LINK=$(printf '%s\n' "$NEW_SESSION_LINK" | sed '\''s/\\/\\\\/g'\'')
    sed -i "${INSERT_LINE}a\\${ESCAPED_LINK}" "$SESSION_FILE"
    echo "Forward link added to Session ${PREV_NUM} -> Session ${NEW_NUM}"
'
