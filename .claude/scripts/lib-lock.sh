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

_lock() {
    _LOCK_FILE="$1"
    local timeout="${2:-10}"
    if command -v flock &>/dev/null; then
        exec 9>"$_LOCK_FILE"
        flock -w "$timeout" 9 || { echo "Lock timeout after ${timeout}s" >&2; return 1; }
        trap '_unlock' EXIT
    else
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

_unlock() {
    if command -v flock &>/dev/null; then
        exec 9>&- 2>/dev/null || true
    else
        rm -rf "${_LOCK_DIR:-}" 2>/dev/null || true
    fi
    trap - EXIT
}
