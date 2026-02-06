#!/usr/bin/env bash
# pickup-scan.sh - Extract session metadata for /pickup command
# Outputs TSV format for low-context menu building
#
# Requirements: bash 4.2+ (associative arrays, lowercase expansion)
#   macOS users: brew install bash (system bash is 3.2, too old)
#
# Usage: pickup-scan.sh [--days=N] [--hidden-file=PATH] [--show-hidden] [SESSION_DIR]
#
# Environment:
#   CLAUDE_SESSION_DIR - Override default session directory
#   VAULT_PATH - Base path to vault (used if CLAUDE_SESSION_DIR not set)
#
# Output format (TSV):
# DATE	SESSION_NUM	TITLE	TIME	PROJECT	LOOP_COUNT	SUMMARY
#
# Platform: Linux, macOS, Windows (Git Bash). Requires bash 4.2+.

set -euo pipefail

# Check bash version (need 4.2+ for associative arrays and ${var,,})
if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2))); then
    echo "ERROR: bash 4.2+ required. Current: ${BASH_VERSION}" >&2
    echo "  Linux: should already have bash 4+." >&2
    echo "  macOS: brew install bash (system /bin/bash is 3.2)." >&2
    echo "  Windows: Git Bash includes bash 4+." >&2
    exit 1
fi

# --- Portable date arithmetic ---
# Tries GNU date, BSD date (macOS), python3 fallback
_date_days_ago() {
    local days="$1"
    date -d "$days days ago" +%Y-%m-%d 2>/dev/null \
        || date -v-${days}d +%Y-%m-%d 2>/dev/null \
        || python3 -c "from datetime import datetime,timedelta; print((datetime.now()-timedelta(days=${days})).strftime('%Y-%m-%d'))" 2>/dev/null \
        || { echo "ERROR: Cannot calculate date. Install GNU coreutils or Python 3." >&2; return 1; }
}
# --- End portable date ---

# Defaults
DAYS=10
HIDDEN_FILE=""
SHOW_HIDDEN=false
SESSION_DIR=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --days=*)
            DAYS="${1#*=}"
            shift
            ;;
        --hidden-file=*)
            HIDDEN_FILE="${1#*=}"
            shift
            ;;
        --show-hidden)
            SHOW_HIDDEN=true
            shift
            ;;
        *)
            SESSION_DIR="$1"
            shift
            ;;
    esac
done

# Determine session directory (priority: arg > CLAUDE_SESSION_DIR > VAULT_PATH > error)
if [[ -z "$SESSION_DIR" ]]; then
    if [[ -n "${CLAUDE_SESSION_DIR:-}" ]]; then
        SESSION_DIR="$CLAUDE_SESSION_DIR"
    elif [[ -n "${VAULT_PATH:-}" ]]; then
        SESSION_DIR="$VAULT_PATH/06 Archive/Claude Sessions"
    else
        echo "ERROR: No session directory specified." >&2
        echo "Set VAULT_PATH or CLAUDE_SESSION_DIR environment variable, or pass directory as argument." >&2
        exit 1
    fi
fi

# Validate session directory exists
if [[ ! -d "$SESSION_DIR" ]]; then
    echo "ERROR: Session directory not found: $SESSION_DIR" >&2
    exit 1
fi

# Calculate cutoff date (portable)
CUTOFF_DATE=$(_date_days_ago "$DAYS") || exit 1
TODAY=$(date +%Y-%m-%d)

# Load hidden entries into arrays
declare -A HIDDEN_PROJECTS
declare -A HIDDEN_SESSIONS
declare -A SNOOZED_PROJECTS
declare -A SNOOZED_SESSIONS

