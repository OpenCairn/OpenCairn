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
    #
    # `## Session N` lines inside fenced code blocks (``` or ~~~) are body
    # content, not real headings — skip them, exactly as write-session.sh
    # --auto-number does (F6). Counting them inflates this probe's baseline
    # whenever a session body quotes a heading in a fenced example, which
    # surfaces downstream as phantom "missed sessions" in /goodnight Step 2's
    # reconciliation against --auto-number's assigned N.
    LAST_NUM=$(awk '
        /^```/  { fence = !fence; next }
        /^~~~/  { fence = !fence; next }
        !fence && /^## Session [0-9]+/ {
            if (match($0, /[0-9]+/)) {
                n = substr($0, RSTART, RLENGTH) + 0
                if (n > max) max = n
            }
        }
        END { print max + 0 }
    ' "$SESSION_FILE")
    LAST_NUM="${LAST_NUM:-0}"
    echo $((LAST_NUM + 1))
else
    echo 1
fi
