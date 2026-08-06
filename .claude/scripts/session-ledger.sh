#!/usr/bin/env bash
# session-ledger.sh - per-session write ledger for /park's file enumeration.
#
# Two modes:
#   (hook)  PostToolUse on Write|Edit - reads the hook JSON on stdin and appends
#           one TSV line per file-mutating tool call. Emits nothing to Claude.
#   --read  prints THIS session's ledger (keyed on $CLAUDE_CODE_SESSION_ID).
#
# Usage:
#   session-ledger.sh                 # hook mode (stdin = hook JSON)
#   session-ledger.sh --read [-m MIN] # this session's writes, deduped by path
#
# Why this exists: /park Step 2a has to enumerate every file the session touched,
# and model recall under-reports it. park-files.sh reconstructs candidates from
# mtimes and git status - which cannot distinguish this session's writes from a
# concurrent session's, and is the whole reason §20 attribution needs care. The
# ledger records the session id at write time, so attribution is exact rather
# than inferred. It does NOT replace park-files.sh: writes that bypass the Write
# and Edit tools (shell redirection, scripts, formatting hooks) are invisible
# here, so the mtime sweep stays as the backstop for those.
#
# Storage: $CLAUDE_CONFIG_DIR/.session-state/<session-id>.tsv
#   columns: ISO8601-UTC \t tool \t absolute-path \t agent-id ("main" on the main thread)
#
# A sub-agent's writes ledger under the PARENT's session_id (verified: a sub-agent
# Write appended to the parent's .tsv and created no new file). So the ledger is
# one list spanning the main thread and every sub-agent, and the agent boundary
# that §20 turns on has to be RECORDED, not inferred - hence the agent_id column,
# which hook input supplies precisely to distinguish the two.
#
# Fails open in hook mode - a broken ledger must never block a write that has
# already landed.
#
# Requires: jq (hook mode only). Platform: Linux, macOS, Windows (Git Bash).
set -uo pipefail

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
STATE_DIR="$CONFIG_DIR/.session-state"

# --- read mode ---------------------------------------------------------------
if [ "${1:-}" = "--read" ]; then
    set -e
    shift
    MIN=""
    if [ "${1:-}" = "-m" ]; then
        [ $# -ge 2 ] || { echo "Usage: $0 --read [-m MINUTES]" >&2; exit 1; }
        MIN="$2"; shift 2
    fi
    SID="${CLAUDE_CODE_SESSION_ID:-}"
    if [ -z "$SID" ]; then
        echo "ERROR: CLAUDE_CODE_SESSION_ID unset - cannot identify this session's ledger." >&2
        echo "       Fall back to park-files.sh for enumeration." >&2
        exit 1
    fi
    LEDGER="$STATE_DIR/$SID.tsv"

    # Ledgers other than this session's, written inside the window. These are
    # CONCURRENT SESSIONS, full stop - a sub-agent of this session ledgers under
    # this session's id (see header), so it never appears here. Reported rather
    # than hidden so a §20 exclusion is made against something visible.
    others() {
        local w="${1:-240}" f found=0
        for f in "$STATE_DIR"/*.tsv; do
            [ -f "$f" ] || continue
            [ "$f" = "$LEDGER" ] && continue
            # ONE test, not two: `find FILE -pred` exits 0 even when the predicate
            # does not match, so an exit-status guard here is dead code - only the
            # emptiness of the output actually filters.
            find "$f" -mmin -"$w" 2>/dev/null | grep -q . || continue
            [ "$found" -eq 0 ] && { echo "# CONCURRENT-SESSION ledgers active in the last ${w}min. These are other"; \
                                    echo "# sessions, not sub-agents of this one — exclude per §20 unless you know better."; found=1; }
            # Paths, not just a count: the caller is told to attribute each file per
            # §20, which it cannot do against a bare number.
            echo "# $(basename "$f" .tsv)"
            awk -F'\t' '{print $3}' "$f" 2>/dev/null | sort -u | sed 's/^/#     /'
        done
    }

    if [ ! -f "$LEDGER" ]; then
        echo "NOTE: no ledger for this session ($SID) - either the hook is not wired"
        echo "      (/setup-hooks), or no Write/Edit tool call has landed yet."
        others "${MIN:-240}"
        exit 0
    fi

    CUTOFF=""
    if [ -n "$MIN" ]; then
        CUTOFF=$(date -u -d "$MIN minutes ago" +%FT%TZ 2>/dev/null \
            || date -u -v-"${MIN}"M +%FT%TZ 2>/dev/null \
            || python3 -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)-timedelta(minutes=$MIN)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
    fi

    # Dedupe by path: first-seen ts, last-seen ts, write count, tools used.
    echo "# ledger begins $(head -1 "$LEDGER" 2>/dev/null | cut -f1) — writes before the hook was"
    echo "# wired are NOT here; park-files.sh is the backstop for them."
    echo "# path	writes	first..last (UTC)	agents"
    awk -F'\t' -v c="$CUTOFF" '
        c != "" && $1 < c { next }
        {
            kept++          # NOT NR: NR counts rows the cutoff above skipped
            p = $3
            if (!(p in first)) { first[p] = $1; order[++n] = p }
            last[p] = $1; count[p]++
            if (index(tools[p], $2) == 0) tools[p] = (tools[p] == "" ? $2 : tools[p] "," $2)
            a = ($4 == "" ? "?" : $4)   # pre-4-column row: UNKNOWN, never a positive "main"
            if (index(ag[p], a) == 0) ag[p] = (ag[p] == "" ? a : ag[p] "," a)
        }
        END {
            for (i = 1; i <= n; i++) {
                p = order[i]
                printf "%s\t%dx %s\t%s..%s\t%s\n", p, count[p], tools[p], substr(first[p],12,5), substr(last[p],12,5), ag[p]
            }
            printf "TOTAL\t%d file(s)\t%d write(s)\n", n, kept
        }
    ' "$LEDGER"
    others "${MIN:-240}"
    exit 0
fi

# --- hook mode ---------------------------------------------------------------
[ -z "${1:-}" ] || { echo "Usage: $0 [--read [-m MINUTES]]" >&2; exit 1; }

INPUT=$(cat)
command -v jq >/dev/null 2>&1 || exit 0

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -n "$FILE" ] || exit 0
SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
[ -n "$SID" ] || exit 0
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // "?"' 2>/dev/null) || TOOL="?"
AGENT=$(printf '%s' "$INPUT" | jq -r '.agent_id // "main"' 2>/dev/null) || AGENT="main"

# Never ledger our own state files. The parboil draft is written with the Write
# tool, so without this the draft's own write lands in the ledger: LEDGER NOW is
# then permanently > the draft's SNAPSHOT-LEDGER-LINES, park's cheap adopt-whole
# branch becomes unreachable, and the state file itself shows up as session work
# product bound for the session log.
case "$FILE" in "$STATE_DIR"/*) exit 0 ;; esac

mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
LEDGER="$STATE_DIR/$SID.tsv"

# First write of a session is the natural once-per-session hook for pruning, so
# the sweep costs one find per session rather than one per write.
[ -f "$LEDGER" ] || find "$STATE_DIR" -maxdepth 1 -type f -mtime +14 -delete 2>/dev/null || true

# Single short line, O_APPEND: atomic against concurrent sessions even though
# each session normally has its own file.
printf '%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$TOOL" "$FILE" "$AGENT" >> "$LEDGER" 2>/dev/null || true
exit 0