if [[ -n "$HIDDEN_FILE" && -f "$HIDDEN_FILE" && "$SHOW_HIDDEN" == "false" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue

        # Check for snooze suffix
        if [[ "$line" == *"|until:"* ]]; then
            entry="${line%%|until:*}"
            snooze_date="${line##*|until:}"

            # Check if snooze has expired
            if [[ "$snooze_date" < "$TODAY" || "$snooze_date" == "$TODAY" ]]; then
                # Expired - don't hide (will be cleaned up by pickup command)
                continue
            fi

            # Active snooze
            if [[ "$entry" == *"#Session"* ]]; then
                SNOOZED_SESSIONS["${entry,,}"]="$snooze_date"
            else
                SNOOZED_PROJECTS["${entry,,}"]="$snooze_date"
            fi
        else
            # Permanent hide
            if [[ "$line" == *"#Session"* ]]; then
                HIDDEN_SESSIONS["${line,,}"]=1
            else
                HIDDEN_PROJECTS["${line,,}"]=1
            fi
        fi
    done < "$HIDDEN_FILE"
fi

# Function to check if entry should be hidden
is_hidden() {
    local date="$1"
    local session_num="$2"
    local title="$3"
    local project="$4"

    # Build session identifier
    local session_id="${date}#Session ${session_num} - ${title}"
    local session_id_lower="${session_id,,}"

    # Check session-level hiding
    [[ -v "HIDDEN_SESSIONS[$session_id_lower]" ]] && return 0
    [[ -v "SNOOZED_SESSIONS[$session_id_lower]" ]] && return 0

    # Check project-level hiding (if project exists)
    if [[ -n "$project" ]]; then
        local project_lower="${project,,}"
        [[ -v "HIDDEN_PROJECTS[$project_lower]" ]] && return 0
        [[ -v "SNOOZED_PROJECTS[$project_lower]" ]] && return 0
    fi

    return 1
}

# Find and process session files
find "$SESSION_DIR" -maxdepth 2 -name "????-??-??.md" -type f 2>/dev/null | while read -r file; do
    # Extract date from filename
    filename=$(basename "$file")
    file_date="${filename%.md}"

    # Skip files outside date range
    [[ "$file_date" < "$CUTOFF_DATE" ]] && continue

    # Process file with awk to extract sessions (POSIX compatible)
    awk -v file_date="$file_date" '
    BEGIN {
        OFS="\t"
        in_session = 0
        in_summary = 0
        in_loops = 0
        in_pickup = 0
        session_num = ""
        title = ""
        time = ""
        project = ""
        loop_count = 0
        summary = ""
    }

    # Session header: ## Session N - Title (HH:MM:SSam/pm)
    /^## Session [0-9]+ - / {
        # Output previous session if exists
        if (session_num != "") {
            # Truncate and clean summary
            gsub(/[\t\n\r]/, " ", summary)
            if (length(summary) > 150) summary = substr(summary, 1, 147) "..."
            print file_date, session_num, title, time, project, loop_count, summary
        }

        # Parse session header - extract number
        line = $0
        sub(/^## Session /, "", line)
        # line is now "N - Title (time)" or "N - Title"
        session_num = line
        sub(/ .*/, "", session_num)  # Get just the number

        # Extract title and time
        sub(/^[0-9]+ - /, "", line)  # Remove "N - ", left with "Title (time)" or "Title"

        # Check for time in parentheses at end
        if (match(line, /\([0-9:]+[ap]m\)$/)) {
            time = substr(line, RSTART+1, RLENGTH-2)  # Extract time without parens
            title = substr(line, 1, RSTART-2)  # Title is everything before " (time)"
        } else {
            time = ""
            title = line
        }

        # Reset for new session
        project = ""
        loop_count = 0
        summary = ""
        in_session = 1
        in_summary = 0
        in_loops = 0
        in_pickup = 0
        next
    }

    # Section headers
    /^### Summary/ { in_summary = 1; in_loops = 0; in_pickup = 0; next }
    /^### Key Insights/ || /^### Next Steps/ || /^### Files Created/ || /^### Files Updated/ || /^### Pickup Context/ {
        in_summary = 0
        if ($0 ~ /Next Steps/) in_loops = 1; else in_loops = 0
        if ($0 ~ /Pickup Context/) in_pickup = 1; else in_pickup = 0
        next
    }
    /^## Session/ || /^# / { in_summary = 0; in_loops = 0; in_pickup = 0 }

    # Collect summary (first paragraph only)
    in_summary && /^[^#]/ && summary == "" {
        summary = $0
        next
    }

    # Count open loops
    in_loops && /^- \[ \]/ {
        loop_count++
        next
    }

    # Extract project from Pickup Context
    in_pickup && /\*\*Project:\*\*/ {
        # Extract project name from wikilink [[path/to/Project Name]]
        # Handle wikilinks that contain ] characters (e.g., [[path#Section [CS]]])
        line = $0
        start = index(line, "[[")
        if (start > 0) {
            rest = substr(line, start + 2)
            # Find closing ]] - look for last occurrence
            end = 0
            for (i = 1; i <= length(rest) - 1; i++) {
                if (substr(rest, i, 2) == "]]") end = i
            }
            if (end > 0) {
                project = substr(rest, 1, end - 1)
                # Normalize path: extract final component after last / or #
                # Examples: "03 Projects/Foo" -> "Foo", "01 Now/WIP#Foo [CS]" -> "Foo [CS]"
                # This enables clustering sessions that link to same project via different paths
                gsub(/\//, "#", project)  # Unify separators
                n = split(project, parts, "#")
                project = parts[n]
            }
        }
        next
    }

    END {
        # Output last session
        if (session_num != "") {
            gsub(/[\t\n\r]/, " ", summary)
            if (length(summary) > 150) summary = substr(summary, 1, 147) "..."
            print file_date, session_num, title, time, project, loop_count, summary
        }
    }
    ' "$file"
done | while IFS=$'\t' read -r date session_num title time project loop_count summary; do
    # Apply hidden filtering
    if ! is_hidden "$date" "$session_num" "$title" "$project"; then
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$date" "$session_num" "$title" "$time" "$project" "$loop_count" "$summary"
    fi
done | sort -t$'\t' -k1,1r -k2,2nr
