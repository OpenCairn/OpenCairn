#!/usr/bin/env bash
# Backfill "### Files Updated" section in a session log entry
# Usage: backfill-files-updated.sh <session-file> <session-num>
#   File list is read from stdin, one "- path - description" per line
#   (the leading "- " is optional; every written row carries exactly one).
#   An indented line is a nested bullet or continuation of the row above: it is
#   written as supplied when that row is written and dropped when it is skipped.
#   A "None" placeholder line is not a row and is never written.
#
# If the session's "### Files Updated" section contains "None", replaces it.
# Otherwise appends after the last entry in that section.
#
# A path already in Files Created/Updated is skipped: its existing row and
# description stay, and the incoming row is printed, not written. Every run that
# reaches the dedup ends with a "<N> added, <M> skipped" line.
#
# Exit codes: 0 at least one row written (or empty/placeholder-only stdin) · 1 usage, lock or
# missing session/section · 3 nothing written because every row was skipped.
#
# Examples (use heredocs, not printf — printf interprets % as format specifiers):
#   cat << 'EOF' | "$VAULT_PATH/.claude/scripts/backfill-files-updated.sh" "/path/to/2026-03-12.md" 25
#   - 03 Projects/Website rebuild.md - Updated Current Objective and Next Actions
#   - 01 Now/This Week.md - Routed task to Thursday
#   EOF
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

# Read before acquiring the lock, bounded against an orphaned heredoc writer.
FILE_LIST=""
_read_stdin_content FILE_LIST || exit $?

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
    END_LINE=$(awk 'END { print NR }' "$SESSION_FILE")
fi

# Find "### Files Updated" within this session block
FILES_UPDATED_LINE=$(sed -n "${SESSION_HEADING},${END_LINE}p" "$SESSION_FILE" | { grep -n "^### Files Updated" || true; } | head -1 | cut -d: -f1)
if [ -z "$FILES_UPDATED_LINE" ]; then
    echo "Could not find '### Files Updated' in Session ${SESSION_NUM}"
    _unlock
    exit 1
fi
FILES_UPDATED_ABS=$((SESSION_HEADING + FILES_UPDATED_LINE - 1))

# Exclusive section end: next section heading within this session, or the
# first line after the session. awk counts an unterminated final record too.
SECTION_END=$(awk -v start="$FILES_UPDATED_ABS" -v end="$END_LINE" '
    NR > start && NR <= end && /^### / { print NR; found=1; exit }
    END { if (!found) print end + 1 }
' "$SESSION_FILE")

# Numeric predicates also make an empty section an empty range (unlike sed's
# reversed start,end range, which can still return the start line).
SECTION_CONTENT=$(awk -v start="$FILES_UPDATED_ABS" -v end="$SECTION_END" '
    NR > start && NR < end
' "$SESSION_FILE")

# --- Row normalisation -------------------------------------------------------
# A file row is written with exactly one leading "- ", whether the caller sent
# it bare, doubled, or under another list marker. A marker is "-", "*" or "+"
# followed by whitespace, so a dash-led filename keeps its dash.
_bullet_row() {
    local row="$1"
    while :; do
        case "$row" in
            [-*+][[:space:]]*) row="${row:1}"; row="${row#"${row%%[![:space:]]*}"}" ;;
            *) break ;;
        esac
    done
    [ -n "$row" ] || return 0
    printf -- '- %s' "$row"
}

