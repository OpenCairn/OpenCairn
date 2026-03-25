#!/usr/bin/env bash
# Check for Claude plan files modified today that may contain stranded work product.
# Usage: check-stranded-plans.sh
# Output: list of plan files modified today (one per line), or empty if none.
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

# Create a midnight marker for today (portable across GNU/BSD)
MARKER="/tmp/.opencairn_midnight_marker_$$"
touch -t "$(date +%Y%m%d0000)" "$MARKER"

# Find files newer than midnight
find "$PLANS_DIR" -type f -newer "$MARKER" 2>/dev/null || true

rm -f "$MARKER"
