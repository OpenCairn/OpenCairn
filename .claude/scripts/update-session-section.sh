#!/usr/bin/env bash
# Update a named section within a session log entry
# Usage: update-session-section.sh <session-file> <session-num> <section-name> [--replace]
#   Content is read from stdin
#   Default: append after last entry (replaces "None" lines automatically)
#   --replace: replace entire section content
#   Section name without "### " prefix (e.g. "Summary", "Files Created")
#
# Examples (use heredocs, not printf — printf interprets % as format specifiers):
#   # Append to Summary (leading blank line creates paragraph break)
#   cat << 'EOF' | update-session-section.sh "/path/to/2026-03-15.md" 5 "Summary"
#
#   Additional work: fixed the auth bug.
#   EOF
#
#   # Append to Files Created (replaces "None" if that's all that's there)
#   cat << 'EOF' | update-session-section.sh "/path/to/2026-03-15.md" 5 "Files Created"
#   - path/to/new-file.md - description
#   EOF
#
#   # Replace Pickup Context entirely
#   cat << 'EOF' | update-session-section.sh "/path/to/2026-03-15.md" 5 "Pickup Context" --replace
#   **For next session:** Deploy to staging
#   **Project:** [[03 Projects/Auth]]
#   EOF
#
# Platform: Linux, macOS, Windows (Git Bash). Uses flock where available, mkdir-based fallback otherwise.

set -euo pipefail

# --- Portable file locking (shared library) ---
source "$(dirname "$0")/lib-lock.sh"

if [ $# -lt 3 ]; then
    echo "Usage: $0 <session-file> <session-num> <section-name> [--replace]"
    exit 1
fi

SESSION_FILE="$1"
SESSION_NUM="$2"
SECTION_NAME="$3"
REPLACE_MODE=false

if [ "${4:-}" = "--replace" ]; then
    REPLACE_MODE=true
fi

# Read content from stdin into a variable (before acquiring lock)
CONTENT="$(cat)"

if [ -z "$CONTENT" ]; then
    echo "No content provided on stdin"
    exit 0
fi

# Validate file exists
if [ ! -f "$SESSION_FILE" ]; then
    echo "Session file not found: $SESSION_FILE"
    exit 1
fi

# Derive lock file path (same directory as session file)
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

# Find section heading within this session block (fixed-string match for names with slashes)
SECTION_LINE=$(sed -n "${SESSION_HEADING},${END_LINE}p" "$SESSION_FILE" | { grep -nF "### ${SECTION_NAME}" || true; } | head -1 | cut -d: -f1)
if [ -z "$SECTION_LINE" ]; then
    echo "Could not find '### ${SECTION_NAME}' in Session ${SESSION_NUM}"
    _unlock
    exit 1
fi
SECTION_ABS=$((SESSION_HEADING + SECTION_LINE - 1))

# Find the next section heading after this one (bounded by session block end)
NEXT_SECTION=$(sed -n "$((SECTION_ABS + 1)),${END_LINE}p" "$SESSION_FILE" | { grep -n "^### " || true; } | head -1 | cut -d: -f1)
if [ -n "$NEXT_SECTION" ]; then
    # SECTION_END points to the line BEFORE the next heading (last line of this section's content)
    SECTION_END=$((SECTION_ABS + NEXT_SECTION - 1))
else
    # Terminal section: content runs to end of session block (or file)
    # +1 so that NR < SECTION_END catches the last line
    SECTION_END=$((END_LINE + 1))
fi

# Preserve original file permissions
ORIG_PERMS=$(stat -c '%a' "$SESSION_FILE" 2>/dev/null || stat -f '%Lp' "$SESSION_FILE")

if [ "$REPLACE_MODE" = "true" ]; then
    # Replace mode: remove all content lines between heading and boundary, insert new content
    # For terminal sections (no next ### heading), add trailing blank line since the skip range
    # eats everything. For non-terminal sections, the blank line before the next heading is
    # naturally preserved (it sits at SECTION_END, outside the skip range).
    TRAILING_BLANK=""
    if [ -z "$NEXT_SECTION" ]; then
        TRAILING_BLANK="yes"
    fi
    export _AWK_SECTION_START="$SECTION_ABS"
    export _AWK_SECTION_END="$SECTION_END"
    export _AWK_CONTENT="$CONTENT"
    export _AWK_TRAILING="$TRAILING_BLANK"
    awk '
        NR == ENVIRON["_AWK_SECTION_START"]+0 {
            print; print ENVIRON["_AWK_CONTENT"]
            if (ENVIRON["_AWK_TRAILING"] != "") print ""
            next
        }
        NR > ENVIRON["_AWK_SECTION_START"]+0 && NR < ENVIRON["_AWK_SECTION_END"]+0 { next }
        { print }
    ' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
    unset _AWK_SECTION_START _AWK_SECTION_END _AWK_CONTENT _AWK_TRAILING
else
    # Append mode: check for "None" or append after last content
    SECTION_BODY=$(sed -n "$((SECTION_ABS + 1)),$((SECTION_END - 1))p" "$SESSION_FILE")

    # Check if section body is a single non-blank line starting with "None"
    NON_BLANK_COUNT=0
    FIRST_NON_BLANK=""
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            NON_BLANK_COUNT=$((NON_BLANK_COUNT + 1))
            if [ -z "$FIRST_NON_BLANK" ]; then
                FIRST_NON_BLANK="$line"
            fi
        fi
    done <<< "$SECTION_BODY"

    if [ "$NON_BLANK_COUNT" -eq 1 ] && echo "$FIRST_NON_BLANK" | grep -q "^None"; then
        # Find the actual "None" line in the file
        NONE_ABS=$(sed -n "$((SECTION_ABS + 1)),$((SECTION_END - 1))p" "$SESSION_FILE" | { grep -n "^None" || true; } | head -1 | cut -d: -f1)
        if [ -n "$NONE_ABS" ]; then
            NONE_ABS=$((SECTION_ABS + NONE_ABS))
            export _AWK_NONE_LINE="$NONE_ABS"
            export _AWK_CONTENT="$CONTENT"
            awk '
                NR == ENVIRON["_AWK_NONE_LINE"]+0 { print ENVIRON["_AWK_CONTENT"]; next }
                { print }
            ' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
            unset _AWK_NONE_LINE _AWK_CONTENT
        fi
    else
        # Find the last non-blank line in the section body and insert after it
        LAST_CONTENT=$(sed -n "$((SECTION_ABS + 1)),$((SECTION_END - 1))p" "$SESSION_FILE" | { grep -n "." || true; } | tail -1 | cut -d: -f1)
        if [ -n "$LAST_CONTENT" ]; then
            INSERT_AFTER=$((SECTION_ABS + LAST_CONTENT))
        else
            # Empty section, insert after heading
            INSERT_AFTER=$SECTION_ABS
        fi
        export _AWK_INSERT="$INSERT_AFTER"
        export _AWK_CONTENT="$CONTENT"
        awk '
            NR == ENVIRON["_AWK_INSERT"]+0 { print; print ENVIRON["_AWK_CONTENT"]; next }
            { print }
        ' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
        unset _AWK_INSERT _AWK_CONTENT
    fi
fi

# Restore permissions
chmod "$ORIG_PERMS" "$SESSION_FILE"

_unlock

echo "Section '${SECTION_NAME}' updated in Session ${SESSION_NUM}"
