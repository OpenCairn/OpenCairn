#!/usr/bin/env bash
# Backfill "### Files Updated" section in a session log entry
# Usage: backfill-files-updated.sh <session-file> <session-num>
#   File list is read from stdin, one "- path - description" per line
#
# If the session's "### Files Updated" section contains "None", replaces it.
# Otherwise appends after the last entry in that section.
#
# Examples:
#   printf -- '- 01 Now/WIP.md - Travel 2026 status updated\n- 01 Now/This Week.md - ANZ Shield retry routed to Fri\n' | \
#     "$VAULT_PATH/.claude/scripts/backfill-files-updated.sh" "/path/to/2026-03-12.md" 25
#
# Platform: Linux, macOS, Windows (Git Bash). Uses flock where available, mkdir-based fallback otherwise.

set -euo pipefail

# --- Portable file locking (shared library) ---
source "$(dirname "$0")/lib-lock.sh"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <session-file> <session-num>"
    exit 1
fi

SESSION_FILE="$1"
SESSION_NUM="$2"

# Read file list from stdin
FILE_LIST="$(cat)"

if [ -z "$FILE_LIST" ]; then
    echo "No file list provided on stdin"
    exit 0
fi

# Validate file exists
if [ ! -f "$SESSION_FILE" ]; then
    echo "Session file not found: $SESSION_FILE"
    exit 1
fi

# Derive lock file path
LOCK_DIR="$(dirname "$SESSION_FILE")"
LOCK_FILE="$LOCK_DIR/.lock"

# Acquire lock
_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock" >&2; exit 1; }

# Find session heading
SESSION_HEADING=$({ grep -n "^## Session ${SESSION_NUM} - " "$SESSION_FILE" || true; } | head -1 | cut -d: -f1)
if [ -z "$SESSION_HEADING" ]; then
    echo "Could not find Session ${SESSION_NUM} heading"
    _unlock
    exit 1
fi

# Find session block end (next session heading or EOF)
NEXT_HEADING=$(tail -n +$((SESSION_HEADING + 1)) "$SESSION_FILE" | { grep -n "^## Session " || true; } | head -1 | cut -d: -f1)
if [ -n "$NEXT_HEADING" ]; then
    END_LINE=$((SESSION_HEADING + NEXT_HEADING - 1))
else
    END_LINE=$(wc -l < "$SESSION_FILE")
fi

# Find "### Files Updated" within this session block
FILES_UPDATED_LINE=$(sed -n "${SESSION_HEADING},${END_LINE}p" "$SESSION_FILE" | { grep -n "^### Files Updated" || true; } | head -1 | cut -d: -f1)
if [ -z "$FILES_UPDATED_LINE" ]; then
    echo "Could not find '### Files Updated' in Session ${SESSION_NUM}"
    _unlock
    exit 1
fi
FILES_UPDATED_ABS=$((SESSION_HEADING + FILES_UPDATED_LINE - 1))

# Find the next section heading after "### Files Updated" (to know the boundary)
NEXT_SECTION=$(tail -n +$((FILES_UPDATED_ABS + 1)) "$SESSION_FILE" | { grep -n "^### " || true; } | head -1 | cut -d: -f1)
if [ -n "$NEXT_SECTION" ]; then
    SECTION_END=$((FILES_UPDATED_ABS + NEXT_SECTION - 1))
else
    SECTION_END=$END_LINE
fi

# Check if the section contains "None" (with possible surrounding text)
SECTION_CONTENT=$(sed -n "$((FILES_UPDATED_ABS + 1)),$((SECTION_END - 1))p" "$SESSION_FILE")

# Preserve original file permissions
ORIG_PERMS=$(stat -c '%a' "$SESSION_FILE" 2>/dev/null || stat -f '%Lp' "$SESSION_FILE")

if echo "$SECTION_CONTENT" | grep -q "^None$"; then
    # Find the "None" line (exact match only — not "None - work completed") and replace it
    NONE_LINE=$(sed -n "$((FILES_UPDATED_ABS + 1)),$((SECTION_END - 1))p" "$SESSION_FILE" | { grep -n "^None$" || true; } | head -1 | cut -d: -f1)
    if [ -n "$NONE_LINE" ]; then
        NONE_ABS=$((FILES_UPDATED_ABS + NONE_LINE))
        # Replace the None line with the file list
        export _AWK_NONE_LINE="$NONE_ABS"
        export _AWK_FILE_LIST="$FILE_LIST"
        awk '
            NR == ENVIRON["_AWK_NONE_LINE"]+0 { print ENVIRON["_AWK_FILE_LIST"]; next }
            { print }
        ' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
        unset _AWK_NONE_LINE _AWK_FILE_LIST
    fi
else
    # Find the last "- " line in the section (last file entry) and append after it
    LAST_ENTRY=$(sed -n "$((FILES_UPDATED_ABS + 1)),$((SECTION_END - 1))p" "$SESSION_FILE" | { grep -n "^- " || true; } | tail -1 | cut -d: -f1)
    if [ -n "$LAST_ENTRY" ]; then
        INSERT_AFTER=$((FILES_UPDATED_ABS + LAST_ENTRY))
    else
        # No entries yet (empty section), insert after heading
        INSERT_AFTER=$FILES_UPDATED_ABS
    fi
    export _AWK_INSERT="$INSERT_AFTER"
    export _AWK_FILE_LIST="$FILE_LIST"
    awk '
        NR == ENVIRON["_AWK_INSERT"]+0 { print; print ENVIRON["_AWK_FILE_LIST"]; next }
        { print }
    ' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
    unset _AWK_INSERT _AWK_FILE_LIST
fi

# Restore permissions
chmod "$ORIG_PERMS" "$SESSION_FILE"

_unlock

echo "Files Updated backfilled for Session ${SESSION_NUM}"