# --- Path extraction ---------------------------------------------------------
# Backticks delimit a path atomically, including extensionless separator names.
# Legacy descriptive rows retain extension anchoring so "Context - Example.md"
# is not split at its filename separator. A paths-only row needs no delimiter.
_extract_path() {
    local line="$1" value p
    case "$line" in '- '*) value="${line#- }" ;; *) return 0 ;; esac
    if [[ "$value" == \`* ]]; then
        value="${value#\`}"
        [[ "$value" == *\`* ]] || return 0
        printf '%s' "${value%%\`*}"
        return
    fi
    p=$(printf '%s\n' "$line" | sed -n 's/^- \(.*\.[A-Za-z0-9]\{1,8\}\) - .*/\1/p')
    if [ -z "$p" ]; then
        if [[ "$value" =~ \.[A-Za-z0-9]{1,8}$ ]]; then
            p="$value"
        else
            p="${value%% - *}"
        fi
    fi
    printf '%s' "$p"
}

# Normalise for comparison: reduce an absolute or ~-relative vault path to its
# vault-relative form, so the same file written two ways compares equal.
# Prefers $VAULT_PATH when the caller exported it; otherwise derives the vault
# directory name from it and strips any absolute prefix up to that name.
# Platform-agnostic by construction — Linux (/home/<user>/), macOS
# (/Users/<user>/) and Git Bash (/c/Users/<user>/) differ only in that prefix.
_norm_path() {
    local p="$1" root="${VAULT_PATH:-}" vdir
    if [ -n "$root" ]; then
        root="${root%/}"
        p="${p#"$root"/}"
    fi
    vdir=$(basename "${root:-Files}")
    printf '%s' "$p" | sed "s|^~/$vdir/||; s|^.*/$vdir/||"
}

# Dedup: skip incoming lines whose path is already present.
# Seed the seen-set from entries already in the section, then add each accepted
# incoming path — so duplicates WITHIN a single batch are caught too, not just
# collisions against what was already written.
SEEN_PATHS=""
while IFS= read -r existing; do
    EXISTING_PATH=$(_extract_path "$existing")
    if [ -n "$EXISTING_PATH" ]; then
        SEEN_PATHS="${SEEN_PATHS}$(_norm_path "$EXISTING_PATH")
"
    fi
done <<< "$SECTION_CONTENT"

# A created file remains Created after later edits; preserve that original row.
CREATED_CONTENT=$(sed -n "${SESSION_HEADING},${END_LINE}p" "$SESSION_FILE" | awk '
    /^### Files Created$/ { inside=1; next }
    /^### / { inside=0 }
    inside { print }
')
while IFS= read -r existing; do
    EXISTING_PATH=$(_extract_path "$existing")
    if [ -n "$EXISTING_PATH" ]; then
        SEEN_PATHS="${SEEN_PATHS}$(_norm_path "$EXISTING_PATH")
"
    fi
done <<< "$CREATED_CONTENT"

DEDUPED_LIST=""
ADDED=0
SKIPPED=0
PLACEHOLDERS=0
PARENT_SKIPPED=false
while IFS= read -r line; do
    case "$line" in
        *[![:space:]]*) ;;
        *) continue ;;  # blank input line: not a row
    esac
    case "$line" in
        [[:space:]]*)
            # Nested bullet or continuation: it belongs to the row above.
            if [ "$PARENT_SKIPPED" = "true" ]; then
                printf '  incoming row not written: %s\n' "$line"
            else
                # With no row above it in this batch it is counted as a row.
                [ -n "$DEDUPED_LIST" ] || ADDED=$((ADDED + 1))
                DEDUPED_LIST="${DEDUPED_LIST:+$DEDUPED_LIST
}$line"
            fi
            continue
            ;;
    esac
    line=$(_bullet_row "$line")
    [ -n "$line" ] || continue  # a bare list marker: not a row
    PARENT_SKIPPED=false
    case "$line" in
        '- None'|'- None.'|'- None ('*)
            # The placeholder for an empty list is not a file row.
            PLACEHOLDERS=$((PLACEHOLDERS + 1))
            continue
            ;;
    esac
    FILE_PATH=$(_extract_path "$line")
    if [ -n "$FILE_PATH" ]; then
        NORM_PATH=$(_norm_path "$FILE_PATH")
        if printf '%s' "$SEEN_PATHS" | grep -qxF -- "$NORM_PATH"; then
            printf 'skipped (already listed in Created/Updated): %s\n' "$FILE_PATH"
            printf '  incoming row not written: %s\n' "$line"
            SKIPPED=$((SKIPPED + 1))
            PARENT_SKIPPED=true
            continue  # already listed (or already accepted earlier in this batch)
        fi
        SEEN_PATHS="${SEEN_PATHS}${NORM_PATH}
"
    fi
    DEDUPED_LIST="${DEDUPED_LIST:+$DEDUPED_LIST
}$line"
    ADDED=$((ADDED + 1))
done <<< "$FILE_LIST"

if [ -z "$DEDUPED_LIST" ] && [ "$SKIPPED" -eq 0 ] && [ "$PLACEHOLDERS" -gt 0 ]; then
    echo "Only a None placeholder on stdin, nothing to backfill"
    echo "0 added, 0 skipped"
    _unlock
    exit 0
fi

if [ -z "$DEDUPED_LIST" ]; then
    echo "All files already listed, nothing to backfill"
    echo "0 added, ${SKIPPED} skipped"
    _unlock
    exit 3
fi
FILE_LIST="$DEDUPED_LIST"

# Preserve original file permissions
ORIG_PERMS=$(stat -c '%a' "$SESSION_FILE" 2>/dev/null || stat -f '%Lp' "$SESSION_FILE" 2>/dev/null || echo "644")

if echo "$SECTION_CONTENT" | grep -qE "^-?[ 	]*None($|[^- 	]|[ 	]*\()"; then
    # Find placeholder "None" line — matches: "None", "- None", "- None (explanation)", "- None."
    # Does NOT match "None - work completed" (intentional content, not a placeholder)
    # Uses [ \t] instead of \s for POSIX/macOS compatibility
    NONE_LINE=$(printf '%s\n' "$SECTION_CONTENT" | { grep -nE "^-?[ 	]*None($|[^- 	]|[ 	]*\()" || true; } | head -1 | cut -d: -f1)
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
    # Append after the last file entry's whole block: its "- " line plus any
    # indented lines (nested bullets, continuations) directly beneath it.
    LAST_ENTRY=$(printf '%s\n' "$SECTION_CONTENT" | awk '
        /^- / { last = NR; open = 1; next }
        open && /^[ \t]+[^ \t]/ { last = NR; next }
        { open = 0 }
        END { if (last) print last }
    ')
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
echo "${ADDED} added, ${SKIPPED} skipped"
