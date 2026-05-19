#!/usr/bin/env bash
# Write session content to session log file with file locking
#
# Usage:
#   write-session.sh <session-file>                                            (append; stdin must include heading)
#   write-session.sh <session-file> --create                                   (first session of day; stdin must include heading)
#   write-session.sh <session-file> --auto-number <topic> <time>               (append; script forms heading inside the lock)
#   write-session.sh <session-file> --create --auto-number <topic> <time>     (first session; body-only stdin)
#
# --auto-number mode resolves the session number atomically INSIDE the flock.
# This eliminates the race where two parallel /park invocations both call
# next-session-number.sh and both resolve to the same N before either acquires
# the write lock. In --auto-number mode, stdin must NOT include the
# `## Session N - …` heading; the script prepends it.
#
# Stdout:
#   Default mode:       Session written to: <path>
#   --auto-number mode: Session written to: <path>
#                       Session number assigned: <N>
#
# Content is read from stdin in all modes.
#
# Platform: Linux, macOS, Windows (Git Bash). Uses flock where available, mkdir-based fallback otherwise.

set -euo pipefail

# --- Portable file locking (shared library) ---
source "$(dirname "$0")/lib-lock.sh"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <session-file> [--create] [--auto-number <topic> <time>]" >&2
    exit 1
fi

SESSION_FILE="$1"
shift

CREATE_MODE=false
AUTO_NUMBER=false
TOPIC=""
TIME_STR=""

while [ $# -gt 0 ]; do
    case "$1" in
        --create)
            CREATE_MODE=true
            shift
            ;;
        --auto-number)
            AUTO_NUMBER=true
            if [ $# -lt 3 ]; then
                echo "--auto-number requires <topic> and <time> arguments" >&2
                exit 1
            fi
            TOPIC="$2"
            TIME_STR="$3"
            if [ -z "$TOPIC" ] || [ -z "$TIME_STR" ]; then
                echo "--auto-number requires non-empty <topic> and <time>" >&2
                exit 1
            fi
            shift 3
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: $0 <session-file> [--create] [--auto-number <topic> <time>]" >&2
            exit 1
            ;;
    esac
done

# Read content from stdin into a variable (before acquiring lock)
CONTENT="$(cat)"

if [ -z "$CONTENT" ]; then
    echo "No content provided on stdin" >&2
    exit 1
fi

# In --auto-number mode, reject stdin whose first non-blank line is a session
# heading. The script prepends its own heading; a duplicate from the caller
# produces two headings and breaks downstream session-block scoping.
if [ "$AUTO_NUMBER" = "true" ]; then
    FIRST_LINE=$(printf '%s\n' "$CONTENT" | grep -m1 -v '^[[:space:]]*$' || true)
    if printf '%s' "$FIRST_LINE" | grep -qE '^## Session [0-9]+'; then
        echo "ERROR: --auto-number mode received stdin starting with a '## Session N' heading." >&2
        echo "Remove the heading from stdin — the script prepends it." >&2
        exit 1
    fi
fi

# Derive lock file path (same directory as session file)
LOCK_DIR="$(dirname "$SESSION_FILE")"
LOCK_FILE="$LOCK_DIR/.lock"

# Ensure directory exists
mkdir -p "$LOCK_DIR"

# Acquire lock and write
_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock" >&2; exit 1; }

# In --auto-number mode, resolve N atomically inside the lock
ASSIGNED_NUM=""
if [ "$AUTO_NUMBER" = "true" ]; then
    if [ "$CREATE_MODE" = "true" ] || [ ! -f "$SESSION_FILE" ]; then
        ASSIGNED_NUM=1
    else
        # Use max (not last) to be robust against post-collision renames that
        # may leave non-monotonic numbering. Empty file or no matches → 0.
        LAST_NUM=$(grep -oE '^## Session [0-9]+' "$SESSION_FILE" 2>/dev/null \
                   | grep -oE '[0-9]+' \
                   | sort -n \
                   | tail -1 || true)
        LAST_NUM="${LAST_NUM:-0}"
        ASSIGNED_NUM=$((LAST_NUM + 1))
    fi
    HEADING="## Session $ASSIGNED_NUM - $TOPIC ($TIME_STR)"
    CONTENT="$HEADING

$CONTENT"
fi

if [ "$CREATE_MODE" = "true" ]; then
    # Safety check: refuse to truncate a file that already has content
    if [ -s "$SESSION_FILE" ]; then
        echo "ERROR: --create would truncate non-empty file: $SESSION_FILE" >&2
        echo "File has $(wc -l < "$SESSION_FILE") lines. Use append mode (omit --create) instead." >&2
        _unlock
        exit 1
    fi
    DATE_PART="$(basename "$SESSION_FILE" .md)"
    printf "# Claude Session - %s\n\n%s\n" "$DATE_PART" "$CONTENT" > "$SESSION_FILE"
else
    printf "\n%s\n" "$CONTENT" >> "$SESSION_FILE"
fi

_unlock

echo "Session written to: $SESSION_FILE"
if [ "$AUTO_NUMBER" = "true" ]; then
    echo "Session number assigned: $ASSIGNED_NUM"
fi
