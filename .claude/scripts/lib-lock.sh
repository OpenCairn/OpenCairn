#!/usr/bin/env bash
# Portable file locking library
# Source this from scripts that need file locking.
# Provides _lock() and _unlock() functions.
#
# Usage:
#   source "$(dirname "$0")/lib-lock.sh"
#   _lock "/path/to/.lock" 10
#   # ... do work ...
#   _unlock
#
# NOTE: _lock() sets an EXIT trap to auto-release the lock on unexpected exit.
# Do NOT set your own EXIT trap before calling _lock() — it will be overwritten.
# If you need cleanup logic, set your trap AFTER _unlock, or call _unlock
# explicitly and manage cleanup yourself.
#
# Platform: Linux, macOS, Windows (Git Bash).
# Uses flock where available, mkdir-based fallback otherwise.

# Canonical lock path for a target file. EVERY writer of a given file must lock
# the SAME path or mutual exclusion silently fails — so all scripts derive the
# lock name from the target via this one function: <dir>/.<basename>.lock.
_lock_path_for() {
    local target="$1"
    printf '%s/.%s.lock' "$(dirname "$target")" "$(basename "$target")"
}

_lock() {
    _LOCK_FILE="$1"
    local timeout="${2:-10}"
    if command -v flock &>/dev/null; then
        _LOCK_MODE="flock"
        exec 9>"$_LOCK_FILE"
        flock -w "$timeout" 9 || { echo "Lock timeout after ${timeout}s" >&2; return 1; }
        trap '_unlock' EXIT
    else
        _LOCK_MODE="mkdir"
        _LOCK_DIR="${_LOCK_FILE}.d"
        local waited=0
        while ! mkdir "$_LOCK_DIR" 2>/dev/null; do
            if [ "$waited" -ge "$timeout" ]; then
                echo "Lock timeout after ${timeout}s" >&2
                return 1
            fi
            # Stale lock recovery: if the lock dir is older than the timeout,
            # the holder likely crashed (kill -9). Remove and retry.
            local lock_mtime
            lock_mtime=$(stat -c '%Y' "$_LOCK_DIR" 2>/dev/null || stat -f '%m' "$_LOCK_DIR" 2>/dev/null || echo 0)
            local now
            now=$(date +%s)
            if [ $(( now - lock_mtime )) -gt "$timeout" ]; then
                rmdir "$_LOCK_DIR" 2>/dev/null || true
            fi
            sleep 1
            waited=$((waited + 1))
        done
        trap '_unlock' EXIT
    fi
}

# _unlock branches on the mode recorded by _lock (NOT a fresh `command -v flock`
# probe — PATH can differ between lock and unlock, which would release with the
# wrong primitive and leak the lock).
_unlock() {
    if [ "${_LOCK_MODE:-}" = "flock" ]; then
        exec 9>&- 2>/dev/null || true
    elif [ "${_LOCK_MODE:-}" = "mkdir" ]; then
        rm -rf "${_LOCK_DIR:-}" 2>/dev/null || true
    fi
    trap - EXIT
}
