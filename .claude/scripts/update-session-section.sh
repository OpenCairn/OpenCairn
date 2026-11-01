#!/usr/bin/env bash
# Update a named section within a session log entry
# Usage: update-session-section.sh <session-file> <session-num> <section-name> [--replace]
# Usage: update-session-section.sh <session-file> --rename-heading <session-num> "<full ## Session N - ... heading>"
#   Section content is read from stdin; --rename-heading does not read stdin.
#   A missing Files Created/Updated/Deleted section is inserted before Pickup Context.
#   --replace takes the complete new section body, never an OLD/separator/NEW pair.
#   Default: append after last entry (replaces "None" lines automatically)
#   --replace: replace entire section content
#   Section name without "### " prefix (e.g. "Summary", "Files Created")
#   "Files Created" / "Files Updated" / "Files Deleted" rows are written with
#   exactly one leading "- " whether or not the caller supplied it; indented
#   lines (nested bullets, continuations) and other sections stay verbatim
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
# Heading rename needs Python 3 (python3 or python); section updates retain their shell/awk route.

set -euo pipefail

# --- Portable file locking (shared library) ---
source "$(dirname "$0")/lib-lock.sh"
source "$(dirname "$0")/lib-session.sh"

if [ $# -lt 3 ]; then
    echo "Usage: $0 <session-file> <session-num> <section-name> [--replace]"
    exit 1
fi

SESSION_FILE="$1"
REPLACE_MODE=false
RENAME_MODE=false
if [ "$2" = "--rename-heading" ]; then
    [ "$#" -eq 4 ] || { echo "--rename-heading requires a session number and full heading" >&2; exit 1; }
    RENAME_MODE=true
    SESSION_NUM="$3"
    NEW_HEADING="$4"
    SECTION_NAME=""
    case "$NEW_HEADING" in
        *$'\n'*|*$'\r'*) echo "The new heading must be one line" >&2; exit 1 ;;
        "## Session ${SESSION_NUM} - "?*) ;;
        *) echo "The new heading must start with '## Session ${SESSION_NUM} - '" >&2; exit 1 ;;
    esac
else
    SESSION_NUM="$2"
    SECTION_NAME="$3"
    if [ "${4:-}" = "--replace" ]; then
        REPLACE_MODE=true
    elif [ "$#" -gt 3 ]; then
        echo "Unknown section update option: $4" >&2; exit 1
    fi
    [ "$#" -le 4 ] || { echo "Too many section update arguments" >&2; exit 1; }
fi
[[ "$SESSION_NUM" =~ ^[1-9][0-9]*$ ]] || { echo "Session number must be a positive integer" >&2; exit 1; }

if [ "$RENAME_MODE" = "true" ]; then
    SESSION_PYTHON_BIN=""
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info[0] != 3)' >/dev/null 2>&1; then
            SESSION_PYTHON_BIN="$candidate"
            break
        fi
    done
    [ -n "$SESSION_PYTHON_BIN" ] || { echo "Heading rename requires Python 3 (python3 or python)" >&2; exit 1; }
fi

if [ "$RENAME_MODE" = "false" ]; then
# Read before acquiring the lock, bounded against an orphaned heredoc writer.
CONTENT=""
_read_stdin_content CONTENT || exit $?

# Reject the same line prefixes used below to delimit sections and sessions, and
# a locked-edit OLD/NEW separator line (the form park-verify.sh detects).
# Validate before locking or writing; avoid an early-exit pipeline under pipefail.
LOCKED_EDIT_SEP_RE='^[[:space:]]*={4,}OPENCAIRN-LOCKED-EDIT-SEP={4,}[[:space:]]*$'
while IFS= read -r line; do
    case "$line" in
        '### '*|'## Session '*)
            echo "ERROR: stdin contains a section or session boundary ('### ' or '## Session '); provide only section body text." >&2
            exit 1
            ;;
    esac
    if [[ "$line" =~ $LOCKED_EDIT_SEP_RE ]]; then
        echo "ERROR: stdin contains a locked-edit separator; --replace takes the complete new section body" >&2
        exit 1
    fi
