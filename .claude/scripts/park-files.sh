#!/usr/bin/env bash
# park-files.sh - mechanical session-footprint enumeration for /park
#
# Usage: park-files.sh <vault> [-m MINUTES] [repo ...]
#   MINUTES  lookback window (default 240)
#   repo     any git repo the session touched (working-tree status is printed)
#
# Prints tab-separated candidate lines, one per file, grouped by tag:
#   [receipt]    sync-receipt entries inside the window (UTC-ISO ts, path, description)
#   [config]     files under $CLAUDE_CONFIG_DIR/{commands,scripts} + top-level *.log
#                modified inside the window
#   [repo]       git status --short per named repo
#   [transient]  vault transient-surface *.md modified inside the window
#                (01 Now, 02 Inbox - never a find from the vault root: .git crawl)
#
# The three config-side checks are deliberately redundant: the receipt carries
# descriptions and reaches outside the config dir; the mtime sweep needs no
# cooperation from the writing tool (hook-written files); repo status catches
# direct edits that bypass both. Output is CANDIDATES, not attribution - the
# caller decides which lines are this session's work.
#
# Platform: Linux, macOS (BSD date fallback), Windows Git Bash.
set -euo pipefail

usage() { echo "Usage: $0 <vault> [-m MINUTES] [repo ...]" >&2; exit 1; }
[ $# -ge 1 ] || usage
VAULT="$1"; shift
[ -d "$VAULT" ] || { echo "ERROR: vault not found: $VAULT" >&2; exit 1; }

MIN=240
if [ "${1:-}" = "-m" ]; then
    [ $# -ge 2 ] || usage
    MIN="$2"; shift 2
fi

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CUTOFF=$(date -u -d "$MIN minutes ago" +%FT%TZ 2>/dev/null \
    || date -u -v-"${MIN}"M +%FT%TZ 2>/dev/null \
    || python3 -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)-timedelta(minutes=$MIN)).strftime('%Y-%m-%dT%H:%M:%SZ'))")

# 1. Receipts from tooling that records its own writes (e.g. /sync-template).
#    Select by timestamp, never tail -N (silently truncates busy sessions).
if [ -f "$CONFIG_DIR/.sync-receipt" ]; then
    awk -F'\t' -v c="$CUTOFF" '$1 >= c { print "[receipt]\t" $0 }' "$CONFIG_DIR/.sync-receipt"
fi

# 2. mtime sweep of the config tree (recursive: skill bundles live in subdirs).
find "$CONFIG_DIR/commands" "$CONFIG_DIR/scripts" \
        \( -name .git -o -name __pycache__ \) -prune -o -type f -mmin -"$MIN" -print 2>/dev/null \
    | sed 's/^/[config]\t/' || true
find "$CONFIG_DIR" -maxdepth 1 -name '*.log' -type f -mmin -"$MIN" 2>/dev/null \
    | sed 's/^/[config]\t/' || true

# 3. Working tree of every named repo.
for repo in "$@"; do
    if git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
        git -C "$repo" status --short | sed "s|^|[repo]\t$repo\t|" || true
    else
        printf '[repo]\t%s\tERROR: not a git repo\n' "$repo"
    fi
done

# 4. Transient surfaces in the vault (scoped roots - NEVER the vault root).
find "$VAULT/01 Now" "$VAULT/02 Inbox" -maxdepth 2 -type f -name '*.md' -mmin -"$MIN" 2>/dev/null \
    | sed 's/^/[transient]\t/' || true

exit 0
