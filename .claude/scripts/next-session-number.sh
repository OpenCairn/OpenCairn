#!/usr/bin/env bash
# Get the next session number for a session log file (DIAGNOSTIC USE ONLY).
#
# ⚠ Race warning: this script reads the file without holding a write lock.
# Two callers running in parallel will both see the same max-N and both
# return N+1, producing duplicate session headings if both then write.
#
# For atomic resolve-and-write, use `write-session.sh --auto-number <topic> <time>`
# instead — it resolves N inside the file lock.
#
# This script is safe for read-only diagnostics (e.g. "what session would be
# next?" for display purposes) but must NOT be used to compute a value that
# will subsequently be written by a separate call.
#
# Usage: next-session-number.sh <session-file>
# Output: integer (next session number)
#   If file doesn't exist or has no sessions, outputs 1.
#
# Platform: Linux, macOS, Windows (Git Bash).

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session-file>" >&2
    exit 1
fi

SESSION_FILE="$1"

if [ -f "$SESSION_FILE" ]; then
    # Use max (not file-order last) to stay consistent with write-session.sh
    # --auto-number. They diverge on non-monotonic numbering (manual edits,
    # post-collision renames), which would cause spurious reconciliation in
    # callers that compare this probe against --auto-number's assigned N.
    LAST_NUM=$(grep -oE '^## Session [0-9]+' "$SESSION_FILE" 2>/dev/null \
               | grep -oE '[0-9]+' \
               | sort -n \
               | tail -1 || true)
    LAST_NUM="${LAST_NUM:-0}"
    echo $((LAST_NUM + 1))
else
    echo 1
fi