done <<< "$CONTENT"

if [ -z "$CONTENT" ]; then
    echo "No content provided on stdin"
    exit 0
fi

# A file-list row is written with exactly one leading "- ", whether the caller sent
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

# Only the file-list sections hold one row per line; every other section is
# prose and stays verbatim. A row is a top-level line: an indented line is a
# nested bullet or a continuation of the row above and passes through, as do
# blank lines and a "None" placeholder ("None", "None.", or "None" followed by
# whitespace, "(" or an em dash). "None.md" and "Nonesuch.md" are rows.
case "$SECTION_NAME" in
    'Files Created'|'Files Updated'|'Files Deleted')
        NORMALISED=""
        while IFS= read -r line; do
            case "$line" in
                ''|[[:space:]]*) ;;
                None|None.|None[[:space:]]*|None\(*|None—*) ;;
                *) line=$(_bullet_row "$line") ;;
            esac
            NORMALISED="${NORMALISED}${line}
"
        done <<< "$CONTENT"
        CONTENT="${NORMALISED%$'\n'}"
        ;;
esac

fi  # section payload handling; heading rename has no stdin payload

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

if [ "$RENAME_MODE" = "true" ]; then
    # Replace exactly one complete heading while retaining every other byte,
    # including an unterminated final record elsewhere in the file.
    CHANGED=$("$SESSION_PYTHON_BIN" - "$SESSION_FILE" "$SESSION_NUM" "$NEW_HEADING" <<'PY_RENAME'
import os, pathlib, re, stat, sys, tempfile
path = pathlib.Path(sys.argv[1])
data = path.read_bytes()
lines = data.splitlines(keepends=True)
pattern = re.compile(rb'^## Session ' + sys.argv[2].encode() + rb' - ')
indices = [i for i, line in enumerate(lines) if pattern.match(line)]
if len(indices) != 1:
    raise SystemExit('The selected session heading must occur exactly once')
index = indices[0]
ending = b'\r\n' if lines[index].endswith(b'\r\n') else (b'\n' if lines[index].endswith(b'\n') else b'')
lines[index] = sys.argv[3].encode('utf-8') + ending
updated = b''.join(lines)
if updated != data:
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, 'wb') as handle:
            handle.write(updated)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    print('yes')
PY_RENAME
)
    [ "$CHANGED" != "yes" ] || _session_record_write "update-session-section" "$SESSION_FILE"
    _unlock
    echo "Heading renamed in Session ${SESSION_NUM}"
    exit 0
fi

# Find session block end (next session heading or EOF)
NEXT_HEADING=$(tail -n +$((SESSION_HEADING + 1)) "$SESSION_FILE" | { grep -n "^## Session " || true; } | head -1 | cut -d: -f1)
if [ -n "$NEXT_HEADING" ]; then
    END_LINE=$((SESSION_HEADING + NEXT_HEADING - 1))
else
    END_LINE=$(awk 'END { print NR }' "$SESSION_FILE")
fi

# Find section heading within this session block (fixed-string match for names with slashes)
SECTION_LINE=$(sed -n "${SESSION_HEADING},${END_LINE}p" "$SESSION_FILE" | { grep -nxF -e "### ${SECTION_NAME}" -e "### ${SECTION_NAME}"$'\r' || true; } | head -1 | cut -d: -f1)
if [ -z "$SECTION_LINE" ]; then
    case "$SECTION_NAME" in
        'Files Created'|'Files Updated'|'Files Deleted')
            PICKUP_LINE=$(sed -n "${SESSION_HEADING},${END_LINE}p" "$SESSION_FILE" | { grep -nxF -e '### Pickup Context' -e $'### Pickup Context\r' || true; } | head -1 | cut -d: -f1)
            if [ -n "$PICKUP_LINE" ]; then
                INSERT_BEFORE=$((SESSION_HEADING + PICKUP_LINE - 1))
                ORIG_PERMS=$(stat -c '%a' "$SESSION_FILE" 2>/dev/null || stat -f '%Lp' "$SESSION_FILE" 2>/dev/null || echo "644")
                export _AWK_INSERT_BEFORE="$INSERT_BEFORE" _AWK_HEADING="### $SECTION_NAME" _AWK_CONTENT="$CONTENT"
                awk '
                    NR == ENVIRON["_AWK_INSERT_BEFORE"]+0 {
                        print ENVIRON["_AWK_HEADING"]; print ENVIRON["_AWK_CONTENT"]; print ""
                    }
                    { print }
                ' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
                unset _AWK_INSERT_BEFORE _AWK_HEADING _AWK_CONTENT
                chmod "$ORIG_PERMS" "$SESSION_FILE"
                _session_record_write "update-session-section" "$SESSION_FILE"
                _unlock
                echo "Section '${SECTION_NAME}' created in Session ${SESSION_NUM}"
                exit 0
            fi
            ;;
    esac
    echo "Could not find '### ${SECTION_NAME}' in Session ${SESSION_NUM} (missing Files sections require Pickup Context)"
    _unlock
    exit 1
