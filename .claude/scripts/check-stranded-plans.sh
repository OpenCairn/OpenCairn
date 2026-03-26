#!/usr/bin/env bash
# Check for Claude plan files modified during the current session (or today).
# Usage: check-stranded-plans.sh <since_time>
#   since_time: HH:MM:SS, HH:MM, or ISO timestamp. Only files modified after this local time.
#               Use "00:00:00" for midnight (entire day, e.g. from /goodnight).
# Output: list of plan files modified since the cutoff (one per line), or empty if none.
#
# Work product in ~/.claude/plans/ doesn't sync, isn't visible in Obsidian,
# and effectively doesn't exist outside the session. This script is the
# safety net — called by /park and /goodnight to catch stranded content.
#
# Platform: Linux, macOS, Windows (Git Bash).

set -euo pipefail

PLANS_DIR="$HOME/.claude/plans"

if [ ! -d "$PLANS_DIR" ]; then
    exit 0
fi

SINCE="${1:?Usage: check-stranded-plans.sh <since_time>}"

# If just a time (HH:MM or HH:MM:SS), prepend today's date
if [[ "$SINCE" =~ ^[0-9]{2}:[0-9]{2} ]]; then
    SINCE="$(date +%Y-%m-%dT)${SINCE}"
fi

MARKER="/tmp/.opencairn_stranded_marker_$$"
trap 'rm -f "$MARKER"' EXIT

# Convert to epoch (portable: try GNU date -d, fall back to BSD date -j)
if EPOCH=$(date -d "$SINCE" +%s 2>/dev/null); then
    touch -d "@$EPOCH" "$MARKER"
elif EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$SINCE" +%s 2>/dev/null); then
    touch -t "$(date -j -f "%s" "$EPOCH" +%Y%m%d%H%M.%S)" "$MARKER"
elif EPOCH=$(date -j -f "%Y-%m-%dT%H:%M" "$SINCE" +%s 2>/dev/null); then
    touch -t "$(date -j -f "%s" "$EPOCH" +%Y%m%d%H%M.%S)" "$MARKER"
else
    echo "Error: could not parse timestamp '$SINCE'" >&2
    exit 1
fi

# Find files newer than the marker
find "$PLANS_DIR" -type f -newer "$MARKER" 2>/dev/null || true
