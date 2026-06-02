#!/usr/bin/env bash
# Write session content to session log file with file locking
#
# Usage:
#   write-session.sh <session-file>                                (append; stdin must include heading)
#   write-session.sh <session-file> --auto-number <topic> <time>   (script forms heading inside the lock)
#
# Whether to lay down the `# Claude Session - DATE` header or append is decided
# from the file's state inside the lock: absent/empty → header + first entry,
# otherwise append. There is no separate "create" path to get wrong.
#
# --create is DEPRECATED and now a no-op (header creation is state-driven). It is
# still accepted so in-flight callers don't break; drop it from new call sites.
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

AUTO_NUMBER=false
TOPIC=""
TIME_STR=""

while [ $# -gt 0 ]; do
    case "$1" in
        --create)
            # Deprecated no-op: header-vs-append is now decided from file state
            # inside the lock. Accepted for backward compatibility only.
            echo "Note: --create is deprecated and ignored (header creation is now state-driven)." >&2
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
    # Decide first-session vs append from ACTUAL file state inside the lock, not
    # from the caller's --create flag. A parallel session that already wrote the
    # first entry makes the file non-empty; basing N on a stale "I'm first"
    # belief is the F2 data-loss path. Absent OR empty file → session 1.
    if [ ! -s "$SESSION_FILE" ]; then
        ASSIGNED_NUM=1
    else
        # Max (not last) to be robust against post-collision renames that may
        # leave non-monotonic numbering. `## Session N` lines inside fenced code
        # blocks (``` or ~~~) are body content, not real headings — skip them
        # (F6) so a quoted heading can't inflate the next number.
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
        ASSIGNED_NUM=$((LAST_NUM + 1))
    fi
    HEADING="## Session $ASSIGNED_NUM - $TOPIC ($TIME_STR)"
    CONTENT="$HEADING

$CONTENT"
fi

# Lay down the `# Claude Session - DATE` header iff the file is absent or empty;
# otherwise append. This is decided from file state inside the lock — never from
# --create — so two parallel first-session writers can't lose content: the loser
# simply finds a non-empty file and appends as the next session. We only ever
# truncate (`>`) an empty/absent file, so a populated day's log is never at risk.
if [ ! -s "$SESSION_FILE" ]; then
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