fi
SECTION_ABS=$((SESSION_HEADING + SECTION_LINE - 1))

# Find the next section heading after this one (bounded by session block end)
NEXT_SECTION=$(sed -n "$((SECTION_ABS + 1)),${END_LINE}p" "$SESSION_FILE" | { grep -n "^### " || true; } | head -1 | cut -d: -f1)
if [ -n "$NEXT_SECTION" ]; then
    # Exclusive boundary: the next heading itself, even without a blank separator.
    SECTION_END=$((SECTION_ABS + NEXT_SECTION))
else
    # Terminal section: content runs to end of session block (or file)
    # +1 so that NR < SECTION_END catches the last line
    SECTION_END=$((END_LINE + 1))
fi

# Preserve original file permissions
ORIG_PERMS=$(stat -c '%a' "$SESSION_FILE" 2>/dev/null || stat -f '%Lp' "$SESSION_FILE" 2>/dev/null || echo "644")

SESSION_PRE=$(mktemp "${TMPDIR:-/tmp}/opencairn-section-pre.XXXXXX")
cp "$SESSION_FILE" "$SESSION_PRE"
if [ "$REPLACE_MODE" = "true" ]; then
    # Replace mode: remove all content lines between heading and boundary, insert new content
    # The exclusive skip range includes the old separator; emit one blank line
    # after the complete new body before the next section/session or EOF.
    TRAILING_BLANK="yes"
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
    SECTION_BODY=$(awk -v start="$SECTION_ABS" -v end="$SECTION_END" 'NR > start && NR < end' "$SESSION_FILE")

    # Check if section body is a single non-blank line starting with "None"
    NON_BLANK_COUNT=0
    FIRST_NON_BLANK=""
    while IFS= read -r line; do
        line=${line%$'\r'}  # a CRLF log's blank line is blank
        if [ -n "$line" ]; then
            NON_BLANK_COUNT=$((NON_BLANK_COUNT + 1))
            if [ -z "$FIRST_NON_BLANK" ]; then
                FIRST_NON_BLANK="$line"
            fi
        fi
    done <<< "$SECTION_BODY"

    if [ "$NON_BLANK_COUNT" -eq 1 ] && echo "$FIRST_NON_BLANK" | grep -q "^None"; then
        # Find the actual "None" line in the file
        NONE_ABS=$(printf '%s\n' "$SECTION_BODY" | { grep -n "^None" || true; } | head -1 | cut -d: -f1)
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
        LAST_CONTENT=$(printf '%s\n' "$SECTION_BODY" | { grep -n $'[^\r]' || true; } | tail -1 | cut -d: -f1)
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

# Compare exact bytes so an identical replacement does not claim a mutation.
# SESSION_PRE is outside the vault and is captured while the existing lock holds.
# Restore permissions
chmod "$ORIG_PERMS" "$SESSION_FILE"

if ! cmp -s "$SESSION_PRE" "$SESSION_FILE"; then
    _session_record_write "update-session-section" "$SESSION_FILE"
fi
rm -f "$SESSION_PRE"

_unlock

echo "Section '${SECTION_NAME}' updated in Session ${SESSION_NUM}"
