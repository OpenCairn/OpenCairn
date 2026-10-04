#!/usr/bin/env bash
# park-files.sh - mechanical session-footprint enumeration for /park
#
# Usage: park-files.sh <vault> [-m MINUTES] [repo ...]
#   MINUTES  lookback window (default 240)
#   repo     any git repo the session touched (working-tree status is printed)
#
# Prints tab-separated candidate lines, one per file, grouped by tag:
#   [receipt]    sync-receipt entries inside the window (UTC-ISO ts, path, description)
#   [config]     files under $CLAUDE_CONFIG_DIR/{commands,scripts}, personal
#                $CODEX_HOME/skills, selected user-runtime roots, and top-level
#                Claude *.log files modified inside the window
#   [repo]       git status --short per named repo
#   [git-diff]   git diff --name-status -M HEAD for the vault and named repos;
#                tracked deletions and both paths of staged moves survive here
#   [git-history] vault commits inside the window, with name-status per commit;
#                preserves intermediate paths that automatic commits removed
#   [vault]      visible vault-body files modified inside the window, excluding
#                transient roots and hidden metadata directories
#   [transient]  vault transient-surface *.md modified inside the window
#                (01 Now, 02 Inbox - never a find from the vault root: .git crawl)
#
# The three config-side checks are deliberately redundant: the receipt carries
# descriptions and reaches outside the config dir; the mtime sweep needs no
# cooperation from the writing tool (hook-written files); repo status catches
# direct edits that bypass both. Output is CANDIDATES, not attribution - the
# caller decides which lines are this session's work.
# Git rows have tag, repo root, status, old/current path, and (for a rename)
# new path. Paths are repo-relative. History time bounds discover candidates,
# not attribution: concurrent and already-parked work may appear as well.
#
# Every sweep matches on mtime OR ctime (-mmin/-cmin). A metadata-preserving
# ingress (cp -p, rsync -a, tar -p, a mover that keeps timestamps) lands a NEW
# file carrying its OLD mtime, so an mtime-only sweep never sees it; ctime is
# set by the kernel at creation and cannot be preserved from userspace, so the
# ctime arm is what surfaces it. A file this sweep still cannot see (created by
# cp -p outside these roots) needs a ledger row: locked-ingress.sh self-ledgers
# for exactly that reason.
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
CODEX_CONFIG_DIR="${CODEX_HOME:-$HOME/.codex}"
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
        \( -name .git -o -name __pycache__ \) -prune -o -type f \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print 2>/dev/null \
    | sed 's/^/[config]\t/' || true
find "$CONFIG_DIR" -maxdepth 1 -name '*.log' -type f \( -mmin -"$MIN" -o -cmin -"$MIN" \) 2>/dev/null \
    | sed 's/^/[config]\t/' || true
find "$CODEX_CONFIG_DIR/skills" \
        \( -name .git -o -name __pycache__ -o -name .system -o -name .tmp \) -prune -o \
        -type f \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print 2>/dev/null \
    | sed 's/^/[config]\t/' || true
find "$HOME/.local/libexec" "$HOME/.config/systemd/user" \
        \( -name .git -o -name __pycache__ \) -prune -o \
        \( -type f -o -type l \) \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print 2>/dev/null \
    | sed 's/^/[config]\t/' || true
if [ -e "$HOME/.config/kwinoutputconfig.json" ]; then
    find "$HOME/.config/kwinoutputconfig.json" \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print 2>/dev/null \
        | sed 's/^/[config]\t/' || true
fi

# 3. Working tree of every named repo.
diff_candidates() {
    git -C "$1" -c core.quotePath=false diff --name-status -M HEAD -- 2>/dev/null \
        | awk -v repo="$1" 'NF { print "[git-diff]\t" repo "\t" $0 }' || true
}
for repo in "$@"; do
    if git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
        git -C "$repo" status --short | sed "s|^|[repo]\t$repo\t|" || true
        diff_candidates "$repo"
    else
        printf '[repo]\t%s\tERROR: not a git repo\n' "$repo"
    fi
done

# 4. Vault git changes, including auto-saves inside the window. A net diff
# against a historical baseline would lose a file moved and then deleted;
# name-status for EACH commit retains both events. Do not inspect a containing
# repository when the vault itself is not a git root.
VAULT_ROOT=$(cd "$VAULT" && pwd -P)
GIT_ROOT=$(git -C "$VAULT" rev-parse --show-toplevel 2>/dev/null) || GIT_ROOT=""
if [ "$GIT_ROOT" = "$VAULT_ROOT" ]; then
    diff_candidates "$VAULT"
    git -C "$VAULT" -c core.quotePath=false log --since="$CUTOFF" --format= \
            --name-status -M -- 2>/dev/null \
        | awk -v repo="$VAULT" 'NF { print "[git-history]\t" repo "\t" $0 }' || true
fi

# 5. Vault body. Enumerate only visible top-level roots, then prune hidden
# metadata BEFORE descending: never crawl .git or archived transcript state.
# Unlike the shallow transient sweep, hubs and area notes can be deeply nested.
find "$VAULT" -maxdepth 1 -type f ! -name '.*' \
        \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print 2>/dev/null \
    | sed 's/^/[vault]\t/' || true
for body_root in "$VAULT"/*; do
    [ -d "$body_root" ] || continue
    case "$body_root" in "$VAULT/01 Now"|"$VAULT/02 Inbox") continue ;; esac
    find "$body_root" \( -type d \( -name '.*' -o -name __pycache__ \) \) -prune -o \
        -type f \( -mmin -"$MIN" -o -cmin -"$MIN" \) -print 2>/dev/null \
        | sed 's/^/[vault]\t/' || true
done

# 6. Transient surfaces in the vault (scoped roots - NEVER the vault root).
find "$VAULT/01 Now" "$VAULT/02 Inbox" -maxdepth 2 -type f -name '*.md' \( -mmin -"$MIN" -o -cmin -"$MIN" \) 2>/dev/null \
    | sed 's/^/[transient]\t/' || true

exit 0
